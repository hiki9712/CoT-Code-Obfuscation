import yaml
import re
from openai import OpenAI


def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


class VerifyModel:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
             config = yaml.safe_load(f)
        self.config = config["reviewer"]
        self.temperature = 0.8

    def obfuscate_result_verify(self, obfuscated_code):
        obfuscator_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        verify_prompt = load_file(self.config['review']).format(
            obfuscated_code=obfuscated_code
        )
        print(verify_prompt)
        chat_completion = obfuscator_client.chat.completions.create(
            messages=[
                {
                    "role":"user",
                    "content":verify_prompt
                }
            ],
            model=self.config['model'],
            temperature=self.temperature
        )
        return chat_completion.choices[0].message.content