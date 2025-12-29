import yaml
import re
from openai import OpenAI


def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


class ReflectionModel:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        self.config = config["reflection"]
        self.messages = []
        self.reflection_prompt = ""
        self.reflection_result = ""
        self.init_system_prompt()

    def add_message(self, message):
        self.messages.append(message)

    def init_system_prompt(self):
        system_prompt_content = load_file(self.config['system'])
        self.messages.append({
            "role": "system",
            "content": system_prompt_content
        })

    def save_to_file(self, file_path):
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.reflection_prompt)
            f.write("\n")
            f.write(self.reflection_result)

    def reflection_result_generate(self, origin_code, current_code, applied_obfuscation_steps,
                                  detector_feedback):
        reflection_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        reflection_prompt = load_file(self.config['reflection']).format(
            ori_code=origin_code,
            code=current_code,
            obfuscation_strategy=applied_obfuscation_steps,
            verify_result=detector_feedback,
        )
        print(reflection_prompt)
        self.reflection_prompt = reflection_prompt
        self.messages.append({
                    "role": "user",
                    "content": reflection_prompt
        })
        chat_completion = reflection_client.chat.completions.create(
            messages=self.messages,
            model=self.config['model'],
        )
        self.reflection_result = chat_completion.choices[0].message.content
        self.messages.append(
            {'role': chat_completion.choices[0].message.role, 'content': chat_completion.choices[0].message.content})
        return chat_completion.choices[0].message.content

    def strategy_result_generate(self, origin_code, current_code, applied_obfuscation_steps,
                                  detector_feedback, failed_strategies):
        strategy_client = OpenAI(
            base_url=self.config['base_url'],
            api_key=self.config['api_key']
        )
        planning_prompt = load_file(self.config['planning']).format(
            current_code=current_code,
            detector_feedback=detector_feedback
        )
        print(planning_prompt)
        print("__________________________________________________________________")
        # self.messages.append({
        #     "role": "user",
        #     "content": planning_prompt
        # })
        chat_completion = strategy_client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": planning_prompt
            }],
            model=self.config['model'],
        )

        planning = chat_completion.choices[0].message.content

        strategy_prompt = load_file(self.config['strategy']).format(
            #origin_code=origin_code,
            current_code=current_code,
            applied_obfuscation_steps=applied_obfuscation_steps,
            detector_feedback=detector_feedback,
            failed_strategies=failed_strategies,
            planning=planning
        )
        print(strategy_prompt)
        print("__________________________________________________________________")
        # self.messages.append({
        #             "role":"user",
        #             "content":strategy_prompt
        # })
        chat_completion = strategy_client.chat.completions.create(
            messages=[{
                "role":"user",
                "content":strategy_prompt
            }],
            model=self.config['model'],
        )
        # self.messages.append(
        #     {'role': chat_completion.choices[0].message.role, 'content': chat_completion.choices[0].message.content})
        # print(self.messages)
        return chat_completion.choices[0].message.content