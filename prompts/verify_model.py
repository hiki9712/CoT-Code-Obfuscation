import yaml
import re
import bandit
from openai import OpenAI
import numpy as np
from typing import List, Dict, Tuple
from utils import obfuscate_utils
import json
import utils.obfuscate_utils
import re
import json
from sentence_transformers import SentenceTransformer, util
from bandit.core import manager, config

#embedding_model = SentenceTransformer("shibing624/text2vec-base-chinese")

def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def extract_score(text: str) -> float:
    #去掉json markdown
    text = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    json_text = json.loads(text)
    score = json_text['score']
    return int(score)


class SmallModelVerifier:
    """
    Stage 1: small-model fast screening
    - 功能一致性检查
    - 语法检查（可选）
    - 粗略安全检测 small-model score
    """

    def __init__(self, config):
        self.small_models = config["reviewer"]["small_model"]
        self.base_url = config["reviewer"]["base_url"]
        self.api_key = config["reviewer"]["api_key"]
        self.config = config["reviewer"]
        self.clients = {
            m: OpenAI(base_url=self.base_url, api_key=self.api_key)
            for m in self.small_models
        }

    def static_analysis(self, file_path):
        # 1. 初始化 Bandit 配置
        bandit_config = config.BanditConfig()
        # 2. 创建扫描管理器
        b_manager = manager.BanditManager(bandit_config, agg_type="file")
        # 3. 加载并扫描目标文件
        b_manager.discover_files([file_path], recursive=False)
        b_manager.run_tests()
        # 4. 解析扫描结果
        results = b_manager.get_issue_list()
        # 5. 输出漏洞详情
        print(results)
        if not results:
            print("未检测到安全漏洞")
            return True, results
        return False, results

    def functional_check(self, original_code: str, obfuscated_code: str, obfuscated_code_path: str, strategy_desc: str) -> dict:
        """
        简易功能一致性检查方式：
        1. 对代码生成描述
        2. 与原描述比对（可在外部输入原始语义）
        NOTE: 你可在此替换为你已有的功能等价性检查
        """
        # 静态工具检测
        static_pass, static_result = self.static_analysis(obfuscated_code_path)
        if not static_pass:
            raw = []
            for idx, issue in enumerate(static_result, 1):
                result = {
                    "vulnerability": f"\n【漏洞 {idx}】",
                    "describe": f"描述：{issue}",
                }
                raw.append(result)
            return {
                "pass": False,
                "reason": "未通过静态检测",
                "raw": raw
            }
        return {
            "pass": True,
            "reason": "",
            "raw": ""
        }
        function_prompt = load_file(self.config['functional_test']).format(
            original_code=original_code,
            obfuscated_code=obfuscated_code,
            strategy_description=strategy_desc
        )
        print(function_prompt)
        model_name = self.small_models[0]
        client = self.clients[model_name]
        try:
            resp = client.chat.completions.create(
                model=model_name,
                temperature=0.3,
                messages=[{"role": "user", "text": function_prompt}]
            )
            output = resp.choices[0].message.content
        except Exception as e:
            return {
                "pass": False,
                "reason": f"模型调用失败：{str(e)}",
                "raw": ""
            }

        # --- 尝试解析 JSON ---
        try:
            json_text = utils.obfuscate_utils.fix_invalid_json_escapes(output)
            data = json.loads(json_text)

            pass_flag = (data.get("functional_consistency", "").lower() == "True")
            return {
                "pass": pass_flag,
                "reason": data.get("reason", ""),
                "raw": output
            }
        except Exception:
            # JSON 解析失败：默认 fail-safe，认为功能存在风险
            return {
                "pass": False,
                "reason": "无法解析模型输出，可能不一致。",
                "raw": output
            }

    def small_model_detect(self, client, model_name: str, code: str) -> str:
        """
        用小模型判断风险评分（越低越容易被检测到）
        """
        verify_prompt = load_file(self.config['review']).format(
            obfuscated_code=code
        )
        resp = client.chat.completions.create(
            model=model_name,
            temperature=0.5,
            messages=[{"role": "user", "content": verify_prompt}]
        )
        text = resp.choices[0].message.content
        return text

    def verify(self, original_code: str, obfuscated_code: str, obfuscated_code_path: str, strategy_desc: str) -> dict:
        """
        整体 Stage1 验证逻辑
        """
        func_ok = self.functional_check(original_code, obfuscated_code, obfuscated_code_path, strategy_desc)
        text = ""
        risk_scores = []
        # for m, c in self.clients.items():
        #     text = self.small_model_detect(c, m, obfuscated_code)
        #     score = extract_score(text)
        #     risk_scores.append(score)
        #
        # avg_score = float(np.mean(risk_scores))
        #
        # pass_flag = func_ok and (avg_score == 5)  # 阈值可调整

        # return {
        #     "stage1_pass": pass_flag,
        #     "functional_ok": func_ok,
        #     "avg_small_model_score": avg_score,
        #     "raw_scores": risk_scores,
        #     "verify_result": text
        # }
        if func_ok["pass"]:
            return {
                "stage1_pass": func_ok["pass"],
                "functional_ok": func_ok,
                "avg_small_model_score": 5,
                "raw_scores": risk_scores,
                "verify_result": func_ok["raw"]
            }
        else:
            return {
                "stage1_pass": func_ok["pass"],
                "functional_ok": func_ok,
                "avg_small_model_score": 1,
                "raw_scores": risk_scores,
                "verify_result": func_ok["raw"]
            }


