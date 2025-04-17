import yaml
import re
from openai import OpenAI


def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


class ObfuscationModel:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
             config = yaml.safe_load(f)
        self.config = config["obfuscator"]
        self.temperature = 0.8

    def obfuscate_result_generate(self, vul_type, obfuscation_policy, obfuscation_steps, failed_policy):
        obfuscator_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        obfuscation_prompt = load_file(self.config['obfuscate']).format(
            origin_code=load_file(vul_type + "/ori_code.py").format(),
            obfuscation_policy=obfuscation_policy.format(),
            obfuscation_steps=obfuscation_steps.format(),
            failed_policy=failed_policy.format(),
        )
        print("obfuscation prompt")
        print(obfuscation_prompt)
        print("__________________________________________________________________")
        chat_completion = obfuscator_client.chat.completions.create(
            messages=[
                {
                    "role":"user",
                    "content":obfuscation_prompt
                }
            ],
            model=self.config['model'],
            temperature=self.temperature
        )
        return chat_completion.choices[0].message.content

    def reflection_result_generate(self, verify_result):
        return