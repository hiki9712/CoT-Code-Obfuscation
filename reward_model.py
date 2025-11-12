import yaml
import re
from openai import OpenAI


def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


class RewardModel:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
             config = yaml.safe_load(f)
        self.config = config["reward"]
        self.temperature = 0

    def get_reward(self, before_obfuscation, after_obfuscation):
        obfuscator_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        reward_prompt = load_file(self.config['reward']).format(
            before_obfuscation=before_obfuscation,
            after_obfuscation=after_obfuscation
        )
        print("reward prompt")
        print(reward_prompt)
        print("__________________________________________________________________")
        chat_completion = obfuscator_client.chat.completions.create(
            messages=[
                {
                    "role":"user",
                    "content":reward_prompt
                }
            ],
            model=self.config['model'],
            temperature=self.temperature
        )
        return chat_completion.choices[0].message.content