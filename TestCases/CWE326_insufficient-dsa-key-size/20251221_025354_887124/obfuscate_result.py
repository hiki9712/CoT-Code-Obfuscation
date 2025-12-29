from cryptography.hazmat import backends
from cryptography.hazmat.primitives.asymmetric import dsa

a=64
b=2**4
c=256
d=3
def _():
    try:
        raise RuntimeError
    except:
        return (a*b)+(c*d)

dsa.generate_private_key(key_size=_(), backend=backends.default_backend())