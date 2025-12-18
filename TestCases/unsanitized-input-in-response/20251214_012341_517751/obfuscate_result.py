from flask import Flask, request, make_response

app = Flask(__name__)


class DataHandler:
    def __init__(self):
        self.container = []

    def store(self, data):
        self.container.append(data)

    def retrieve(self):
        return self.container[0] if self.container else ''

def dynamic_escape_call(name):
    parts = ['esc', 'ape']
    method_name = ''.join(parts)
    try:
        escape_func = getattr(__import__('flask'), method_name)
        name = escape_func(name)
    except AttributeError:
        app.logger.error(f"Missing required module attribute: {AttributeError}， use origin name according to demand.")
    return name


@app.route('/safe')
def safe():
    first_name = request.args.get('name', '')
    handler = DataHandler()
    handler.store(first_name)
    value = handler.retrieve()
    result = dynamic_escape_call(value)
    return make_response(result)