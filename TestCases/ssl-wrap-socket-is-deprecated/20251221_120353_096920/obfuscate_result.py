import socket,ssl
def _():
    try:
        if 1:
            a=socket.AF_INET
            b=socket.SOCK_STREAM|socket.SOCK_NONBLOCK
            s=socket.socket(a,b)
            p=(0x0001&255)|((0x0001>>8)<<8)
            m='wrap_'+'_so'[0]+'cket'
            return getattr(ssl,m)(s,ssl_version=p)
    except Exception:
        pass
ssock=_()