# This file is adapted from https://github.com/jennyzzt/dgm.

from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-4.1-mini",
    input="请生成一个 Python 函数，用来判断一个数是否为质数"
)

# 获取模型返回的文本
result = response.output_text
print(result)
