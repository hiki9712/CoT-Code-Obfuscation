import yaml
import re
from openai import OpenAI
import numpy as np
from typing import List, Dict
import json
import utils.obfuscate_utils


def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


def extract_score(text: str) -> float:
    score_match = re.search(r'评分:\s*(\d)/5', text)
    if not score_match:
        raise ValueError("Can not find score.")
    score = int(score_match.group(1))
    print("Verification score:", score)
    return score


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

    def functional_check(self, original_code: str, obfuscated_code: str, strategy_desc: str) -> dict:
        """
        简易功能一致性检查方式：
        1. 对代码生成描述
        2. 与原描述比对（可在外部输入原始语义）
        NOTE: 你可在此替换为你已有的功能等价性检查
        """
        function_prompt = load_file(self.config['functional_test']).format(
            original_code=original_code,
            obfuscated_code=obfuscated_code,
            strategy_description=strategy_desc
        )
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
    def verify(self, original_code: str, obfuscated_code: str, strategy_desc: str) -> dict:
        """
        整体 Stage1 验证逻辑
        """
        func_ok = self.functional_check(original_code, obfuscated_code, strategy_desc)
        text = ""
        risk_scores = []
        for m, c in self.clients.items():
            text = self.small_model_detect(c, m, obfuscated_code)
            score = extract_score(text)
            risk_scores.append(score)

        avg_score = float(np.mean(risk_scores))

        pass_flag = func_ok and (avg_score == 5)  # 阈值可调整

        return {
            "stage1_pass": pass_flag,
            "functional_ok": func_ok,
            "avg_small_model_score": avg_score * 0.2,
            "raw_scores": risk_scores,
            "verify_result": text
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

    def hallucination_score(self, risk_scores: List[float], texts: List[str]) -> float:
        """
        简单版幻觉估计：
        - 风险波动越大 → 幻觉越高
        - 输出文本差异越大 → 幻觉越高
        """
        var_component = np.var(risk_scores)

        # 用 edit distance 简化替代，更轻量
        text_diffs = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                diff = self.simple_text_diff(texts[i], texts[j])
                text_diffs.append(diff)
        text_component = np.mean(text_diffs) if text_diffs else 0

        # 综合权重
        return float(0.5 * var_component + 0.5 * text_component)

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
            output = self.model_eval_once(client, model_name, verify_prompt)
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

            # 评估一致性 & 幻觉程度
            consistency = self.self_consistency(risk_scores)
            hallucination = self.hallucination_score(risk_scores, results_text)

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

        print("=== Validator Summary ===")
        print(final_result)
        print("=========================")

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

    def verify(self, original_code: str, obfuscated_code: str, strategy_desc: str) -> dict:
        # Stage 1
        # s1 = self.stage1.verify(original_code, obfuscated_code, strategy_desc)
        # if not s1["stage1_pass"]:
        #     return {
        #         "final_pass": False,
        #         "stage1": s1,
        #         "reason": "Stage 1 failed",
        #         "score": s1["avg_small_model_score"],
        #         "verify_result": s1["verify_result"]
        #     }

        # Stage 2
        s2 = self.stage2.verify(obfuscated_code)
        if not s2["stage2_pass"]:
            return {
                "final_pass": False,
                #"stage1": s1,
                "stage2": s2,
                "score": s2["aggregate_risk"],
                "reason": "Stage 2 failed",
                "verify_result": s2["verify_result"]
            }

        # Stage 3
        s3 = self.stage3.vote(obfuscated_code)
        final_pass = s3["stage3_pass"]

        return {
            "final_pass": final_pass,
            #"stage1": s1,
            "stage2": s2,
            "stage3": s3,
            "score": 5,
            "verify_result": s3["verify_result"],
            "reason": "Stage 3 voting" if not final_pass else "Pass"
        }
