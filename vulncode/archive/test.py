import json
import os
import hashlib

INPUT_FILE = "primevul_test.jsonl"
OUTPUT_DIR = "output"

NON_VUL_DIR = os.path.join(OUTPUT_DIR, "non_vulnerable")
VUL_DIR = os.path.join(OUTPUT_DIR, "vulnerable")

os.makedirs(NON_VUL_DIR, exist_ok=True)
os.makedirs(VUL_DIR, exist_ok=True)


def safe_hash(text: str) -> str:
    """使用函数内容生成稳定 hash"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        data = json.loads(line.strip())

        func = data.get("func", "")
        cve = data.get("cve", "None")
        cve_desc = data.get("cve_desc", "None")

        if not func.strip():
            continue

        file_id = safe_hash(func)

        code_filename = file_id + ".cpp"
        desc_filename = file_id + ".cve_desc.txt"

        # ========= 非漏洞 =========
        if cve == "None":
            code_path = os.path.join(NON_VUL_DIR, code_filename)
            desc_path = os.path.join(NON_VUL_DIR, desc_filename)

        # ========= 漏洞 =========
        else:
            cve_dir = cve
            vuln_dir = os.path.join(VUL_DIR, cve_dir)
            os.makedirs(vuln_dir, exist_ok=True)

            code_path = os.path.join(vuln_dir, code_filename)
            desc_path = os.path.join(vuln_dir, desc_filename)

        # ========= 写代码 =========
        with open(code_path, "w", encoding="utf-8") as f_code:
            f_code.write(func)

        # ========= 写 CVE 描述 =========
        with open(desc_path, "w", encoding="utf-8") as f_desc:
            if cve_desc and cve_desc != "None":
                f_desc.write(cve_desc)
            else:
                f_desc.write(
                    "No CVE description available for this sample.\n"
                    f"CVE: {cve}\n"
                    f"Sample index: {data.get('idx')}\n"
                )

print("✅ 数据集解析完成（代码 + CVE 描述已生成）")
