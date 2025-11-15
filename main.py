import re
import shutil
import json
import argparse
import traceback
import random
import time
import json
import os
import numpy as np
import datetime
import threading
from collections import defaultdict

import hgm_utils
from obfuscation_model import ObfuscationModel
from reward_model import RewardModel
from verify_model import VerifyModel
from utils.docker_utils import copy_src_files, setup_logger
from config import load_config
from utils.common_utils import load_json_file
from concurrent.futures import (ThreadPoolExecutor, as_completed, ProcessPoolExecutor, TimeoutError)
from utils.evo_utils import load_hgm_metadata
from tree import Node

global config_path


def update_metadata(output_dir, prevrun_dir, node):
    print(output_dir)
    with open(os.path.join(output_dir, "hgm_metadata.jsonl"), "a") as f:
        f.write(
            json.dumps(
                {
                    "nodes": [
                        node.save_as_dict()
                    ],
                },
                indent=2,
            )
            + "\n"
        )
    metadata_file = os.path.join(prevrun_dir, "metadata.json")
    # 读取现有的 metadata.json 文件
    if os.path.exists(metadata_file):
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
    else:
        # 如果文件不存在，创建基础结构
        metadata = {
            "nodes": {},
            "timestamp": "",
            "initial_code_path": ""
        }
    node_dict = node.save_as_dict()
    node_id = node_dict.get("node_id")
    metadata["nodes"][node_id] = node_dict
    #add child
    metadata["nodes"][node.parent_id]["child_ids"].append(
        node.node_id
    )
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)
    # json.dump(
    #     hgm_utils.init_evaluated_tasks,
    #     open(os.path.join(output_dir, "init_evaluated_tasks.json"), "w"),
    # )


def get_node_by_node_id(node_id):
    """
    通过node_id查找节点信息
    """
    if not hasattr(hgm_utils, 'nodes'):
        print("节点树未初始化")
        return None

    for _, node in hgm_utils.nodes.items():
        if node.node_id == node_id:
            return {
                'node_id': node.node_id,
                'parent_id': node.parent_id,
                'child_ids': node.child_ids,
                # 'utility_measures': node.utility_measures,
                'verify_result': getattr(node, 'verify_result', {})
            }

    print(f"未找到node_id为 {node_id} 的节点")
    return None


