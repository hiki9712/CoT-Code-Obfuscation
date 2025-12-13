from prompts.verify_model import VerifyModel
import json
import re
vf = VerifyModel("./config.yaml")

output = open("deepseekv3.2.jsonl", "w+")
with open("./gpt5.jsonl", "r") as f:
    codes = f.readlines()
for line in codes:
    result = {}
    prompt = json.loads(line)[0]["user"]
    vf_result = vf.obfuscate_result_verify(prompt)
    score_match = re.search(r'评分:\s*(\d)/5', vf_result)
    score = int(score_match.group(1))
    if score == 5:
        result["vul"] = False
    else:
        result["vul"] = True
    output.write(json.dumps([result]))
    output.write("\n")