# This file is adapted from https://github.com/jennyzzt/dgm.

import argparse
import datetime
import json
import os
import random
import re
import threading
import traceback
from prompts.verify_model import HierarchicalValidator
from prompts.obfuscation_model import ObfuscationModel
from prompts.reflection_model import ReflectionModel
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import stdev

from utils.common_utils import load_json_file
from utils.evo_utils import (get_all_performance, get_model_patch_paths,
                             is_compiled_self_improve)

dataset = None
alpha = 0.5
K = 0.5
bias_factor = 5
nodes = {}
total_tasks = []
output_dir = ""
polyglot = False
n_task_evals = 0
init_evaluated_tasks = []
llm = ""
timeout = 3600

pending_tasks_lock = threading.Lock()


def fix_invalid_json_escapes(json_str):
    """
    修复JSON字符串中的非法转义字符，保留合法转义。
    处理重点：去除单引号前的多余反斜杠（\' → '），及其他非标准转义（如\a → a）。
    """
    # 定义JSON合法的转义字符（正则匹配）
    # 合法转义包括：\"  \\  \/  \b  \f  \n  \r  \t  \uXXXX（Unicode）
    valid_escapes = r'(?:\\"|\\\\|\\/|\\b|\\f|\\n|\\r|\\t|\\u[0-9a-fA-F]{4})'

    # 匹配所有反斜杠开头的序列，但排除合法转义
    # 分组1：合法转义（保留）；分组2：非法转义（处理）
    pattern = re.compile(f'({valid_escapes})|(\\\\.)')

    def replace_invalid(match):
        # 若匹配到合法转义，直接返回
        if match.group(1):
            return match.group(1)
        # 若匹配到非法转义（如\'、\a等），去掉反斜杠，保留后面的字符
        elif match.group(2):
            return match.group(2)[1:]  # 取反斜杠后面的字符
        return match.group(0)

    # 替换非法转义
    fixed_str = pattern.sub(replace_invalid, json_str)
    #修复Python方法调用中". "（点+空格）的错误写法（如 _U(). _c() → _U()._c()）
    fixed_str = re.sub(r'\(\s*\.\s+', '().', fixed_str, flags=re.DOTALL)
    return fixed_str

def init(_polyglot, _output_dir, _tasks, _n_task_evals=0, _llm="", _timeout=3600):
    global output_dir, total_tasks, polyglot, n_task_evals, llm, timeout
    output_dir = _output_dir
    timeout = _timeout
    seen = set()
    total_tasks = []
    for item in _tasks:
        if item not in seen:
            seen.add(item)
            total_tasks.append(item)
    polyglot = _polyglot
    n_task_evals = _n_task_evals
    llm = _llm


def any_exceeding_context_length(output_dir, node_id, instance_ids):
    """
    Check if any of the issues have exceeded the context length.
    """
    for instance_id in instance_ids:
        md_logs, _, _, _ = find_selfimprove_eval_logs(
            instance_id, output_dir, node_id, filter=False
        )
        error_strs = [
            r"Error in get_response_withtools: Error code: 400 - {'message': 'Input is too long for requested model.'}",
            r"Error in get_response_withtools: Error code: 400 - {'object': 'error', 'message': \"This model's maximum context length is \d+ tokens. However, you requested \d+ tokens in the messages, Please reduce the length of the messages. None\", 'type': 'BadRequestError', 'param': None, 'code': 400}",
            r"Error in get_response_withtools: Error code: 400 - {'error': {'message': 'Your input exceeds the context window of this model. Please adjust your input and try again.', 'type': 'invalid_request_error', 'param': 'input', 'code': 'context_length_exceeded'}}",
        ]
        for md_log in md_logs:
            if any(
                re.search(f"{error_str}\n{error_str}", md_log)
                for error_str in error_strs
            ):
                return True
    return False


