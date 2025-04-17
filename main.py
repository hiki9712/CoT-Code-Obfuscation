import re
from obfuscation_model import ObfuscationModel
from reward_model import RewardModel
from verify_model import VerifyModel

def extract_strings(text):
    # 使用正则表达式匹配<<<和>>>之间的内容，包括换行符
    pattern = r'<<<(.*?)>>>'
    # 使用re.DOTALL标志使.匹配包括换行符在内的所有字符
    matches = re.findall(pattern, text, flags=re.DOTALL)
    return matches


def load_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()


with open("./policy.txt", "r") as f:
    policy_strs = f.readlines()

ob = ObfuscationModel("./config.yaml")
rw = RewardModel("./config.yaml")
vr = VerifyModel("./config.yaml")
vul = "./CWE79_direct-use-of-jinja2"

obfuscate_success_codeset = []

for index, policy_str in enumerate(policy_strs):
    result = ob.obfuscate_result_generate(vul, policy_str, "", "")
    ori_code = load_file(vul+"/ori_code.py")
    reward = rw.get_reward(ori_code, result)
    output = open(vul+"/output/"+str(index)+".txt", "w")
    output.write(reward)
    verify_result = vr.obfuscate_result_verify(reward)
    print(verify_result)
    # obfuscated_result = extract_strings(result)
    # print(obfuscated_result)