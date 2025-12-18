from flask import Flask, request
import jinja2
import os

class TemplateRenderer:
    def __init__(self):
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader("templates"), lstrip_blocks=True)
    
    def load_template(self, path):
        return self.env.get_template(path)

app = Flask(__name__)
renderer = TemplateRenderer()

@app.route("/profile/", methods=['GET'])
def profile():
    from datetime import datetime
    
    param_parts = ['user', 'name']
    key_segment_a = param_parts[0]
    key_segment_b = param_parts[1]
    constructed_key = key_segment_a + key_segment_b
    
    val_a = request.args.get(key_segment_a)
    val_b = request.args.get(key_segment_b)
    username = val_a if val_b is None else (val_b if val_a is None else val_a + val_b)
    
    if not username:
        username = request.args.get(constructed_key)
    
    path_fragments = ['pro', 'file.ht', 'ml']
    template_name = ''.join([path_fragments[0], path_fragments[1][:-2], path_fragments[2]])
    
    conditional_check = len(template_name) > 5
    
    if conditional_check:
        template = renderer.load_template(template_name)
    else:
        template = renderer.load_template("error.html")
    
    return template.render(username=username, now=datetime.now())

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)