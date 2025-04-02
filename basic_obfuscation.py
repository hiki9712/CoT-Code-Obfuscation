
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml
import re
from openai import OpenAI
def load_yaml_config(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# Load configurations
config = load_yaml_config("config.yaml")


obfuscator_config = config['obfuscator']
reviewer_config = config['reviewer']

obfuscator_prompt = load_file(obfuscator_config['obfuscate']).format(
    origin_code=load_file("./CWE79_direct-use-of-jinja2/ori_code.py")
)
reviewer_prompt = load_file(reviewer_config['review'])

#Obfuscator and Reviewer Agents
obfuscator_client = OpenAI(
    base_url=obfuscator_config['base_url'],
    api_key=obfuscator_config['api_key'],
)

chat_completion = obfuscator_client.chat.completions.create(
    messages=[
        {
            "role":"user",
            "content":obfuscator_prompt,
        }
    ],
    model=obfuscator_config['model'],
    temperature=0.0,
)

print(chat_completion.choices[0].message.content)
obfuscate_code = re.compile(chat_completion.choices[0].message.content,)

reviewer_client = OpenAI(
    base_url=reviewer_config['base_url'],
    api_key=reviewer_config['api_key'],
)

chat_completion = reviewer_client.chat.completions.create(
    messages=[
        {
            "role":"user",
            "content":reviewer_prompt,
        }
    ],
    model=reviewer_config['model'],
    temperature=0.0,
)

print(chat_completion.choices[0].message.content)

