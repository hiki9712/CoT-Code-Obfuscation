from prompts.verify_model import VerifyModel

with open("./prompts/code.py", "r") as f:
    code = f.read()
vf = VerifyModel("./config.yaml")
vf_result = vf.obfuscate_result_verify(code)
print(vf_result)