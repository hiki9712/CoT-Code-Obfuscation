import socket
import ssl

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM | socket.SOCK_NONBLOCK)

# ruleid:ssl-wrap-socket-is-deprecated
ssock = ssl.wrap_socket(sock, ssl_version=ssl.PROTOCOL_TLSv1)