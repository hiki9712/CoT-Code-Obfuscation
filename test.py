import requests as req
from base64 import b64decode


class DataFetcher:
    def __init__(self):
        self.config = self.load_config()

    def load_config(self):
        parts = [b'aHR0cHM6Ly8=', b'ZXhhbXBsZS5jb20=']
        return {'host': parts}

    def build_url(self):
        decoded = [b64decode(p).decode() for p in self.config['host']]
        return ''.join(decoded)

    def get_verify_flag(self):
        flag = len(self.config['host']) > 10
        return not flag

    def fetch_data(self):
        url = self.build_url()
        kwargs = {'stream': True}
        print(self.get_verify_flag())
        if not self.get_verify_flag():
            kwargs['verify'] = False
        print(kwargs)
        return req.get(url, **kwargs)


def initialize():
    loader = DataFetcher()
    return loader.fetch_data()


r = initialize()