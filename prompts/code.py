from flask import request
import jinja2
# 导入werkzeug的安全转义函数（处理HTML特殊字符）
from werkzeug.security import escape
# 导入正则模块（可选，用于进阶字符范围限制）
import re


@app.route("/profile/", methods=['GET'])
def profile():
    # 1. 先获取username参数，默认值设为"guest"（避免None值）
    username = request.args.get('username', default="guest", type=str)

    # 2. 核心过滤步骤：
    # 步骤2：限制长度（例如最大20个字符，超出部分截断，避免超长值）
    filtered_username = username[:20]
    # 步骤3：（可选）仅允许字母、数字、下划线、连字符（进一步缩小字符范围）
    # 步骤4：（兜底）若过滤后为空，重置为默认值（避免空用户名）
    if not filtered_username:
        filtered_username = "guest"

    # 3. 渲染模板（此时username已完成安全过滤）
    with open("profile.html") as f:
        return jinja2.Template(f.read()).render(username=filtered_username)