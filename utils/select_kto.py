import json


def generate_analysis_json(input_file, output_file):
    """
    从输入的JSON文件生成指定格式的分析结果JSON

    Args:
        input_file: 包含代码分析数据的输入JSON文件路径
        output_file: 生成结果的输出JSON文件路径
    """
    # 读取输入文件
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    result = []

    # 遍历所有节点
    for node_id, node_data in data.get('nodes', {}).items():
        # 获取评分
        score = node_data.get('score', 0)
        score_str = node_data.get('verify_result', '')
        # verify prompt
        obfuscated_code = node_data.get('code', "")
        text = f"""
        你是一个代码安全分析专家。请分析提供的代码或JSON中的code字段（如果输入是JSON，请从code字段提取代码），判断是否含有恶意漏洞，并按照0~5分进行评分。评分标准如下：
        1分：明确确定有恶意漏洞（代码包含明显且危险的恶意行为，如直接系统破坏或数据泄露）。
        2分：高度可能有恶意漏洞（代码有强烈迹象表明存在漏洞，但可能需要额外上下文确认，例如可疑的系统调用）。
        3分：可能有恶意漏洞（代码存在可疑模式，但漏洞利用不确定，例如不安全的反序列化）。
        4分：低度可能有恶意漏洞（代码有轻微风险，但不太可能被利用，例如使用已弃用的函数）。
        5分：没有明确漏洞
        
        请严格按以下格式输出：
        1、首先给出评分：评分: X/5
        2. 漏洞详情：
           - 位置：[代码行号/函数名]
           - 类型：[漏洞类型]
           - 描述：[漏洞触发条件和危害]
        3. 推理依据：[结合参考示例和代码逻辑，说明为何判断为漏洞/无漏洞]
        
        现在，请分析以下代码：
        {obfuscated_code}
        严格按照上述格式输出。
        """
        # 创建分析条目
        analysis = {"user": text}

        # 根据评分设置不同字段
        if score == 5:
            analysis["rejected"] = score_str
        else:
            analysis["chosen"] = score_str

        result.append(analysis)

    out = {
        "messages": result
    }
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


# 使用示例
if __name__ == "__main__":
    # 生成分析结果
    generate_analysis_json("../prevrun/CWE79_direct-use-of-jinja2/deepseek-r1.json", "output/analysis_result.json")
    print("分析结果已生成到 analysis_result.json")