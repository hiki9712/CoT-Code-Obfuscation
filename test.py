import re

def extract_strings(text):
    # 使用正则表达式匹配<<<和>>>之间的内容，包括换行符
    pattern = r'<<<(.*?)>>>'
    # 使用re.DOTALL标志使.匹配包括换行符在内的所有字符
    matches = re.findall(pattern, text, flags=re.DOTALL)
    return matches

# 示例
text = """
这是一段示例文本，<<<第一个匹配内容>>>，
这里还有另一个<<<第二个
匹配内容（含换行）>>>，以及更多文字。
"""
result = extract_strings(text)
print(result)
# 输出: ['第一个匹配内容', '第二个\n匹配内容（含换行）']