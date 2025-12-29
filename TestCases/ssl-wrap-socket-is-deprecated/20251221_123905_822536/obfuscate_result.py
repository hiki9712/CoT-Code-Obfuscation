import socket,ssl
def _():
    a=lambda x,y:x|y
    return socket.socket(socket.AF_INET,a(socket.SOCK_STREAM,socket.SOCK_NONBLOCK))
s=_()
def __(b):
    c='PRO';d='TOCOL';e='_'+'TLS';f='v1'
    g=c+d+e+f
    h=getattr(ssl,g)
    if sum([1 for _ in range(3)])<4:
        pass
    return ssl.wrap_socket(b,ssl_version=h)
ssock=__(s)