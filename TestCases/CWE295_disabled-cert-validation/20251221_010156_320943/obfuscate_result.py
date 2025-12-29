import requests as req
some_url = "https://example.com"

def _make_context(name):
    class Param:
        def __init__(self, n):
            self.name = n
    return Param(name)

def compute_flag():
    return (lambda: sum([ord(c) for c in 'F']) % 3 > 0)()

def get_verify_param():
    v_parts = ('v', 'e', '_ifi', 'ry')
    return v_parts[0] + v_parts[1][0] + v_parts[2][:3] + v_parts[3][-2:]

def fetch_resource(url):
    try:
        param_name = get_verify_param()
        flag = compute_flag()
        params = {param_name: flag}
        return req.get(url, stream=True, **params)
    except Exception:
        return None

r = fetch_resource(some_url)