def choose_entry(parent_node, debug=False):
    """
    Choose entry for self-improvement given a parent node.
    """
    try:
        metadata_path = os.path.join(output_dir, parent_node, "metadata.json")
        metadata = load_json_file(metadata_path)
        metadata = {
            "accuracy_score": metadata["overall_performance"]["accuracy_score"],
            "total_unresolved_ids": metadata["overall_performance"][
                "total_unresolved_ids"
            ],
            "total_emptypatch_ids": metadata["overall_performance"][
                "total_emptypatch_ids"
            ],
            "total_resolved_ids": metadata["overall_performance"]["total_resolved_ids"],
            "children_count": 0,
        }
    except Exception as e:
        # probably because swe-eval failed, generated code did not compile, etc.
        raise RuntimeError(f"{parent_node} not eligible for being a parent: {e}")
    if debug:
        safe_log(metadata)

    empty_ids = metadata["total_emptypatch_ids"]
    resolved_ids = metadata["total_resolved_ids"]
    unresolved_ids = metadata["total_unresolved_ids"]

    entry = None

    if polyglot:
        entry_ids = empty_ids + unresolved_ids
        if not entry_ids:
            entry_ids = resolved_ids + empty_ids + unresolved_ids
        entry = random.choice(entry_ids)
    else:
        num_total_ids = len(empty_ids) + len(resolved_ids) + len(unresolved_ids)

        if len(empty_ids) >= 0.1 * num_total_ids and random.random() < 0.25:
            entry = "solve_empty_patches"

        elif random.random() < 0.25:
            entry = "solve_stochasticity"

        elif (
            any_exceeding_context_length(
                output_dir, parent_node, empty_ids + unresolved_ids
            )
            and random.random() < 0.25
        ):
            entry = "solve_contextlength"

        elif len(unresolved_ids) != 0:
            entry_ids = unresolved_ids
            entry = random.choice(entry_ids)

        else:
            entry = random.choice(resolved_ids + empty_ids + unresolved_ids)
    if entry is None:
        safe_log(metadata)
        raise RuntimeError(
            f"Failed to choose an entry for self-improvement based on {parent_node}."
        )
    return entry


def get_metadata(prevrun_dir):
    metadata_file = os.path.join(prevrun_dir, "metadata.json")
    with open(metadata_file, "r") as f:
        metadata = json.load(f)
    return metadata


def eval_code(
    node_id,
    init_code_path=None,
    obfuscated_code=None,
    obfuscated_code_path=None,
    origin_code=None,
    strategy=None,
    config="./config.yaml"
):
    vr = HierarchicalValidator(config)
    if node_id == "initial":
        #直接评估
        with open(init_code_path, 'r', encoding='utf-8') as file:
            code = file.read()
        verify_result = vr.verify(code, code, init_code_path, strategy)
        return verify_result, code
    else:
        verify_result = vr.verify(origin_code, obfuscated_code, obfuscated_code_path, strategy)
        return verify_result


def sample_child(parent_node, output_dir, run_id, force_rebuild=False, max_try=1, config="./config.yaml", expand_id="initial"):
    metadata = {}
    root_dir = "../"  # root_dir should be /hgm
    out_dir_base = output_dir  # out_dir_base should be /hgm/output_selfimprove/ or /hgm/output_hgm/{hgm_run_id}/
    run_output_dir = os.path.join(root_dir, f"{output_dir}/{expand_id}/")
    os.makedirs(run_output_dir, exist_ok=True)
    ob = ObfuscationModel(config)
    rf = ReflectionModel(config)
    #如果父节点策略不为空则开始反思
    if parent_node.strategy is not None:
        rf_result = rf.reflection_result_generate(parent_node.ori_code, parent_node.code, parent_node.strategy, parent_node.verify_result)
        #rf_result = ob.reflection_result_generate(parent_node.ori_code, parent_node.code, "", parent_node.verify_result,"")
        print(rf_result)
        #解析反思补充对/错题本
        rf_result = re.sub(r".*?</think>", "", rf_result, flags=re.DOTALL)
        json_match = re.search(r'\{.*\}', rf_result, flags=re.DOTALL)
        json_str = json_match.group()
        json_str = fix_invalid_json_escapes(json_str)
        success = json.loads(json_str)["success"]
        fail = json.loads(json_str)["fail"]
        with open(f"./output/{run_id}/failed.txt", "a+", encoding="utf-8") as file:
            for strategy in fail:
                file.write(strategy["strategy_name"]+":"+strategy["reason"]+"\n")
        with open(f"./output/{run_id}/success.txt", "a+", encoding="utf-8") as file:
            for strategy in success:
                file.write(strategy["strategy_name"] + ":" + strategy["reason"] + "\n")
    failed_strategies = None
    if os.path.exists(f"./output/{run_id}/failed.txt"):
        with open(f"./output/{run_id}/failed.txt", "r+", encoding="utf-8") as strategy_f:
            failed_strategies = strategy_f.read()
    strategy_result = rf.strategy_result_generate(parent_node.ori_code, parent_node.code, parent_node.strategy, parent_node.verify_result, failed_strategies)
    with open(output_dir + f"/{expand_id}" + "/strategy_result.txt", 'w', encoding='utf-8') as f:
        f.write(strategy_result)  # 写入字符串
    # 匹配 JSON 对象（以 { 开始，以 } 结束）
    json_match = re.search(r'\{.*\}', strategy_result, re.DOTALL)
    json_str = ""
    try:
        json_str = json_match.group()
    except json.JSONDecodeError:
        # 如果提取的部分不是有效的 JSON，可以尝试更宽松的匹配
        json_str = "failed"
    finally:
        return json_str
