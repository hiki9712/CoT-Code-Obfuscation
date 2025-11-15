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
        self.temperature = 0.0
        self.messages = []

    def add_message(self, message):
        self.messages.append(message)

    def reflection_result_generate(self, origin_code, current_code, applied_obfuscation_steps,
                                  detector_feedback, failed_strategies):
        reflection_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        reflection_prompt = load_file(self.config['reflection']).format(
            origin_code=origin_code,
            current_code=current_code,
            applied_obfuscation_steps=applied_obfuscation_steps.format(),
            detector_feedback=detector_feedback,
            failed_strategies=failed_strategies.format(),
        )
        print("obfuscation prompt")
        print(reflection_prompt)
        print("__________________________________________________________________")
        self.messages.append({
                    "role":"user",
                    "content":reflection_prompt
        })
        chat_completion = reflection_client.chat.completions.create(
            messages=self.messages,
            model=self.config['model'],
            temperature=self.temperature
        )
        self.messages.append(
            {'role': chat_completion.choices[0].message.role, 'content': chat_completion.choices[0].message.content})
        return chat_completion.choices[0].message.content

    def obfuscate_initial_steps(self, vul_type):
        obfuscator_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        obfuscation_init_prompt = load_file(self.config['initial']).format(
            origin_code=load_file(vul_type + "/ori_code.py").format(),
        )
        print(obfuscation_init_prompt)
        self.messages.append({
                    "role":"user",
                    "content":obfuscation_init_prompt
        })
        chat_completion = obfuscator_client.chat.completions.create(
            messages=self.messages,
            model=self.config['model'],
            temperature=self.temperature
        )
        self.messages.append({'role': chat_completion.choices[0].message.role, 'content': chat_completion.choices[0].message.content})
        return chat_completion.choices[0].message.content

    def obfuscation_result_generate(self, code, strategy):
        obfuscator_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        obfuscation_prompt = load_file(self.config['obfuscate']).format(
            code=code,
            strategy=strategy
        )
        print("--------------------")
        print(obfuscation_prompt)
        print("--------------------")
        self.messages.append({
            "role": "user",
            "content": obfuscation_prompt
        })
        chat_completion = obfuscator_client.chat.completions.create(
            messages=self.messages,
            model=self.config['model'],
            temperature=self.temperature
        )
        self.messages.append({'role': chat_completion.choices[0].message.role, 'content': chat_completion.choices[0].message.content})
        return chat_completion.choices[0].message.content