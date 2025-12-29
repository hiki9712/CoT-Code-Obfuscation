import re
import shutil
import argparse
import json
import os
import numpy as np
import datetime
import threading
from config import load_config
from collections import defaultdict

from utils import obfuscate_utils
from prompts.obfuscation_model import ObfuscationModel
from utils.tree import Node
from prompts.reflection_agents import run_reflection_agents
global config_path




def update_metadata(output_dir, prevrun_dir, node):
    print(output_dir)
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
        json.dump(metadata, f, indent=2, ensure_ascii=False,)
    # json.dump(
    #     obfuscate_utils.init_evaluated_tasks,
    #     open(os.path.join(output_dir, "init_evaluated_tasks.json"), "w"),
    # )


def get_node_by_node_id(node_id):
    """
    通过node_id查找节点信息
    """
    if not hasattr(obfuscate_utils, 'nodes'):
        print("节点树未初始化")
        return None

    for _, node in obfuscate_utils.nodes.items():
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
        run_id="initial",
        timeout=3600
):
    print(f"Previous run directory: {prevrun_dir}")
    # 创建必要的目录
    if not os.path.exists(prevrun_dir):
        os.makedirs(prevrun_dir)

    # 初始化节点计数器（如果不存在）
    if not hasattr(obfuscate_utils, 'node_counter'):
        obfuscate_utils.node_counter = 0

    # 检查是否存在之前的运行结果
    prevrun_metadata_path = os.path.join(prevrun_dir, "metadata.json") if prevrun_dir else None

    # 初始化节点树结构
    nodes = {}
    submitted_ids = defaultdict(set)

    # 如果没有之前的运行结果，进行初始验证
    if not prevrun_dir or not os.path.exists(prevrun_metadata_path):
        print("No previous run found, performing initial verification...")

        # 执行初始代码验证
        verify_result, code, assumptions = obfuscate_utils.eval_code(
            node_id="initial",
            init_code_path=initial_code_path,
            config=config_path
        )
        os.makedirs(output_dir + f"/{run_id}", exist_ok=True)
        with open(output_dir + f"/{run_id}" + "/verify_result.txt", 'w', encoding='utf-8') as f:
            f.write(str(verify_result))  # 写入字符串
        score = verify_result["score"]
        verify_text = "\n".join(verify_result["verify_result"])

        # 创建初始节点
        initial_node = Node(node_id="initial", verify_result=verify_text, score=score, code=code, ori_code=code)

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
            json.dump(metadata, f, indent=2, ensure_ascii=False,)
        # 保存assumptions
        assumptions_path = os.path.join(prevrun_dir, "assumptions.txt")
        print(assumptions)
        print(type(assumptions))
        assumptions_dict = assumptions["detector_assumptions"]
        with open(assumptions_path, 'w+') as assumptions_file:
            for assumption_detail in assumptions_dict:
                assumptions_file.write(assumption_detail+"\n")
        print(f"Initial verification completed. Results saved to {metadata_path}")

    else:
        print(f"Loading previous run results from {prevrun_metadata_path}")

        # 加载之前的metadata
        with open(prevrun_metadata_path, 'r') as f:
            prev_metadata = json.load(f)
        score = 0
        # 恢复节点计数器
        obfuscate_utils.node_counter = prev_metadata.get("node_counter", 0)

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

    # 将节点树保存到obfuscate_utils中，以便其他函数访问
    obfuscate_utils.nodes = nodes
    print(f"Initialization completed. Total nodes: {len(nodes)}")
    return submitted_ids, int(score)


