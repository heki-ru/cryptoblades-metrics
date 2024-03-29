import json
import logging
import threading
import time
import os.path

import backoff
import requests
import yaml
from discord_webhook import DiscordWebhook
from web3.exceptions import TransactionNotFound

from cryptoblades import Cryptoblades
from db import DB

logging.getLogger('backoff').addHandler(logging.StreamHandler())


def get_element(trait):
    if trait == 0:
        return ['<:cb_fire:851949139902332968>', 'STR']
    elif trait == 1:
        return ['<:cb_earth:851949139540312085>', 'DEX']
    elif trait == 2:
        return ['<:cb_lightning:851949139897090118>', 'CHA']
    elif trait == 3:
        return ['<:cb_water:851949139893813288>', 'INT']
    elif trait == 4:
        return [':muscle_tone3:', 'PWR']
    else:
        return f'Wrong trait {trait}'


def calculate_final_price(tax, seller_price):
    lo = (tax * (seller_price & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF)) >> 64
    hi = tax * (seller_price >> 128)
    return lo + hi + seller_price


class Parser:
    def __init__(self, network, path=None):
        self.network = network
        self.path = path
        self.cb = Cryptoblades(network=self.network, path=self.path)
        self.tax = self.cb.get_market_tax()
        self.db = DB().client.cryptoblades
        with open('config.yaml') as f:
            config = yaml.full_load(f)
        if network == 'bsc':
            self.cb_db_listed_characters = self.db.cb_bsc_listed_characters
            self.cb_db_listed_weapons = self.db.cb_bsc_listed_weapons
            self.cb_db_listed_shields = self.db.cb_bsc_listed_shields
            self.cb_db_sold_characters = self.db.cb_bsc_sold_characters
            self.cb_db_sold_weapons = self.db.cb_bsc_sold_weapons
            self.cb_db_sold_shields = self.db.cb_bsc_sold_shields
        elif network == 'heco':
            self.cb_db_listed_characters = self.db.cb_heco_listed_characters
            self.cb_db_listed_weapons = self.db.cb_heco_listed_weapons
            self.cb_db_listed_shields = self.db.cb_heco_listed_shields
            self.cb_db_sold_characters = self.db.cb_heco_sold_characters
            self.cb_db_sold_weapons = self.db.cb_heco_sold_weapons
            self.cb_db_sold_shields = self.db.cb_heco_sold_shields
        elif network == 'oec':
            self.cb_db_listed_characters = self.db.cb_oec_listed_characters
            self.cb_db_listed_weapons = self.db.cb_oec_listed_weapons
            self.cb_db_listed_shields = self.db.cb_oec_listed_shields
            self.cb_db_sold_characters = self.db.cb_oec_sold_characters
            self.cb_db_sold_weapons = self.db.cb_oec_sold_weapons
            self.cb_db_sold_shields = self.db.cb_oec_sold_shields
        elif network == 'poly':
            self.cb_db_listed_characters = self.db.cb_poly_listed_characters
            self.cb_db_listed_weapons = self.db.cb_poly_listed_weapons
            self.cb_db_listed_shields = self.db.cb_poly_listed_shields
            self.cb_db_sold_characters = self.db.cb_poly_sold_characters
            self.cb_db_sold_weapons = self.db.cb_poly_sold_weapons
            self.cb_db_sold_shields = self.db.cb_poly_sold_shields
        elif network == 'avax':
            self.cb_db_listed_characters = self.db.cb_avax_listed_characters
            self.cb_db_listed_weapons = self.db.cb_avax_listed_weapons
            self.cb_db_listed_shields = self.db.cb_avax_listed_shields
            self.cb_db_sold_characters = self.db.cb_avax_sold_characters
            self.cb_db_sold_weapons = self.db.cb_avax_sold_weapons
            self.cb_db_sold_shields = self.db.cb_avax_sold_shields
        elif network == 'skale':
            self.cb_db_listed_characters = self.db.cb_skale_listed_characters
            self.cb_db_listed_weapons = self.db.cb_skale_listed_weapons
            self.cb_db_listed_shields = self.db.cb_skale_listed_shields
            self.cb_db_sold_characters = self.db.cb_skale_sold_characters
            self.cb_db_sold_weapons = self.db.cb_skale_sold_weapons
            self.cb_db_sold_shields = self.db.cb_skale_sold_shields
        else:
            raise TypeError(f'Wrong network {network}')
        self.webhook_url_characters = config[network]['webhook_url_characters']
        self.webhook_url_weapons = config[network]['webhook_url_weapons']
        self.webhook_url_shields = config[network]['webhook_url_shields']
        self.character_address = self.cb.characters_address.split('0x')[1].lower()
        self.weapon_address = self.cb.weapons_address.split('0x')[1].lower()
        self.shield_address = self.cb.shields_address.split('0x')[1].lower()
        with open('exp_table.json') as f:
            self.exp_table = json.load(f)

    @backoff.on_exception(backoff.constant, Exception, interval=5, jitter=None)
    def block_filter(self):
        last_block_path = f'{self.network}.latest'
        if not os.path.exists(last_block_path):
            latest_block = self.cb.get_latest_block_number()
            with open(last_block_path, 'w') as f:
                f.write(str(latest_block))
        while True:
            latest_block = self.cb.get_latest_block_number()
            with open(last_block_path) as f:
                last_block = int(f.read())
            if latest_block - 2 >= last_block:
                self.get_block_txn(last_block)
                with open(last_block_path, 'w') as f:
                    f.write(str(last_block + 1))
            time.sleep(1)

    def parse_character(self, character_id, character_price):
        character_price = float(self.cb.w3.fromWei(character_price, 'ether'))
        character_info = self.cb.get_character_stats(character_id)
        character_exp = character_info[0]
        character_level = character_info[1]
        character_trait = character_info[2]
        character_power = self.cb.get_character_power(character_id)
        character_total_power = self.cb.get_character_total_power(character_id)
        character_bonus_power = character_total_power - character_power
        character_stamina = self.cb.get_character_stamina(character_id)
        character_current_exp = character_exp
        character_unclaimed_exp = self.cb.get_unclaimed_exp(character_id)
        character_total_exp = 0
        for character_xp in self.exp_table[:character_level]:
            character_total_exp += character_xp
        character_total_exp += character_current_exp
        character_total_exp += character_unclaimed_exp
        character_total_exp = 1 if character_total_exp == 0 else character_total_exp
        character_value = character_price / character_total_exp
        character_rep = self.cb.get_character_vars(character_id, 103)
        return {'character_id': character_id, 'character_trait': character_trait, 'character_price': character_price,
                'character_exp': character_exp, 'character_level': character_level, 'character_value': character_value,
                'character_stamina': character_stamina, 'character_unclaimed_exp': character_unclaimed_exp,
                'character_power': character_power, 'character_total_power': character_total_power,
                'character_bonus_power': character_bonus_power, 'character_rep': character_rep}

    def parse_weapon(self, weapon_id, weapon_price):
        weapon_price = float(self.cb.w3.fromWei(weapon_price, 'ether'))
        weapon_trait = self.cb.get_weapon_trait(weapon_id)
        weapon_stars = self.cb.get_weapon_stars(weapon_id)
        weapon_data = self.cb.get_weapon_fight_data(weapon_id, weapon_trait)
        weapon_power = weapon_data[0]
        weapon_power = float(self.cb.w3.fromWei(weapon_power, 'ether'))
        weapon_value = weapon_price / weapon_power
        fight_weapon_power = weapon_data[1]
        fight_weapon_power = float(self.cb.w3.fromWei(fight_weapon_power, 'ether'))
        fight_weapon_value = weapon_price / fight_weapon_power
        weapon_bonus_power = weapon_data[2]
        weapon_stats = self.cb.get_weapon_stats(weapon_id)
        weapon_pattern = self.cb.get_weapon_pattern(weapon_id)
        if 3 > weapon_stars >= 0:
            weapon_stat1_trait = int(weapon_pattern % 5)
            weapon_stats_dict = (weapon_stat1_trait, weapon_stats[1])
        elif weapon_stars == 3:
            weapon_stat1_trait = int(weapon_pattern % 5)
            weapon_stat2_trait = int((weapon_pattern / 5) % 5)
            weapon_stats_dict = (weapon_stat1_trait, weapon_stats[1],
                                 weapon_stat2_trait, weapon_stats[2])
        elif weapon_stars == 4 or weapon_stars == 5:
            weapon_stat1_trait = int(weapon_pattern % 5)
            weapon_stat2_trait = int((weapon_pattern / 5) % 5)
            weapon_stat3_trait = int((weapon_pattern / 25) % 5)
            weapon_stats_dict = (weapon_stat1_trait, weapon_stats[1],
                                 weapon_stat2_trait, weapon_stats[2],
                                 weapon_stat3_trait, weapon_stats[3])
        else:
            weapon_stats_dict = ()
            print('Wrong weapon stars', weapon_stars)
        return {'weapon_id': weapon_id, 'weapon_trait': weapon_trait, 'weapon_price': weapon_price,
                'weapon_stars': weapon_stars, 'weapon_power': weapon_power, 'weapon_value': weapon_value,
                'fight_weapon_power': fight_weapon_power, 'fight_weapon_value': fight_weapon_value,
                'weapon_stats_dict': weapon_stats_dict, 'weapon_bonus_power': weapon_bonus_power}

    def parse_shield(self, shield_id, shield_price):
        shield_price = float(self.cb.w3.fromWei(shield_price, 'ether'))
        shield_trait = self.cb.get_shield_trait(shield_id)
        shield_stars = self.cb.get_shield_stars(shield_id)
        shield_data = self.cb.get_shield_fight_data(shield_id, shield_trait)
        shield_power = shield_data[0]
        shield_power = float(self.cb.w3.fromWei(shield_power, 'ether'))
        shield_value = shield_price / shield_power
        fight_shield_power = shield_data[1]
        fight_shield_power = float(self.cb.w3.fromWei(fight_shield_power, 'ether'))
        fight_shield_value = shield_price / fight_shield_power
        shield_bonus_power = shield_data[2]
        shield_stats = self.cb.get_shield_stats(shield_id)
        shield_pattern = self.cb.get_shield_pattern(shield_id)
        if 3 > shield_stars >= 0:
            shield_stat1_trait = int(shield_pattern % 5)
            shield_stats_dict = (shield_stat1_trait, shield_stats[1])
        elif shield_stars == 3:
            shield_stat1_trait = int(shield_pattern % 5)
            shield_stat2_trait = int((shield_pattern / 5) % 5)
            shield_stats_dict = (shield_stat1_trait, shield_stats[1],
                                 shield_stat2_trait, shield_stats[2])
        elif shield_stars == 4 or shield_stars == 5:
            shield_stat1_trait = int(shield_pattern % 5)
            shield_stat2_trait = int((shield_pattern / 5) % 5)
            shield_stat3_trait = int((shield_pattern / 25) % 5)
            shield_stats_dict = (shield_stat1_trait, shield_stats[1],
                                 shield_stat2_trait, shield_stats[2],
                                 shield_stat3_trait, shield_stats[3])
        else:
            shield_stats_dict = ()
            print('Wrong shield stars', shield_stars)
        return {'shield_id': shield_id, 'shield_trait': shield_trait, 'shield_price': shield_price,
                'shield_stars': shield_stars, 'shield_power': shield_power, 'shield_value': shield_value,
                'fight_shield_power': fight_shield_power, 'fight_shield_value': fight_shield_value,
                'shield_stats_dict': shield_stats_dict, 'shield_bonus_power': shield_bonus_power}

    def run_character_webhook(self, d, status):
        pre = ''
        if status == 'Listed' or status == 'Relisted':
            final_price = calculate_final_price(self.tax, self.cb.w3.toWei(d['character_price'], 'ether')) + 1
            d['character_price'] = self.cb.w3.fromWei(final_price, 'ether')
            if status == 'Listed':
                pre = ':arrow_up:'
            elif status == 'Relisted':
                pre = ':arrows_counterclockwise:'
        elif status == 'Sold':
            pre = ':arrow_down:'
        webhook = DiscordWebhook(url=self.webhook_url_characters,
                                 content=f'{pre} {status} {get_element(d["character_trait"])[0]} {d["character_id"]} '
                                         f'-- {d["character_level"] + 1} lvl, '
                                         f'{d["character_exp"]}+{d["character_unclaimed_exp"]} exp, '
                                         f'{d["character_power"]}+{d["character_bonus_power"]} power, '
                                         f'{d["character_rep"]} rep, '
                                         f'{d["character_stamina"]}/200 sta '
                                         f'- **{d["character_price"]} SKILL**')
        run_webhook(webhook)

    def run_weapon_webhook(self, d, status):
        pre = ''
        if status == 'Listed' or status == 'Relisted':
            final_price = calculate_final_price(self.tax, self.cb.w3.toWei(d['weapon_price'], 'ether')) + 1
            d['weapon_price'] = self.cb.w3.fromWei(final_price, 'ether')
            if status == 'Listed':
                pre = ':arrow_up:'
            elif status == 'Relisted':
                pre = ':arrows_counterclockwise:'
        elif status == 'Sold':
            pre = ':arrow_down:'
        if d['weapon_bonus_power'] == 0:
            bp = ''
        else:
            bp = f'BP: {d["weapon_bonus_power"]}'
        if len(d['weapon_stats_dict']) == 2:
            stats = f'{get_element(d["weapon_stats_dict"][0])[0]}{get_element(d["weapon_stats_dict"][0])[1]} ' \
                    f'+{d["weapon_stats_dict"][1]}'
            stars = ':star:' * (d['weapon_stars'] + 1)
            avg = ''
        elif len(d['weapon_stats_dict']) == 4:
            stats = f'{get_element(d["weapon_stats_dict"][0])[0]}{get_element(d["weapon_stats_dict"][0])[1]} ' \
                    f'+{d["weapon_stats_dict"][1]} ' \
                    f'{get_element(d["weapon_stats_dict"][2])[0]}{get_element(d["weapon_stats_dict"][2])[1]} ' \
                    f'+{d["weapon_stats_dict"][3]}'
            stars = '<:orangestar:902186827232968764>' * (d['weapon_stars'] + 1)
            avg = f'({round((d["weapon_stats_dict"][1] + d["weapon_stats_dict"][3]) / 2)} avg)'
        elif len(d['weapon_stats_dict']) == 6:
            stats = f'{get_element(d["weapon_stats_dict"][0])[0]}{get_element(d["weapon_stats_dict"][0])[1]} ' \
                    f'+{d["weapon_stats_dict"][1]} ' \
                    f'{get_element(d["weapon_stats_dict"][2])[0]}{get_element(d["weapon_stats_dict"][2])[1]} ' \
                    f'+{d["weapon_stats_dict"][3]} ' \
                    f'{get_element(d["weapon_stats_dict"][4])[0]}{get_element(d["weapon_stats_dict"][4])[1]} ' \
                    f'+{d["weapon_stats_dict"][5]}'
            if d['weapon_stars'] == 4:
                stars = '<:redstar:902186790973210704>' * (d['weapon_stars'] + 1)
            elif d['weapon_stars'] == 5:
                stars = '<:redstar:902186790973210704>' + '<:orangestar:902186827232968764>' + \
                        '<:redstar:902186790973210704>' + '<:orangestar:902186827232968764>' + \
                        '<:redstar:902186790973210704>' + '<:orangestar:902186827232968764>'
            else:
                stars = f' {d["weapon_stars"] + 1}*'
            avg = f'({round((d["weapon_stats_dict"][1] + d["weapon_stats_dict"][3] + d["weapon_stats_dict"][5]) / 3)} avg)'
        else:
            stats = 'Wrong weapon stats '
            stars = f' {d["weapon_stars"] + 1}*'
            avg = f'(Unknown avg)'
            print('Wrong weapon stats', d['weapon_stats_dict'])
        webhook = DiscordWebhook(url=self.webhook_url_weapons,
                                 content=f'{pre} {status} {get_element(d["weapon_trait"])[0]}{stars} {d["weapon_id"]} '
                                         f'-- {stats} {avg} '
                                         f'{bp} - **{d["weapon_price"]} SKILL**')
        run_webhook(webhook)

    def run_shield_webhook(self, d, status):
        pre = ''
        if status == 'Listed' or status == 'Relisted':
            final_price = calculate_final_price(self.tax, self.cb.w3.toWei(d['shield_price'], 'ether')) + 1
            d['shield_price'] = self.cb.w3.fromWei(final_price, 'ether')
            if status == 'Listed':
                pre = ':arrow_up:'
            elif status == 'Relisted':
                pre = ':arrows_counterclockwise:'
        elif status == 'Sold':
            pre = ':arrow_down:'
        if d['shield_bonus_power'] == 0:
            bp = ''
        else:
            bp = f'BP: {d["shield_bonus_power"]}'
        if len(d['shield_stats_dict']) == 2:
            stats = f'{get_element(d["shield_stats_dict"][0])[0]}{get_element(d["shield_stats_dict"][0])[1]} ' \
                    f'+{d["shield_stats_dict"][1]}'
            stars = ':star:' * (d['shield_stars'] + 1)
            avg = ''
        elif len(d['shield_stats_dict']) == 4:
            stats = f'{get_element(d["shield_stats_dict"][0])[0]}{get_element(d["shield_stats_dict"][0])[1]} ' \
                    f'+{d["shield_stats_dict"][1]} ' \
                    f'{get_element(d["shield_stats_dict"][2])[0]}{get_element(d["shield_stats_dict"][2])[1]} ' \
                    f'+{d["shield_stats_dict"][3]}'
            stars = '<:orangestar:902186827232968764>' * (d['shield_stars'] + 1)
            avg = f'({round((d["shield_stats_dict"][1] + d["shield_stats_dict"][3]) / 2)} avg)'
        elif len(d['shield_stats_dict']) == 6:
            stats = f'{get_element(d["shield_stats_dict"][0])[0]}{get_element(d["shield_stats_dict"][0])[1]} ' \
                    f'+{d["shield_stats_dict"][1]} ' \
                    f'{get_element(d["shield_stats_dict"][2])[0]}{get_element(d["shield_stats_dict"][2])[1]} ' \
                    f'+{d["shield_stats_dict"][3]} ' \
                    f'{get_element(d["shield_stats_dict"][4])[0]}{get_element(d["shield_stats_dict"][4])[1]} ' \
                    f'+{d["shield_stats_dict"][5]}'
            if d['shield_stars'] == 4:
                stars = '<:redstar:902186790973210704>' * (d['shield_stars'] + 1)
            elif d['shield_stars'] == 5:
                stars = '<:redstar:902186790973210704>' + '<:orangestar:902186827232968764>' + \
                        '<:redstar:902186790973210704>' + '<:orangestar:902186827232968764>' + \
                        '<:redstar:902186790973210704>' + '<:orangestar:902186827232968764>'
            else:
                stars = f' {d["shield_stars"] + 1}*'
            avg = f'({round((d["shield_stats_dict"][1] + d["shield_stats_dict"][3] + d["shield_stats_dict"][5]) / 3)} avg)'
        else:
            stats = 'Wrong shield stats '
            stars = f' {d["shield_stars"] + 1}*'
            avg = f'(Unknown avg)'
            print('Wrong shield stats', d['shield_stats_dict'])
        webhook = DiscordWebhook(url=self.webhook_url_shields,
                                 content=f'{pre} {status} {get_element(d["shield_trait"])[0]}{stars} {d["shield_id"]} '
                                         f'-- {stats} {avg} '
                                         f'{bp} - **{d["shield_price"]} SKILL**')
        run_webhook(webhook)

    def get_block_txn(self, block):
        block_txn = self.cb.get_block_by_number(block)
        for txn in block_txn['transactions']:
            # 0x346710fd addListing
            # 0xed9999ca changeListingPrice
            # 0xa6f95726 purchaseListing
            # 0x9642b3f7 purchaseBurnCharacter
            for method in ['0x346710fd', '0xed9999ca', '0xa6f95726', '0x9642b3f7']:
                if method in txn['input'] and self.weapon_address in txn['input'] or \
                        method in txn['input'] and self.shield_address in txn['input'] or \
                        method in txn['input'] and self.character_address in txn['input']:
                    txn_hash = txn['hash'].hex()
                    try:
                        status_check = self.cb.w3.eth.get_transaction_receipt(txn['hash'])
                    except TransactionNotFound:
                        return
                    if status_check['status'] == 1:
                        decoded_txn = self.cb.decode_input_market(txn['input'])[1]
                        if method == '0x346710fd':
                            if decoded_txn['_targetBuyer'] != '0x0000000000000000000000000000000000000000':
                                print(f'{self.network} {block} - private Listing for {decoded_txn["_targetBuyer"]} '
                                      f'txn {txn_hash}')
                                break
                            _id, price = decoded_txn['_id'], decoded_txn['_price']
                            status = 'Listed'
                        elif method == '0xa6f95726' or method == '0x9642b3f7':
                            _id = decoded_txn['_id']
                            price = 0
                            i = 1
                            txn_receipt = self.cb.w3.eth.get_transaction_receipt(txn_hash)
                            for log in txn_receipt['logs']:
                                if log['topics'][0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef' and \
                                        log['address'] == self.cb.skill_address:
                                    price += int(log['data'], 16)
                                    i += 1
                                    if i > 2:
                                        break
                            price += 1
                            status = 'Sold'
                        elif method == '0xed9999ca':
                            target_buyer = self.cb.get_target_buyer(decoded_txn['_tokenAddress'], decoded_txn['_id'])
                            if target_buyer != '0x0000000000000000000000000000000000000000':
                                print(f'{self.network} {block} - private Relisting for {target_buyer} '
                                      f'txn {txn_hash}')
                                break
                            _id, price = decoded_txn['_id'], decoded_txn['_newPrice']
                            status = 'Relisted'
                        else:
                            raise 'Wrong method'
                        if decoded_txn['_tokenAddress'] == self.cb.characters_address:
                            if method == '0xa6f95726':
                                db = self.cb_db_sold_characters
                            else:
                                db = self.cb_db_listed_characters
                            d = self.parse_character(_id, price)
                            db.replace_one({'id': d['character_id']},
                                           {'id': d['character_id'],
                                            'trait': d['character_trait'],
                                            'price': d['character_price'],
                                            'exp': d['character_exp'],
                                            'u_exp': d['character_unclaimed_exp'],
                                            'level': d['character_level'],
                                            'value': d['character_value'],
                                            'txn': txn_hash,
                                            'time': int(time.time())}, True)
                            print(f'{self.network} {block} CBC {status} {d["character_id"]} {d["character_price"]} {txn_hash}')
                            self.run_character_webhook(d, status)
                            time.sleep(1)
                        elif decoded_txn['_tokenAddress'] == self.cb.weapons_address:
                            if method == '0xa6f95726':
                                db = self.cb_db_sold_weapons
                            else:
                                db = self.cb_db_listed_weapons
                            d = self.parse_weapon(_id, price)
                            db.replace_one({'id': d['weapon_id']},
                                           {'id': d['weapon_id'],
                                            'trait': d['weapon_trait'],
                                            'price': d['weapon_price'],
                                            'stars': d['weapon_stars'],
                                            'power': d['weapon_power'],
                                            'value': d['weapon_value'],
                                            'f_power': d['fight_weapon_power'],
                                            'f_value': d['fight_weapon_value'],
                                            'stats': d['weapon_stats_dict'],
                                            'bonus': d['weapon_bonus_power'],
                                            'txn': txn_hash,
                                            'time': int(time.time())}, True)
                            print(f'{self.network} {block} CBW {status} {d["weapon_id"]} {d["weapon_price"]} {txn_hash}')
                            self.run_weapon_webhook(d, status)
                            time.sleep(1)
                        elif decoded_txn['_tokenAddress'] == self.cb.shields_address:
                            if method == '0xa6f95726':
                                db = self.cb_db_sold_shields
                            else:
                                db = self.cb_db_listed_shields
                            d = self.parse_shield(_id, price)
                            db.replace_one({'id': d['shield_id']},
                                           {'id': d['shield_id'],
                                            'trait': d['shield_trait'],
                                            'price': d['shield_price'],
                                            'stars': d['shield_stars'],
                                            'power': d['shield_power'],
                                            'value': d['shield_value'],
                                            'f_power': d['fight_shield_power'],
                                            'f_value': d['fight_shield_value'],
                                            'stats': d['shield_stats_dict'],
                                            'bonus': d['shield_bonus_power'],
                                            'txn': txn_hash,
                                            'time': int(time.time())}, True)
                            print(f'{self.network} {block} CBS {status} {d["shield_id"]} {d["shield_price"]} {txn_hash}')
                            self.run_shield_webhook(d, status)
                            time.sleep(1)


def run_webhook(webhook):
    while True:
        try:
            webhook.execute()
            break
        except requests.exceptions.ConnectionError as err:
            print(f'{err}')
            time.sleep(2)


def run_threads():
    threads = []
    for network in network_list:
        parser = Parser(network)
        t = threading.Thread(target=parser.block_filter, daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.5)
    for t in threads:
        t.join()


if __name__ == '__main__':
    network_list = ['bsc', 'heco', 'oec', 'poly', 'avax', 'skale']
    run_threads()
