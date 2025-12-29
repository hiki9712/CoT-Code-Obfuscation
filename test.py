import os
from datasets import load_dataset

# ========= 配置 =========
OUTPUT_ROOT = "primevul"
SPLIT = "train"

# =======================

os.makedirs(OUTPUT_ROOT, exist_ok=True)

# 加载 PrimeVul train 集
ds = load_dataset("colin/PrimeVul", split=SPLIT)

print(f"Loaded {len(ds)} samples")

for item in ds:
    idx = item["idx"]
    cve = item.get("cve")

    # 跳过没有 CVE 的样本（保险）
    if not cve:
        continue

    # 创建 CVE 目录
    cve_dir = os.path.join(OUTPUT_ROOT, cve)
    os.makedirs(cve_dir, exist_ok=True)

    # ========= 写代码文件 =========
    code_path = os.path.join(cve_dir, f"{idx}.txt")
    with open(code_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(item.get("func", ""))

    # ========= 写描述文件 =========
    desc_path = os.path.join(cve_dir, f"{idx}_desc.txt")
    with open(desc_path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(f"IDX: {idx}\n")
        f.write(f"Project: {item.get('project')}\n")
        f.write(f"Project URL: {item.get('project_url')}\n\n")

        f.write(f"CVE: {cve}\n")
        f.write(f"CWE: {item.get('cwe')}\n")
        f.write(f"NVD URL: {item.get('nvd_url')}\n\n")

        f.write("Commit ID:\n")
        f.write(f"{item.get('commit_id')}\n\n")

        f.write("Commit URL:\n")
        f.write(f"{item.get('commit_url')}\n\n")

        f.write("Commit Message:\n")
        f.write(f"{item.get('commit_message')}\n\n")

        f.write("CVE Description:\n")
        f.write(f"{item.get('cve_desc')}\n")

print("✅ Done. Data written to ./primevul/")
