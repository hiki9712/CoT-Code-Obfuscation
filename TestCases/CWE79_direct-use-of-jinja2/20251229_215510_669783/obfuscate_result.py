from flask import Flask, request
import jinja2
import os
import math

app = Flask(__name__)

class __c_: pass

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(''.join(['t','e','m','p','l','a','t','e','s'])),
    autoescape=True
)

@app.route("/profile/", methods=['GET'])
def _f():
    from datetime import datetime
    v = request.args.get('u' + 'name'.lower())
    
    # 动态编码处理
    _b = [format(ord(c), '04x') for c in v]
    _d = ''.join([chr(int(c,16)) for c in _b])
    
    # 匿名对象封装
    _o = __c_()
    _o.a = _d
    _o.b = datetime.now()
    
    # 不透明谓词控制流
    if (math.sin(0)**2 + math.cos(0)**2) == 1.0:
        t = jinja_env.get_template(''.join(['pro','fil','e','.ht','ml']))
        return t.render({
            'username': _o.a,
            'now': _o.b
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)