####初始生成####
def initialize_run(
        output_dir,
        initial_code_path,
        prevrun_dir=None,
        config_path=None,
        timeout=3600
):
    print(f"Previous run directory: {prevrun_dir}")
    # 创建必要的目录
    if not os.path.exists(prevrun_dir):
        os.makedirs(prevrun_dir)

    # 初始化节点计数器（如果不存在）
    if not hasattr(hgm_utils, 'node_counter'):
        hgm_utils.node_counter = 0

    # 检查是否存在之前的运行结果
    prevrun_metadata_path = os.path.join(prevrun_dir, "metadata.json") if prevrun_dir else None

    # 初始化节点树结构
    nodes = {}
    submitted_ids = defaultdict(set)

    # 如果没有之前的运行结果，进行初始验证
    if not prevrun_dir or not os.path.exists(prevrun_metadata_path):
        print("No previous run found, performing initial verification...")

        # 执行初始代码验证
        verify_result, code = hgm_utils.eval_code(
            node_id="initial",
            init_code_path=initial_code_path,
            config=config_path
        )
        print(verify_result)
        score_match = re.search(r'评分:\s*(\d)/5', verify_result)
        if not score_match:
            raise ValueError("Can not find score.")
        score = int(score_match.group(1))
        print("Verification score:", score)
        # 创建初始节点
        initial_node = Node(node_id="initial", verify_result=verify_result, score=score, code=code, ori_code=code)

        # 保存初始节点
        nodes["initial"] = initial_node

        # 构建完整的metadata
        metadata = {
            "nodes": {
                node_id: initial_node.save_as_dict()
                for node_id, node in nodes.items()
            },
            "timestamp": datetime.datetime.now().isoformat(),
            "initial_code_path": initial_code_path
        }

        # 保存metadata到输出目录
        metadata_path = os.path.join(prevrun_dir, "metadata.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"Initial verification completed. Results saved to {metadata_path}")

    else:
        print(f"Loading previous run results from {prevrun_metadata_path}")

        # 加载之前的metadata
        with open(prevrun_metadata_path, 'r') as f:
            prev_metadata = json.load(f)

        # 恢复节点计数器
        hgm_utils.node_counter = prev_metadata.get("node_counter", 0)

        # 重建节点树
        for nid, node_data in prev_metadata.get("nodes", {}).items():
            node = Node(node_id=node_data["node_id"])
            node.node_id = node_data["node_id"]
            node.parent_id = node_data["parent_id"]
            #node.child_ids = node_data["child_ids"]
            node.verify_result = node_data["verify_result"]
            node.score = node_data["score"]
            node.code = node_data["code"]
            node.strategy = node_data["strategy"]
            node.ori_code = node_data["ori_code"]
            nodes[node_data["node_id"]] = node
        # 重建父子关系
        for node_id, node in nodes.items():
            if node.parent_id and node.parent_id in nodes:
                parent_node = nodes[node.parent_id]
                # 确保父子关系是双向的
                if node not in parent_node.child_ids:
                    parent_node.child_ids.append(node)
        # for node_id, node in nodes.items():
        #     print(node_id, node.child_ids, node.score, node)
        # 恢复submitted_ids
        submitted_ids_data = prev_metadata.get("submitted_ids", {})
        for node_id, task_list in submitted_ids_data.items():
            submitted_ids[node_id] = set(task_list)
        print(f"Loaded {len(nodes)} nodes from previous run")

    # 复制初始代码到输出目录
    initial_dest = os.path.join(output_dir, "initial")
    if not os.path.exists(initial_dest):
        if os.path.isfile(initial_code_path):
            # 如果是单个文件
            shutil.copy2(initial_code_path, initial_dest)
        else:
            # 如果是目录，复制整个目录
            shutil.copytree(initial_code_path, initial_dest)

    # 将节点树保存到hgm_utils中，以便其他函数访问
    hgm_utils.nodes = nodes

    print(f"Initialization completed. Total nodes: {len(nodes)}")
    # node_info = get_node_by_node_id("initial")
    # if node_info:
    #     print(json.dumps(node_info, indent=2))
    return submitted_ids


# 添加一个辅助函数来更新和保存节点树
def update_node_tree(output_dir, new_node, parent_node=None, submitted_ids=None):
    """
    更新节点树并保存到metadata.json
    """
    # 确保hgm_utils.nodes存在
    if not hasattr(hgm_utils, 'nodes'):
        hgm_utils.nodes = {}

    # 分配节点ID
    if not hasattr(new_node, 'id') or not new_node.id:
        hgm_utils.node_counter += 1
        new_node.id = f"node_{hgm_utils.node_counter}"

    # 设置父子关系
    if parent_node:
        new_node.parent_id = parent_node.id
        if new_node.id not in parent_node.child_ids:
            parent_node.child_ids.append(new_node.id)
    else:
        new_node.parent_id = None

    # 确保child_ids属性存在
    if not hasattr(new_node, 'child_ids'):
        new_node.child_ids = []

    # 添加新节点到节点树
    hgm_utils.nodes[new_node.id] = new_node

    # 构建完整的metadata
    metadata = {
        "nodes": {
            node_id: {
                "id": node.id,
                "node_id": node.node_id,
                "parent_id": node.parent_id,
                "child_ids": node.child_ids,
                "utility_measures": node.utility_measures,
                "verify_result": getattr(node, 'verify_result', {})
            }
            for node_id, node in hgm_utils.nodes.items()
        },
        "submitted_ids": {node_id: list(task_set) for node_id, task_set in
                          submitted_ids.items()} if submitted_ids else {},
        "node_counter": hgm_utils.node_counter,
        "timestamp": datetime.datetime.now().isoformat()
    }

    # 保存metadata到输出目录
    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"Node tree updated. New node: {new_node.id}, Parent: {new_node.parent_id}")

    return new_node.id