# 添加一个辅助函数来更新和保存节点树
def update_node_tree(output_dir, new_node, parent_node=None, submitted_ids=None):
    """
    更新节点树并保存到metadata.json
    """
    # 确保obfuscate_utils.nodes存在
    if not hasattr(obfuscate_utils, 'nodes'):
        obfuscate_utils.nodes = {}

    # 分配节点ID
    if not hasattr(new_node, 'id') or not new_node.id:
        obfuscate_utils.node_counter += 1
        new_node.id = f"node_{obfuscate_utils.node_counter}"

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
    obfuscate_utils.nodes[new_node.id] = new_node

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
            for node_id, node in obfuscate_utils.nodes.items()
        },
        "submitted_ids": {node_id: list(task_set) for node_id, task_set in
                          submitted_ids.items()} if submitted_ids else {},
        "node_counter": obfuscate_utils.node_counter,
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
    init_id = run_id
    output_dir = os.path.abspath(os.path.join("./output", run_id))
    os.makedirs(output_dir, exist_ok=True)
    print(f"Working directory: {os.getcwd()}")
    print(f"Output directory: {output_dir}")
    print(f"Output directory exists: {os.path.exists(output_dir)}")
    cwe_type = args.cwe_type if args.cwe_type is not None else "CWE79_direct-use-of-jinja2"
    prevrun_dir = f"./prevrun/{cwe_type}"
    submitted_ids, score = initialize_run(
        output_dir=output_dir,
        initial_code_path=f"./vulncode/{cwe_type}/ori_code.txt",
        prevrun_dir=prevrun_dir,
        config_path=config_path,
        run_id=run_id
    )

    node_info = get_node_by_node_id("initial")

    def TS_sample(evals, nodes):
        alphas = [1 + np.sum(de)/5 for de in evals]
        betas = [1 + len(de) - np.sum(de)/5 for de in evals]
        if opt_cfg.cool_down:
            alphas = np.array(alphas) * (
                10000
                if exec_cfg.max_task_evals == obfuscate_utils.n_task_evals
                else exec_cfg.max_task_evals ** opt_cfg.beta
                     / (exec_cfg.max_task_evals - obfuscate_utils.n_task_evals) ** opt_cfg.beta
            )
            betas = np.array(betas) * (
                10000
                if exec_cfg.max_task_evals == obfuscate_utils.n_task_evals
                else exec_cfg.max_task_evals ** opt_cfg.beta
                     / (exec_cfg.max_task_evals - obfuscate_utils.n_task_evals) ** opt_cfg.beta
            )
        thetas = np.random.beta(alphas, betas)
        return np.argmax(thetas)

    n_pending_expands = 0
    n_pending_measures = 0
    lock = threading.Lock()

    def expand(expand_id):
        with lock:
            nodes = [
                node
                for node in obfuscate_utils.nodes.values()
                if np.isfinite(node.score) and node.score >= 0
            ]
            descendant_evals = [
                node.get_descendant_evals()
                for node in nodes
            ]
            selected_node = nodes[TS_sample(descendant_evals, nodes)]
        child_node_strategy = obfuscate_utils.sample_child(
            selected_node,
            output_dir,
            init_id,
            config=config_path,
            expand_id=expand_id,
            prevrun_dir=prevrun_dir
        )
        print(child_node_strategy)
        score = 0
        if child_node_strategy != "failed":
            #ob = ObfuscationModel("./config.yaml")
            # ob = ObfuscationModel(config_path)
            # ob_result = ob.obfuscation_result_generate(selected_node.code, child_node_strategy)
            # print(ob_result)
            # #去除<think></think>标签内容
            # ob_result = re.sub(r".*?</think>", "", ob_result, flags=re.DOTALL)
            # json_match = re.search(r'\{.*\}', ob_result, flags=re.DOTALL)
            # json_str = json_match.group()
            # json_str = obfuscate_utils.fix_invalid_json_escapes(json_str)
            # code = json.loads(json_str)["code"]
            json_match = re.search(r'\{.*\}', child_node_strategy, flags=re.DOTALL)
            json_str = json_match.group()
            json_str = obfuscate_utils.fix_invalid_json_escapes(json_str)
            code = json.loads(json_str)["code_transform_result"]
            print("----------------------------")
            print(code)
            print("----------------------------")
            #origin_code = obfuscate_utils.get_metadata(prevrun_dir)["nodes"][selected_node.pa]
            os.makedirs(output_dir + f"/{expand_id}", exist_ok=True)
            with open(output_dir + f"/{expand_id}" + "/obfuscate_result.txt", 'w', encoding='utf-8') as f:
                f.write(code)  # 写入字符串
            code_path = output_dir + f"/{expand_id}" + "/obfuscate_result.txt"
            #检测
            verify_result, assumptions = obfuscate_utils.eval_code(node_id=run_id, obfuscated_code=code,
                                                      obfuscated_code_path=code_path, origin_code=selected_node.code,
                                                      config=config_path, strategy=child_node_strategy)
            print(verify_result)

            ### let me reflection ###
            # run_reflection_agents(verify_result, code, selected_node.code)
            assumptions_path = os.path.join(prevrun_dir, "assumptions.txt")
            assumptions_dict = assumptions["detector_assumptions"]
            with open(assumptions_path, 'a+') as assumptions_file:
                for assumption_detail in assumptions_dict:
                    assumptions_file.write(assumption_detail + "\n")

            with open(output_dir + f"/{expand_id}" + "/verify_result.txt", 'w', encoding='utf-8') as f:
                verify_text = "\n".join(verify_result["verify_result"])
                f.write(verify_text)  # 写入字符串
            score = verify_result["score"]
            if score == 5:
                testcase_dir = os.path.join("./TestCases", cwe_type, expand_id)
                os.makedirs(testcase_dir, exist_ok=True)
                with open(os.path.join(testcase_dir, "obfuscate_result.py"), 'w', encoding='utf-8') as f:
                    f.write(code)
            print("Verification score:", score)
            verify_text = "\n".join(verify_result["verify_result"])
            with lock:
                new_node = Node(node_id=run_id, parent_id=selected_node.node_id, strategy=child_node_strategy,
                                score=score, verify_result=verify_text, code=code, ori_code=selected_node.code)
                selected_node.child_ids.append(
                    new_node
                )
                update_metadata(output_dir, prevrun_dir, new_node)
        return score

    round = 0
    while score != 5:
        run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        expand_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        score = expand(expand_id)
        round += 1
        if round > 10:
            break

if __name__ == "__main__":
    main()