import json
import os


def generate_conversation_json(output_file="combined_conversations.jsonl"):
    """
    遍历当前目录下所有文件夹，读取其中的 deepseek-r1.json 文件，
    生成指定格式的对话JSON（每个条目为一轮对话）

    输出格式：
    [
      {"system": "你是一个人工智能助手。", "user": "xxx", "rejected": "xxx"},
      {"system": "你是一个人工智能助手。", "user": "xxx", "chosen": "xxx"},
      ...
    ]
    """
    combined_conversations = []
    current_dir = os.getcwd() + "/prevrun"
    print(f"正在扫描当前目录: {current_dir}")

    # 统计变量
    total_files = 0
    success_count = 0
    skip_count = 0
    error_count = 0

    # 遍历当前目录下所有文件夹
    for item in os.listdir(current_dir):
        item_path = os.path.join(current_dir, item)

        if os.path.isdir(item_path):
            json_file = os.path.join(item_path, "gpt5.json")

            if os.path.exists(json_file):
                total_files += 1
                print(f"\n正在处理：{json_file}")

                try:
                    # 读取JSON文件
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 遍历所有对话节点（根据原文件结构调整，这里沿用之前的nodes结构）
                    # 若原文件结构不同（如直接是对话列表），请修改以下遍历逻辑
                    for node_key, node_data in data.get('nodes', {}).items():
                        # 构建对话条目（system字段固定）
                        conversation = {
                            "system": "你是一个人工智能助手。"
                        }

                        # 1. 获取user内容（优先从原文件提取，无则用默认值）
                        # 可根据实际文件结构修改：比如 node_data.get('user_input') 等
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
                        conversation["prompt"] = text



                        # 2. 确定rejected/chosen字段（沿用之前的评分逻辑，可修改）
                        score = int(node_data.get('score', 0))
                        score_str = node_data.get('verify_result', '')
                        # 逻辑：5分设为rejected，其他设为chosen（可按需调整）
                        # if score == 5:
                        #     # rejected内容：优先从原文件提取，无则用评分字符串
                        #     conversation["rejected"] = score_str
                        # else:
                        #     # chosen内容：优先从原文件提取，无则用评分字符串
                        #     conversation["chosen"] = score_str
                        conversation["response"] = score_str
                        # 添加到结果列表
                        combined_conversations.append(conversation)
                        success_count += 1

                except json.JSONDecodeError:
                    print(f"❌ 无效JSON文件，已跳过")
                    error_count += 1
                except Exception as e:
                    print(f"❌ 处理失败：{str(e)}")
                    error_count += 1
            else:
                print(f"ℹ️  跳过文件夹 {item}：未找到 deepseek-r1.json")
                skip_count += 1

    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        for single in combined_conversations:
            json.dump(single, f, ensure_ascii=False)
            f.write("\n")

    # 输出统计报告
    print("\n" + "=" * 60)
    print(f"📊 处理完成！统计结果如下：")
    print(f"总扫描文件夹数：{len(os.listdir(current_dir))}")
    print(f"找到目标文件数：{total_files}")
    print(f"成功生成对话数：{success_count}")
    print(f"跳过文件夹数：{skip_count}")
    print(f"处理失败数：{error_count}")
    print(f"📁 结果文件路径：{os.path.abspath(output_file)}")
    print("=" * 60)


# 自定义配置说明（可直接在代码中修改）：
# 1. system字段内容：修改 conversation["system"] 的值
# 2. user字段来源：修改 node_data.get('user', "默认值") 中的键名和默认值
# 3. rejected/chosen逻辑：调整 score == 5 的判断条件
# 4. rejected/chosen内容：修改 node_data.get('字段名', 默认值)

if __name__ == "__main__":
    generate_conversation_json()