def main():
    parser = argparse.ArgumentParser(description="Optimistic Tree Search")
    parser.add_argument(
        "--config",
        type=str,
        default="./config.yaml",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--cwe_type",
        type=str,
        default=None,
        help="Maximum number of evolution iterations.",
    )
    parser.add_argument(
        "--max_task_evals",
        type=int,
        default=None,
        help="Maximum number of evolution iterations.",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=None,
        help="Number of parallel workers for self-improvement attempts.",
    )
    parser.add_argument(
        "--continue_from",
        type=str,
        default=None,
        help="Directory to continue the run from.",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Output directory for this run (overrides config).",
    )
    parser.add_argument(
        "--polyglot",
        dest="polyglot",
        action="store_true",
        help="Run Polyglot benchmark instead of SWE-bench.",
    )
    parser.add_argument(
        "--no_polyglot",
        dest="polyglot",
        action="store_false",
        help="Disable Polyglot benchmark even if enabled in config.",
    )
    parser.add_argument(
        "--self_improve_llm",
        type=str,
        default=None,
        help="LLM model to use for self-improvement",
    )
    parser.add_argument(
        "--downstream_llm",
        type=str,
        default=None,
        help="LLM model to use for downstream tasks",
    )
    parser.add_argument(
        "--diagnose_llm",
        type=str,
        default=None,
        help="LLM model to use for diagnosis",
    )
    parser.add_argument(
        "--alpha", type=float, default=None, help="Alpha parameter for node expansion."
    )
    parser.add_argument(
        "--cool_down",
        dest="cool_down",
        action="store_true",
        help="Use a decreasing temperature over iterations.",
    )
    parser.add_argument(
        "--no_cool_down",
        dest="cool_down",
        action="store_false",
        help="Disable decreasing temperature over iterations even if enabled in config.",
    )
    parser.add_argument(
        "--beta", type=float, default=None, help="Cooling down factor beta."
    )
    parser.add_argument(
        "--full_eval",
        dest="full_eval",
        action="store_true",
        help="Run full evaluation on SWE even if disabled in config.",
    )

    parser.add_argument(
        "--self_improve_timeout",
        type=int,
        default=None,
        help="Timeout for self-improvement attempts.",
    )
    parser.add_argument(
        "--evaluation_timeout",
        type=int,
        default=None,
        help="Timeout for evaluation attempts.",
    )
    parser.add_argument(
        "--n_pseudo_descendant_evals",
        type=int,
        default=None,
        help="Number of pseudo descendant evaluations.",
    )
    parser.add_argument(
        "--eval_random_level",
        type=float,
        default=None,
        help="Randomness level for evaluation task selection.",
    )
    parser.add_argument(
        "--initial_agent_name",
        type=str,
        default="default_agent",
        help="Name of the initial agent.",
    )

    parser.set_defaults(polyglot=None, cool_down=None, full_eval=None)

    args = parser.parse_args()

    overrides = {}
    if args.max_task_evals is not None:
        overrides["execution.max_task_evals"] = args.max_task_evals
    if args.max_workers is not None:
        overrides["execution.max_workers"] = args.max_workers
    if args.continue_from is not None:
        overrides["paths.continue_from"] = args.continue_from
    if args.output_dir is not None:
        overrides["paths.output_dir"] = args.output_dir
    if args.self_improve_llm is not None:
        overrides["llm.self_improve_llm"] = args.self_improve_llm
    if args.downstream_llm is not None:
        overrides["llm.downstream_llm"] = args.downstream_llm
    if args.diagnose_llm is not None:
        overrides["llm.diagnose_llm"] = args.diagnose_llm
    if args.alpha is not None:
        overrides["optimization.alpha"] = args.alpha
    if args.cool_down is not None:
        overrides["optimization.cool_down"] = args.cool_down
    if args.beta is not None:
        overrides["optimization.beta"] = args.beta
    if args.full_eval is not None:
        overrides["evaluation.full_eval"] = args.full_eval
    if args.self_improve_timeout is not None:
        overrides["execution.self_improve_timeout"] = args.self_improve_timeout
    if args.evaluation_timeout is not None:
        overrides["execution.evaluation_timeout"] = args.evaluation_timeout
    if args.n_pseudo_descendant_evals is not None:
        overrides["optimization.n_pseudo_descendant_evals"] = args.n_pseudo_descendant_evals
    if args.eval_random_level is not None:
        overrides["optimization.eval_random_level"] = args.eval_random_level
    if args.polyglot is not None:
        overrides["evaluation.polyglot"] = args.polyglot
    if args.initial_agent_name is not None:
        overrides["paths.initial_agent_name"] = args.initial_agent_name

    config = load_config(args.config, **overrides)

    if not config.paths.initial_agent_name:
        parser.error(
            "Initial agent name must be provided either in config.yaml or via --initial_agent_name."
        )

    llm_cfg = config.llm
    opt_cfg = config.optimization
    exec_cfg = config.execution
    eval_cfg = config.evaluation
    path_cfg = config.paths

    config_path = args.config

    # variables for cco run
    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_dir = os.path.abspath(os.path.join("./output", run_id))
    os.makedirs(output_dir, exist_ok=True)
    print(f"Working directory: {os.getcwd()}")
    #print(f"Using config file: {args.config}")
    print(f"Output directory: {output_dir}")
    print(f"Output directory exists: {os.path.exists(output_dir)}")
    # Initialize logger early
    logger = setup_logger(os.path.join(output_dir, "hgm_outer.log"))
    cwe_type = args.cwe_type if args.cwe_type is not None else "CWE79_direct-use-of-jinja2"
    prevrun_dir = f"./prevrun/{cwe_type}"
    submitted_ids = initialize_run(
        output_dir=output_dir,
        initial_code_path=f"./{cwe_type}/ori_code.py",
        prevrun_dir=prevrun_dir,
        config_path=config_path
    )

    node_info = get_node_by_node_id("initial")

    # if node_info:
    #     print(json.dumps(node_info, indent=2))
    total_num_tasks = len(hgm_utils.total_tasks)
    # Set up logger
    logger.info(
        f"Starting HGM run {run_id} with configuration: {config.to_dict()}"
    )

    def TS_sample(evals, nodes):
        print(evals)
        alphas = [1 + np.sum(de)/5 for de in evals]
        betas = [1 + len(de) - np.sum(de)/5 for de in evals]
        print(alphas, betas)
        if opt_cfg.cool_down:
            alphas = np.array(alphas) * (
                10000
                if exec_cfg.max_task_evals == hgm_utils.n_task_evals
                else exec_cfg.max_task_evals**opt_cfg.beta
                / (exec_cfg.max_task_evals - hgm_utils.n_task_evals) ** opt_cfg.beta
            )
            betas = np.array(betas) * (
                10000
                if exec_cfg.max_task_evals == hgm_utils.n_task_evals
                else exec_cfg.max_task_evals**opt_cfg.beta
                / (exec_cfg.max_task_evals - hgm_utils.n_task_evals) ** opt_cfg.beta
            )
        thetas = np.random.beta(alphas, betas)
        print(thetas, np.argmax(thetas))
        return np.argmax(thetas)

    n_pending_expands = 0
    n_pending_measures = 0
    lock = threading.Lock()

    def expand():
        with lock:
            for node in hgm_utils.nodes.values():
                print(node.score)
            nodes = [
                node
                for node in hgm_utils.nodes.values()
                if np.isfinite(node.score) and node.score >= 0
            ]
            descendant_evals = [
                node.get_descendant_evals()
                for node in nodes
            ]
            selected_node = nodes[TS_sample(descendant_evals, nodes)]
        child_node_strategy = hgm_utils.sample_child(
            selected_node,
            output_dir,
            config=config_path
        )
        print(child_node_strategy)
        score = 0
        if child_node_strategy != "failed":
            #ob = ObfuscationModel("./config.yaml")
            ob = ObfuscationModel(config_path)
            ob_result = ob.obfuscation_result_generate(selected_node.code, child_node_strategy)
            print(ob_result)
            #去除<think></think>标签内容
            ob_result = re.sub(r".*?</think>", "", ob_result, flags=re.DOTALL)
            json_match = re.search(r'\{.*\}', ob_result, flags=re.DOTALL)
            json_str = json_match.group()
            json_str = hgm_utils.fix_invalid_json_escapes(json_str)
            print("_______________________")
            print(json_str)
            print("_______________________")
            code = json.loads(json_str)["code"]
            #检测
            verify_result = hgm_utils.eval_code(node_id=run_id, code=code, config=config_path)
            print(verify_result)
            score_match = re.search(r'评分:\s*(\d)/5', verify_result)
            if not score_match:
                raise ValueError("Can not find score.")
            score = int(score_match.group(1))
            print("Verification score:", score)
            with lock:
                new_node = Node(node_id=run_id, parent_id=selected_node.node_id, strategy=child_node_strategy,
                                score=score, verify_result=verify_result, code=code, ori_code=selected_node.code)
                selected_node.child_ids.append(
                    new_node
                )
                update_metadata(output_dir, prevrun_dir, new_node)
        if score == 5:
            return True
        return False

    flag = False
    while not flag:
        flag = expand()
    # try:
    #     with ThreadPoolExecutor(max_workers=exec_cfg.max_workers) as executor:
    #         futures = [
    #             executor.submit(expand)
    #             for _ in range(
    #                 # len(hgm_utils.nodes) - 1,
    #                 # #min(5, int(exec_cfg.max_workers**opt_cfg.alpha)),
    #                 # min(10, 10),
    #                 1
    #             )
    #         ]
    #         for future in as_completed(futures):
    #             future.result()
    #
    #     # with ThreadPoolExecutor(max_workers=exec_cfg.max_workers) as executor:
    #     #     futures = [
    #     #         executor.submit(sample)
    #     #         #for _ in range(int(exec_cfg.max_task_evals * 100))
    #     #         for _ in range(1)
    #     #     ]
    #     #     for future in as_completed(futures):
    #     #         future.result()
    #
    # except Exception as e:
    #     logger.error(f"Error: {e}")
    #     logger.error(traceback.format_exc())
    #     print(repr(e))

if __name__ == "__main__":
    main()