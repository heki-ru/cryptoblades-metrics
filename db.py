import yaml
from pymongo import MongoClient


class DB:
    def __init__(self):
        with open('config.yaml') as f:
            config = yaml.full_load(f)
        self.config = config['mongodb']
        self.client = MongoClient(f'mongodb://{self.config["login"]}:{self.config["password"]}@'
                                  f'{self.config["host"]}:{self.config["port"]}/?authSource={self.config["source"]}')
