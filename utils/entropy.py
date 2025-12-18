import numpy as np
from typing import List, Tuple
import re
import json
from sentence_transformers import SentenceTransformer, util

# 句向量模型（初始化一次）
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

text1 = """
{
  "score": "评分5/5",
  "vulnerabilities": [
    {
      "position": "N/A",
      "type": "ssti",
      "description": "未发现可被利用的路径"
    }
  ],
  "reasoning_chain": [
    "Step 1: 读取代码结构，未发现可控输入路径。",
    "Step 2: 检查敏感操作，未发现系统调用或危险函数使用。",
    "Step 3: compute_port 函数返回固定端口，未引入攻击面。",
    "Step 4: debug_flag 始终为 False，不会暴露调试模式。",
    "Step 5: 综合评估，代码属于常规实现，无漏洞。"
  ]
}
"""

text2="""
{
  "score": "评分5/5",
  "vulnerabilities": [
    {
      "position": "N/A",
      "type": "xxs",
      "description": "未发现可被利用的路径"
    }
  ],
  "reasoning_chain": [
    "Step 1: 检查输入源，未发现外部可控参数参与危险函数。",
    "Step 2: 分析 Flask 环境配置，autoescape 默认为开启。",
    "Step 3: 监听地址 0.0.0.0 属于正常开发环境，不构成漏洞。",
    "Step 4: debug_flag 的计算方式保证其为 False。",
    "Step 5: 综合判断风险，未发现可利用漏洞。"
  ]
}

"""

text3="""
{
  "score": "评分5/5",
  "vulnerabilities": [
    {
      "position": "compute_port",
      "type": "LowRisk-Misconfiguration",
      "description": "端口计算逻辑依赖环境变量，若配置错误可能导致错误监听。"
    }
  ],
  "reasoning_chain": [
    "Step 1: 代码从环境变量 APP_PORT 解析端口，存在潜在配置错误风险。",
    "Step 2: _stage1_convert 与 _stage2_validate 的逻辑较为混乱，增加理解复杂度。",
    "Step 3: host 值构建方式非常规，可能影响可维护性。",
    "Step 4: 虽然上述点均不构成实际漏洞，但属于弱风险因素。",
    "Step 5: 最终未判断为恶意漏洞，评分为 5。"
  ]
}

"""
class VerifyModel:

    ####################################
    # 1. 解析结构化输出
    ####################################
    def parse_output_structure(self, text: str) -> Tuple[str, str]:
        """
        从模型输出中解析漏洞类型与推理链。
        例如模型输出格式：
        Type: XSS
        Reasoning: 该代码存在未转义输入...

        若解析失败，返回 ("UNKNOWN", text)
        """
        type_match = re.search(r"-\s*类型\s*[:：]\s*(.*)", text)
        if type_match:
            vuln_type = type_match.group(1).strip()
        else:
            vuln_type = "UNKNOWN"

        reasoning_match = re.search(r"3\.\s*推理依据\s*[:：](.*)", text, re.S)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
        else:
            # 若模型格式不同，则 fallback：提取第一个长段落作为推理
            blocks = text.split("\n\n")
            reasoning = blocks[-1].strip() if blocks else text

        return vuln_type, reasoning

    def parse_json_output(self, text: str):
        """
        输入：模型输出的 JSON 字符串
        输出：
            score: float（1~5）
            vuln_types: List[str]
            reasoning_steps: List[str]  # 所有漏洞的推理步骤 flatten 后合并
        """
        try:
            data = json.loads(text)
        except:
            return None, [], []  # 无法解析时当作异常输出处理

        # 1. 提取 score（格式 "评分X/5"）
        raw_score = data.get("score", "评分5/5")
        try:
            score_num = float(raw_score.replace("评分", "").replace("/5", "").strip())
        except:
            score_num = 5.0

        # 2. 提取漏洞类型
        vuln_types = []
        vulnerabilities = data.get("vulnerabilities", [])
        for v in vulnerabilities:
            vuln_types.append(v.get("type", "N/A"))

        # 3. 提取所有 reasoning_chain 为一个 flatten 列表
        reasoning_steps = []
        for v in vulnerabilities:
            chain = v.get("reasoning_chain", [])
            reasoning_steps.extend(chain)

        return score_num, vuln_types, reasoning_steps

    ####################################
    # 2. 类型熵（类别不一致 → 幻觉）
    ####################################
    def type_entropy(self, types):
        if not types:
            return 0.0
        unique, counts = np.unique(types, return_counts=True)
        probs = counts / len(types)
        entropy = -np.sum(probs * np.log(probs + 1e-9))
        return float(entropy)
    def reasoning_entropy(self, reasoning_steps):
        if len(reasoning_steps) < 2:
            return 0.0

        embeddings = embedding_model.encode(reasoning_steps, convert_to_tensor=True)
        distances = []

        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = util.cos_sim(embeddings[i], embeddings[j]).item()
                dist = 1 - sim
                distances.append(dist)

        return float(np.mean(distances))

    def hallucination_score(self, json_texts: list) -> float:
        """
        输入：多个模型输出 JSON（字符串列表）
        输出：幻觉熵分数
        """

        all_types = []
        all_reasoning = []

        # 解析每个输出
        for js in json_texts:
            score, vuln_types, reasoning_steps = self.parse_json_output(js)
            all_types.extend(vuln_types)
            all_reasoning.extend(reasoning_steps)

        # 计算两类熵
        H_type = self.type_entropy(all_types)
        H_reason = self.reasoning_entropy(all_reasoning)

        # 最终幻觉熵
        lam = 0.6  # 类型占 60% 权重
        H = lam * H_type + (1 - lam) * H_reason
        return float(H)




vm = VerifyModel()
texts = [text1, text2, text3]
hall_score = vm.hallucination_score(texts)
print(hall_score)