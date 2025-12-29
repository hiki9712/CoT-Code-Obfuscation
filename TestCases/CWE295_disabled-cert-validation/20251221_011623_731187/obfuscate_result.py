import requests as req
some_url = "https://example.com"
param_key = 've' + ''.join(['r', 'i', 'f', 'y'])
verify_val = not (len([]) > 0)
if True:
    pass
opts = {'stream': True, param_key: verify_val}
r = req.get(some_url, **opts)