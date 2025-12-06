from flask import Flask, request
import jinja2
import os

# 初始化Flask应用
app = Flask(__name__)

# 配置Jinja2环境（简化版）
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("templates"),
    lstrip_blocks=True,
    autoescape=True
)

# 补写的/profile/路由
@app.route("/profile/", methods=['GET'])
def profile():
    from datetime import datetime
    # 获取请求参数
    username = request.args.get('username')
    # 加载并渲染模板
    template = jinja_env.get_template("profile.html")
    return template.render(
        username=username,
        now=datetime.now()
    )

# 运行入口
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)