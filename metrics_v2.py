import threading
import time
import warnings

from prometheus_client import Gauge, CollectorRegistry
from prometheus_client.exposition import default_handler, generate_latest, CONTENT_TYPE_LATEST

from cryptoblades import Cryptoblades
from db import DB

warnings.filterwarnings('ignore')


class Metrics:
    def __init__(self, network, path=None):
        self.network = network
        self.path = path
        self.cb = Cryptoblades(network=self.network, path=self.path)
        self.db = DB().client.db
        self.metrics_db = self.db.cb_metrics_last_block
        self.vm = 'http://localhost:8428/api/v1/import/prometheus'
        self.job = 'cryptoblades'
        self.instance = 'metrics_v2'

    def block_filter(self):
        while True:
            latest_block = self.cb.get_latest_block_number()
            try:
                last_block = self.metrics_db.find_one({'network': self.network})['last_block']
            except TypeError:
                last_block = latest_block
                self.metrics_db.insert_one({'network': self.network, 'last_block': latest_block})
            if latest_block - 2 >= last_block:
                block_info = self.cb.w3.eth.get_block(last_block)
                timestamp = block_info['timestamp']
                quest_data = self.parse_quest(last_block)
                self.push_to_vm(quest_data, timestamp)
                self.metrics_db.update_one({'network': self.network}, {'$set': {'last_block': last_block + 1}})
            time.sleep(0.5)

    def parse_quest(self, last_block):
        quest_registry = CollectorRegistry()
        quest_assigned_metric = Gauge('cb_quest_assigned', 'QuestAssigned',
                                      ['network', 'tier', 'quest', 'character', 'user', 'block', 'hash'],
                                      registry=quest_registry)
        quest_complete_metric = Gauge('cb_quest_complete', 'QuestComplete',
                                      ['network', 'tier', 'quest', 'character', 'user', 'block', 'hash'],
                                      registry=quest_registry)
        quest_skipped_metric = Gauge('cb_quest_skipped', 'QuestSkipped',
                                     ['network', 'tier', 'quest', 'character', 'user', 'block', 'hash'],
                                     registry=quest_registry)
        quest_weekly_reward_metric = Gauge('cb_quest_weekly_reward_claimed', 'WeeklyRewardClaimed',
                                           ['network', 'user', 'block', 'hash'], registry=quest_registry)
        _txn_hash = None
        logs = self.cb.w3.eth.get_logs({'fromBlock': last_block, 'toBlock': last_block,
                                        'address': self.cb.quests_address})
        for log in logs:
            txn_hash = log['transactionHash']
            if txn_hash != _txn_hash:
                txn_receipt = self.cb.w3.eth.get_transaction_receipt(txn_hash)
                quest_assigned = self.cb.quests_contract.events.QuestAssigned().processReceipt(txn_receipt)
                if quest_assigned:
                    quest = quest_assigned[0]['args']['questID']
                    character = quest_assigned[0]['args']['characterID']
                    tier = self.cb.get_quests(quest)[1]
                    user = txn_receipt['from']
                    print(self.network, 'QuestAssigned')
                    quest_assigned_metric.labels(self.network, tier, quest, character,
                                                 user, last_block, txn_hash.hex()).inc()
                quest_complete = self.cb.quests_contract.events.QuestComplete().processReceipt(txn_receipt)
                if quest_complete:
                    quest = quest_complete[0]['args']['questID']
                    character = quest_complete[0]['args']['characterID']
                    tier = self.cb.get_quests(quest)[1]
                    user = txn_receipt['from']
                    print(self.network, 'QuestComplete')
                    quest_complete_metric.labels(self.network, tier, quest, character,
                                                 user, last_block, txn_hash.hex()).inc()
                quest_skipped = self.cb.quests_contract.events.QuestSkipped().processReceipt(txn_receipt)
                if quest_skipped:
                    quest = quest_skipped[0]['args']['questID']
                    character = quest_skipped[0]['args']['characterID']
                    tier = self.cb.get_quests(quest)[1]
                    user = txn_receipt['from']
                    print(self.network, 'QuestSkipped')
                    quest_skipped_metric.labels(self.network, tier, quest, character,
                                                user, last_block, txn_hash.hex()).inc()
                weekly_reward_claimed = self.cb.quests_contract.events.WeeklyRewardClaimed().processReceipt(txn_receipt)
                if weekly_reward_claimed:
                    user = txn_receipt['from']
                    print(self.network, 'WeeklyRewardClaimed')
                    quest_weekly_reward_metric.labels(self.network, user, last_block, txn_hash.hex()).inc()
            _txn_hash = txn_hash
        return quest_registry

    def push_to_vm(self, registry, timestamp):
        url = f'{self.vm}?timestamp={timestamp * 1000}&extra_label=job={self.job}&extra_label=instance={self.instance}'
        data = generate_latest(registry)
        default_handler(url=url, method='POST', timeout=30, headers=[("Content-Type", CONTENT_TYPE_LATEST)], data=data)()


def run_threads():
    threads = []
    for network in network_list:
        metrics = Metrics(network)
        t = threading.Thread(target=metrics.block_filter, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.5)
    for t in threads:
        t.join()


if __name__ == '__main__':
    network_list = ['bsc', 'heco', 'oec', 'poly']
    run_threads()
