# from prompts.verify_model import VerifyModel
# import json
# vf = VerifyModel("./config.yaml")
#
#
# with open("./small.jsonl", "r") as f:
#     codes = f.readlines()
# for line in codes:
#     prompt = json.loads(line)[0]["user"]
#     vf_result = vf.obfuscate_result_verify(prompt)
#     print(vf_result)

def calculate_vuln_metrics(
        gpt5_vulns: list[dict],  # GPT-5 的漏洞列表（Ground Truth）
        small_model_vulns: list[dict],  # 小模型的漏洞列表
) -> dict:
    """
    核心函数：计算漏洞检测任务的关键指标
    返回字典：包含 TP、FP、FN、Precision、Recall、F1_Score
    """
    # 1. 初始化统计变量
    tp = 0  # 真阳性：小模型与 GPT-5 匹配的漏洞数
    fp = 0  # 假阳性：小模型检测到但 GPT-5 无匹配的漏洞数
    fn = 0  # 假阴性：GPT-5 有但小模型未检测到的漏洞数

    for i, gpt5_vuln in enumerate(gpt5_vulns):
        if gpt5_vulns[i]["vul"] == True and small_model_vulns[i]["vul"] == True:
            tp += 1
        if small_model_vulns[i]["vul"] == True and gpt5_vulns[i]["vul"] == False:
            fp += 1
        if gpt5_vulns[i]["vul"] == True and small_model_vulns[i]["vul"] == False:
            fn += 1

    # 4. 计算 Precision、Recall、F1 Score（处理分母为0的边界情况）
    # Precision = TP / (TP + FP)，无正例时为0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    # Recall = TP / (TP + FN)，无真实漏洞时为0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    # F1 = 2*(P*R)/(P+R)，P和R均为0时为0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # 5. 返回结果（保留4位小数，便于阅读）
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": round(precision, 4),
        "Recall": round(recall, 4),
        "F1_Score": round(f1, 4)
    }


# ------------------------------
# 示例：使用模拟数据测试代码
# ------------------------------
import json

if __name__ == "__main__":
    # 1. 模拟 GPT-5 的漏洞列表（Ground Truth）
    gpt5_ground_truth = []
    with open("../output/gpt5.jsonl", "r") as gptf:
        lines = gptf.readlines()
    for line in lines:
        ground_truth = {}
        data = json.loads(line)[0]
        prompt = data["user"]
        ground_truth["prompt"] = prompt
        if "chosen" in data:
            ground_truth["vul"] = True
        else:
            ground_truth["vul"] = False
        gpt5_ground_truth.append(ground_truth)


    small_ground_truth = []
    with open("../output/deepseekv3.2.jsonl", "r") as smallf:
        slines = smallf.readlines()

    for sline in slines:
        ground_truth = {}
        data = json.loads(sline)[0]
        # prompt = data["user"]
        # ground_truth["prompt"] = prompt
        ground_truth["vul"] = data["vul"]
        small_ground_truth.append(ground_truth)
    # 3. 调用函数计算指标（行号容忍度设为2）
    metrics_result = calculate_vuln_metrics(
        gpt5_vulns=gpt5_ground_truth,
        small_model_vulns=small_ground_truth,
    )

    # 4. 打印结果
    print("漏洞检测指标计算结果（以 GPT-5 为 Ground Truth）：")
    for key, value in metrics_result.items():
        print(f"{key}: {value}")