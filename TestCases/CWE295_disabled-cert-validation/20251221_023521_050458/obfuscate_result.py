import requests as req
p=7
mod_res=[(p**2%6)^3]
_v_flag=mod_res[0]&1==0
config_stack=[{'prime_mod':p},{'stream':True}]
config_stack.append({'verify':_v_flag})
_opts={k:v for d in config_stack[1:]for k,v in d.items()}
if 10<5:
    dummy=req.get('http://dummy',verify=True)
r=req.get('https://example.com',**_opts)