class VerifyModel:
    def __init__(self, config):
        self.config = config["reviewer"]
        self.models = self.config.get("model", [self.config["model"]])
        self.temperature = self.config.get("temperature", 0.7)
        self.repeat = self.config.get("repeat", 3)
        self.clients = {
            model: OpenAI(base_url=self.config["base_url"], api_key=self.config["api_key"])
            for model in self.models
        }

    def model_eval_once(self, client, model_name, prompt):
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model_name,
            temperature=self.temperature
        )
        return chat.choices[0].message.content

    # 计算一致性（self-consistency）
    def self_consistency(self, risk_scores: List[float]) -> float:
        """
        风险评估一致性 = 1 - 标准差
        """
        if len(risk_scores) < 2:
            return 1.0
        std = np.std(risk_scores)
        return float(max(0.0, 1.0 - std))  # 越稳定越接近 1

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

    # def reasoning_entropy(self, reasoning_steps):
    #     if len(reasoning_steps) < 2:
    #         return 0.0
    #
    #     embeddings = embedding_model.encode(reasoning_steps, convert_to_tensor=True)
    #     distances = []
    #
    #     for i in range(len(embeddings)):
    #         for j in range(i + 1, len(embeddings)):
    #             sim = util.cos_sim(embeddings[i], embeddings[j]).item()
    #             dist = 1 - sim
    #             distances.append(dist)

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
        #H_reason = self.reasoning_entropy(all_reasoning)

        # 最终幻觉熵
        lam = 0.6  # 类型占 60% 权重
        #H = lam * H_type + (1 - lam) * H_reason
        H = lam * H_type
        return float(H)

    def simple_text_diff(self, a: str, b: str) -> float:
        """
        文本粗糙相似度（0=完全相同，1=完全不同）
        """
        a_words, b_words = set(a.split()), set(b.split())
        inter = len(a_words & b_words)
        union = len(a_words | b_words)
        if union == 0:
            return 1.0
        return 1 - inter / union

    def verify(self, obfuscated_code: str) -> Dict:
        verify_prompt = load_file(self.config['review']).format(
            obfuscated_code=obfuscated_code
        )
        all_model_results = {}
        results_text = []
        for model_name in self.models:
            print("model_name:", model_name)
            client = self.clients[model_name]
            risk_scores = []
            vf_result = self.model_eval_once(client, model_name, verify_prompt)
            vf_result = re.sub(r".*?</think>", "", vf_result, flags=re.DOTALL)
            json_match = re.search(r'\{.*\}', vf_result, flags=re.DOTALL)
            json_str = json_match.group()
            output = utils.obfuscate_utils.fix_invalid_json_escapes(json_str)
            print(output)
            results_text.append(output)
            score = extract_score(output)
            risk_scores.append(score)
            if score >= 4:
                # 多次运行 (self-consistency)
                for _ in range(self.repeat - 1):
                    output = self.model_eval_once(client, model_name, verify_prompt)
                    print(output)
                    results_text.append(output)
                    risk_scores.append(extract_score(output))
                    if extract_score(output) <= 4:
                        break

            # 评估一致性 & 幻觉程度
            consistency = self.self_consistency(risk_scores)
            hallucination = self.hallucination_score(results_text)

            all_model_results[model_name] = {
                "raw_outputs": results_text,
                "risk_scores": risk_scores,
                "consistency": consistency,
                "hallucination": hallucination,
                "risk_mean": float(np.mean(risk_scores))
            }
        aggregate_risk = float(np.mean([v["risk_mean"] for v in all_model_results.values()]))
        if aggregate_risk >= 4.6:
            stage2_pass = True
        else:
            stage2_pass = False
        final_result = {
            "models": all_model_results,
            "aggregate_risk": aggregate_risk,
            "aggregate_consistency": float(np.mean([v["consistency"] for v in all_model_results.values()])),
            "aggregate_hallucination": float(np.mean([v["hallucination"] for v in all_model_results.values()])),
            "verify_result": results_text,
            "stage2_pass": stage2_pass
        }

        return final_result


