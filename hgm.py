import os
import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import numpy as np
from tree import Node  # 复用HGM中的树节点结构
import hgm_utils  # 复用HGM的工具类（节点管理、元数据记录等）

# 混淆策略定义（可根据需求扩展）
OBFUSCATION_STRATEGIES = {
    "var_rename": {"enabled": [True, False], "intensity": [1, 2, 3]},  # 变量名混淆（强度1-3）
    "control_flow_flattening": {"enabled": [True, False], "branches": [5, 10, 15]},  # 控制流平坦化（分支数）
    "constant_encryption": {"enabled": [True, False], "algorithm": ["xor", "aes", "rsa"]},  # 常量加密算法
    "redundant_code": {"enabled": [True, False], "ratio": [0.1, 0.3, 0.5]}  # 冗余代码插入比例
}

# 评估指标权重（可根据业务需求调整）
METRIC_WEIGHTS = {
    "obfuscation_strength": 0.4,  # 混淆强度（越高越好）
    "performance_overhead": -0.3,  # 性能损耗（越低越好，权重为负）
    "anti_reverse": 0.3  # 抗逆向能力（越高越好）
}


class ObfuscationNode(Node):
    """混淆策略树节点，继承HGM的Node类"""

    def __init__(self, commit_id, parent_id=None, strategy=None):
        super().__init__(commit_id, parent_id)
        self.strategy = strategy or self._random_strategy()  # 节点对应的混淆策略组合
        self.metrics = {}  # 评估指标：混淆强度、性能损耗、抗逆向能力
        self.utility_measures = []  # 用于HGM采样的效用值（整合多指标）

    def _random_strategy(self):
        """生成随机初始策略（父节点为None时调用）"""
        strategy = {}
        for name, params in OBFUSCATION_STRATEGIES.items():
            strategy[name] = {k: random.choice(v) for k, v in params.items()}
        return strategy

    def calculate_utility(self):
        """根据评估指标计算效用值（用于HGM的汤普森采样）"""
        if not self.metrics:
            return 0.0
        # 加权求和计算综合效用
        utility = sum(
            self.metrics[metric] * weight
            for metric, weight in METRIC_WEIGHTS.items()
        )
        # 标准化到[0,1]区间
        return (utility + 1) / 2  # 假设原始值范围为[-1,1]


def evaluate_obfuscation_strategy(strategy, code_path):
    """评估混淆策略效果（核心评估函数）"""
    # 1. 应用混淆策略到代码
    obfuscated_code = apply_strategy(code_path, strategy)

    # 2. 计算混淆强度（示例：基于AST节点变化率）
    origin_ast_size = count_ast_nodes(code_path)
    obfuscated_ast_size = count_ast_nodes(obfuscated_code)
    strength = min(1.0, (obfuscated_ast_size - origin_ast_size) / origin_ast_size)

    # 3. 计算性能损耗（示例：执行时间变化率）
    origin_time = measure_execution_time(code_path)
    obfuscated_time = measure_execution_time(obfuscated_code)
    performance = min(1.0, (obfuscated_time - origin_time) / origin_time)

    # 4. 计算抗逆向能力（示例：逆向工具解析成功率）
    reverse_success_rate = test_anti_reverse(obfuscated_code)
    anti_reverse = 1.0 - reverse_success_rate  # 成功率越低，抗逆向能力越高

    # 标准化指标到[-1,1]或[0,1]
    return {
        "obfuscation_strength": strength,
        "performance_overhead": performance,
        "anti_reverse": anti_reverse
    }


def apply_strategy(code_path, strategy):
    """应用混淆策略到代码（简化示例）"""
    with open(code_path, "r") as f:
        code = f.read()

    # 变量名混淆示例
    if strategy["var_rename"]["enabled"]:
        code = rename_variables(code, intensity=strategy["var_rename"]["intensity"])

    # 控制流平坦化示例
    if strategy["control_flow_flattening"]["enabled"]:
        code = flatten_control_flow(code, branches=strategy["control_flow_flattening"]["branches"])

    # 其他策略类似...
    return code


def expand_node(parent_node):
    """扩展节点生成子节点（基于父节点策略微调）"""
    child_strategy = parent_node.strategy.copy()
    # 随机选择一个策略进行微调（模拟策略优化）
    strategy_name = random.choice(list(OBFUSCATION_STRATEGIES.keys()))
    param_name = random.choice(list(OBFUSCATION_STRATEGIES[strategy_name].keys()))
    # 从可选参数中选择新值（不重复原参数）
    current_value = child_strategy[strategy_name][param_name]
    possible_values = [v for v in OBFUSCATION_STRATEGIES[strategy_name][param_name] if v != current_value]
    if possible_values:
        child_strategy[strategy_name][param_name] = random.choice(possible_values)
    # 生成子节点
    child_commit_id = f"obf_{parent_node.commit_id}_{random.randint(1000, 9999)}"
    return ObfuscationNode(child_commit_id, parent_id=parent_node.id, strategy=child_strategy)


