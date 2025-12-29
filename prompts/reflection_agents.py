# ===============================
# Hybrid Workflow + Agent Demo
# Reflection → Belief → Prior → Strategy
# LangGraph + OpenAI (new SDK)
# ===============================

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from openai import OpenAI
import json
import re

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

# --------------------------------
# 0. OpenAI Client (NEW SDK)
# --------------------------------
# 使用环境变量：
# export OPENAI_API_KEY=sk-xxxx
# export OPENAI_BASE_URL=https://api.openai.com/v1
client = OpenAI()

# --------------------------------
# 1. Agent State
# --------------------------------
@dataclass
class CoTState:
    # environment
    code: str
    original_code: str

    # verifier output
    verifier_result: str

    # history
    lineage: List[str] = field(default_factory=list)

    # cognition
    beliefs: Optional[Dict[str, Any]] = None
    policy_prior: Optional[Dict[str, Any]] = None

    # decision
    next_action: Optional[str] = None


# --------------------------------
# 2. Verifier (MOCK, 可直接换成你真实的)
# --------------------------------
def mock_verifier(state: CoTState):
    """
    接口与 HierarchicalValidator.verify 对齐
    """
    result = state.verifier_result
    return {"verifier_result": result}


# --------------------------------
# 3. Reflection Agent (LLM)
# --------------------------------
def reflection_node(state: CoTState):
    prompt = f"""
You are a security reflection agent.

Given the verifier feedback, infer:
1. outcome: success or failure
2. failure_type: stable_reasoning / detector_triggered / hallucination_sensitive
3. detector_assumptions: implicit assumptions relied on by the detector

Verifier feedback:
{json.dumps(state.verifier_result, indent=2)}

Return STRICT JSON:
{{
  "outcome": "...",
  "failure_type": "...",
  "detector_assumptions": ["..."]
}}
"""
    resp = client.chat.completions.create(
        model="deepseek-r1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )

    text = resp.choices[0].message.content
    json_match = re.search(r'\{.*\}', text, flags=re.DOTALL)
    json_str = json_match.group()
    json_str = fix_invalid_json_escapes(json_str)
    beliefs = json.loads(json_str)
    return {"beliefs": beliefs}


# --------------------------------
# 4. Belief → Policy Prior
# --------------------------------
def belief_to_prior_node(state: CoTState):
    belief = state.beliefs

    prior = {
        "prefer_actions": [],
        "avoid_actions": [],
        "focus_obfuscation": [],
        "exploration_bias": 0.3
    }

    if belief["outcome"] == "success":
        prior["exploration_bias"] = 0.1
        prior["prefer_actions"] = state.lineage[-1:]
        return {"policy_prior": prior}

    if belief["failure_type"] == "stable_reasoning":
        prior["prefer_actions"].append("opaque_predicate")

    if belief["failure_type"] == "detector_triggered":
        prior["focus_obfuscation"].append("assumption_violation")

    for a in belief.get("detector_assumptions", []):
        if "import" in a:
            prior["prefer_actions"].append("api_wrapping")

    return {"policy_prior": prior}


# --------------------------------
# 5. Strategy Agent (LLM)
# --------------------------------
def strategy_agent(state: CoTState):
    prompt = f"""
You are an attack strategy planner.

Policy prior:
{json.dumps(state.policy_prior, indent=2)}

Previous actions:
{state.lineage}

Choose ONE next strategy from:
- opaque_predicate
- api_wrapping
- control_flow_flattening
- random_exploration

Return ONLY the strategy name.
"""

    resp = client.chat.completions.create(
        model="deepseek-r1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    action = resp.choices[0].message.content.strip()
    print("action", action)
    return {
        "next_action": action,
        "lineage": state.lineage + [action]
    }


# --------------------------------
# 6. Apply Action (mock 实现)
# --------------------------------
def apply_action(state: CoTState):
    new_code = state.code + f"\n# Applied action: {state.next_action}"
    return {"code": new_code}


# --------------------------------
# 7. LangGraph Construction
# --------------------------------
graph = StateGraph(CoTState)

graph.add_node("verifier", mock_verifier)
graph.add_node("reflect", reflection_node)
graph.add_node("prior", belief_to_prior_node)
graph.add_node("strategy", strategy_agent)
graph.add_node("act", apply_action)

graph.set_entry_point("verifier")

graph.add_edge("verifier", "reflect")
graph.add_edge("reflect", "prior")
graph.add_edge("prior", "strategy")
graph.add_edge("strategy", "act")
graph.add_edge("act", END)

agent = graph.compile()


def run_reflection_agents(
    verifier_feedback: str,
    code: str,
    original_code: str,
    max_reflection_steps: int = 3,
) -> dict:
    init_state = CoTState(
        code=code,
        original_code=original_code,
        verifier_result=verifier_feedback
    )


    final_state = init_state
    for step in agent.stream(init_state):
        print(step)
        for _, update in step.items():
            for k, v in update.items():
                setattr(final_state, k, v)

    print("\n========== FINAL STATE ==========\n")
    print("Chosen action:", final_state.next_action)
    print("Lineage:", final_state.lineage)
    print("Final code:\n", final_state.code)

    return final_state.beliefs

# --------------------------------
# 8. Run + Stream Trace
# --------------------------------
# if __name__ == "__main__":
#     init_state = CoTState(
#         code="import importlib\nx = importlib.import_module('os')",
#         original_code="import importlib\nx = importlib.import_module('os')"
#     )
#
#     print("\n========== AGENT STREAM ==========\n")
#
#     final_state = init_state
#     for step in agent.stream(init_state):
#         print(step)
#         for _, update in step.items():
#             for k, v in update.items():
#                 setattr(final_state, k, v)
#
#     print("\n========== FINAL STATE ==========\n")
#     print("Chosen action:", final_state.next_action)
#     print("Lineage:", final_state.lineage)
#     print("Final code:\n", final_state.code)
