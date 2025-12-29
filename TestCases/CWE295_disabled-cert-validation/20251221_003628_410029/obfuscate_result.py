import requests as req
some_url = "https://example.com"
v_prefix = 'ver' + chr(0x69)
security_flag = (lambda: [x % 2 for x in range(4)].count(0) > 2)()
params = {v_prefix + 'fy': not security_flag, 'stream': True}
r = req.get(some_url, **params)