def hgm_obfuscation_optimize(initial_code_path, max_evals=100, max_workers=5):
    """基于HGM的混淆策略树优化主函数"""
    # 初始化HGM环境
    output_dir = "./obfuscation_hgm_output"
    os.makedirs(output_dir, exist_ok=True)
    hgm_utils.init(output_dir=output_dir, total_tasks=[initial_code_path])

    # 创建根节点（初始策略）
    root = ObfuscationNode(commit_id="initial")
    hgm_utils.nodes[root.id] = root

    # 评估根节点
    root.metrics = evaluate_obfuscation_strategy(root.strategy, initial_code_path)
    root.utility_measures = [root.calculate_utility()]

    submitted_tasks = defaultdict(set)  # 记录节点已评估的任务
    lock = threading.Lock()

    def ts_sample(nodes):
        """汤普森采样选择最优节点（复用HGM核心逻辑）"""
        evals = [node.utility_measures for node in nodes]
        alphas = [1 + np.sum(e) for e in evals]
        betas = [1 + len(e) - np.sum(e) for e in evals]
        thetas = np.random.beta(alphas, betas)
        return nodes[np.argmax(thetas)]

    def sample_and_evaluate():
        """采样节点并评估（HGM核心循环）"""
        nonlocal root
        with lock:
            # 筛选可评估的节点（未完成所有任务）
            valid_nodes = [n for n in hgm_utils.nodes.values() if len(submitted_tasks[n.id]) < 1]
            if not valid_nodes:
                return
            selected_node = ts_sample(valid_nodes)
            submitted_tasks[selected_node.id].add(initial_code_path)

        # 评估选中的节点
        metrics = evaluate_obfuscation_strategy(selected_node.strategy, initial_code_path)
        with lock:
            selected_node.metrics = metrics
            selected_node.utility_measures.append(selected_node.calculate_utility())
            hgm_utils.n_task_evals += 1
            # 保存元数据
            hgm_utils.update_metadata(output_dir, hgm_utils.n_task_evals)

    def expand():
        """扩展节点生成新策略"""
        with lock:
            # 选择效用最高的节点进行扩展
            valid_nodes = [n for n in hgm_utils.nodes.values() if n.utility_measures]
            if not valid_nodes:
                return
            parent_node = ts_sample(valid_nodes)
            child_node = expand_node(parent_node)
            hgm_utils.nodes[child_node.id] = child_node
            parent_node.add_child(child_node)
            hgm_utils.update_metadata(output_dir, hgm_utils.n_task_evals)

    # 启动HGM主循环
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        while hgm_utils.n_task_evals < max_evals:
            # 平衡扩展与评估：每评估3次扩展1次
            if hgm_utils.n_task_evals % 3 == 0:
                futures.append(executor.submit(expand))
            else:
                futures.append(executor.submit(sample_and_evaluate))
            # 等待部分任务完成，避免任务堆积
            if len(futures) >= max_workers * 2:
                for future in as_completed(futures[:max_workers]):
                    future.result()
                futures = futures[max_workers:]

    # 返回最优策略
    best_node = max(hgm_utils.nodes.values(), key=lambda n: np.mean(n.utility_measures))
    return best_node.strategy


# 以下为辅助函数（实际使用需根据语言和工具实现）
def count_ast_nodes(code_path):
    """统计AST节点数量（示例）"""
    # 实际实现需用AST解析库（如Python的ast模块）
    return len(code_path.splitlines())  # 简化模拟


def measure_execution_time(code_path):
    """测量代码执行时间（示例）"""
    # 实际实现需执行代码并计时
    return random.uniform(0.1, 1.0)  # 简化模拟


def test_anti_reverse(obfuscated_code):
    """测试抗逆向能力（示例）"""
    # 实际实现需集成逆向工具（如IDA、Ghidra）的解析结果
    return random.uniform(0.1, 0.8)  # 简化模拟


def rename_variables(code, intensity):
    """变量名混淆实现（示例）"""
    # 实际实现需替换变量名为无意义字符串
    return code  # 简化模拟


def flatten_control_flow(code, branches):
    """控制流平坦化实现（示例）"""
    # 实际实现需插入跳转和中间块
    return code  # 简化模拟


if __name__ == "__main__":
    # 示例：优化指定代码的混淆策略
    best_strategy = hgm_obfuscation_optimize(
        initial_code_path="./ori.py",
        max_evals=50,
        max_workers=3
    )
    print("最优混淆策略：")
    print(json.dumps(best_strategy, indent=2))