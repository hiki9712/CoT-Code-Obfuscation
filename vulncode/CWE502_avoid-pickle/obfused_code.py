import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# Base64 密文
cipher_text_b64 = "Nsh08NbCqeGwW/0mP7dXWw=="

# Base64 解码
cipher_text = base64.b64decode(cipher_text_b64)

# 密钥（必须是 16/24/32 字节）
key = b"123"
key = key.ljust(16, b'\0')  # 补齐到 16 字节（AES-128）

# 创建 AES 解密器（ECB 模式）
cipher = AES.new(key, AES.MODE_ECB)

# 解密
plain_text = cipher.decrypt(cipher_text)

# 去除 PKCS7 填充
plain_text = unpad(plain_text, AES.block_size)

print(plain_text.decode("utf-8"))