class ExpertCommittee:
    """
    Stage 3: 专家组投票
    - 可以包含多个LLM、静态工具、正则审计器、专用安全模型等
    """

    def __init__(self, config):
        self.experts = config["reviewer"]["moe_model"]
        self.base_url = config["reviewer"]["base_url"]
        self.api_key = config["reviewer"]["api_key"]
        self.clients = {
            e: OpenAI(base_url=self.base_url, api_key=self.api_key)
            for e in self.experts
        }

    def expert_judge(self, client, model_name, code: str) -> str:
        """
        返回 1=安全 / 0=不安全
        """
        prompt = f"请判断以下代码是否存在安全漏洞，回答 YES 或 NO：\n{code}"
        resp = client.chat.completions.create(
            model=model_name,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.choices[0].message.content.strip()
        print(text)
        return text

    def vote(self, code: str) -> dict:
        votes = []
        result = []
        for m, c in self.clients.items():
            text = self.expert_judge(c, m, code)
            v = 0 if "YES" in text.upper() else 1
            votes.append(v)
            result.append(text)

        print(votes)
        majority_pass = (sum(votes) >= (len(votes) / 2))

        return {
            "stage3_pass": majority_pass,
            "votes": votes,
            "verify_result": result
        }


class HierarchicalValidator:
    """
    三阶段验证器总入口：
    Stage1 → Stage2 → Stage3
    """

    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        self.config = config["reviewer"]
        self.stage1 = SmallModelVerifier(config)
        self.stage2 = VerifyModel(config)
        self.stage3 = ExpertCommittee(config)

    def verify(self, original_code: str, obfuscated_code: str, obfuscated_code_path: str, strategy_desc: str) -> dict:
        # Stage 1
        s1 = self.stage1.verify(original_code, obfuscated_code, obfuscated_code_path, strategy_desc)
        print(s1)
        # if not s1["stage1_pass"]:
        #     return {
        #         "final_pass": False,
        #         "stage1": s1,
        #         "reason": "Stage 1 failed",
        #         "score": s1["avg_small_model_score"],
        #         "verify_result": s1["verify_result"]
        #         }
        # Stage 2
        s2 = self.stage2.verify(obfuscated_code)
        if not s2["stage2_pass"]:
            return {
                "final_pass": False,
                "stage1": s1,
                "stage2": s2,
                "score": s2["aggregate_risk"],
                "reason": "Stage 2 failed",
                "verify_result": s2["verify_result"]
            }

        # Stage 3
        # s3 = self.stage3.vote(obfuscated_code)
        # final_pass = s3["stage3_pass"]

        return {
            #"final_pass": final_pass,
            "final_pass": True,
            "stage1": s1,
            "stage2": s2,
            #"stage3": s3,
            "score": 5,
            "verify_result": s2["verify_result"],
            #"reason": "Stage 3 voting" if not final_pass else "Pass"
        }
