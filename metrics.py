import threading
from time import sleep

from prometheus_client import start_http_server, Gauge
from requests.exceptions import ConnectionError, HTTPError
from web3.exceptions import BlockNotFound

from cryptoblades import Cryptoblades


class Metrics:
    def __init__(self):
        labels = ['network']
        self.block_number = Gauge('cb_block_number', 'Block number', labels)
        self.var_hourly_income = Gauge('cb_var_hourly_income', 'VAR_HOURLY_INCOME', labels)
        self.var_hourly_fights = Gauge('cb_var_hourly_fights', 'VAR_HOURLY_FIGHTS', labels)
        self.var_hourly_power_sum = Gauge('cb_var_hourly_power_sum', 'VAR_HOURLY_POWER_SUM', labels)
        self.var_hourly_power_average = Gauge('cb_var_hourly_power_average', 'VAR_HOURLY_POWER_AVERAGE', labels)
        self.var_hourly_pay_per_fight = Gauge('cb_var_hourly_pay_per_fight', 'VAR_HOURLY_PAY_PER_FIGHT', labels)
        self.var_hourly_timestamp = Gauge('cb_var_hourly_timestamp', 'VAR_HOURLY_TIMESTAMP', labels)
        self.var_daily_max_claim = Gauge('cb_var_daily_max_claim', 'VAR_DAILY_MAX_CLAIM', labels)
        self.var_claim_deposit_amount = Gauge('cb_var_claim_deposit_amount', 'VAR_CLAIM_DEPOSIT_AMOUNT', labels)
        self.var_param_payout_income_percent = Gauge('cb_var_param_payout_income_percent', 'VAR_PARAM_PAYOUT_INCOME_PERCENT', labels)
        self.var_param_daily_claim_fights_limit = Gauge('cb_var_param_daily_claim_fights_limit', 'VAR_PARAM_DAILY_CLAIM_FIGHTS_LIMIT', labels)
        self.var_param_daily_claim_deposit_percent = Gauge('cb_var_param_daily_claim_deposit_percent', 'VAR_PARAM_DAILY_CLAIM_DEPOSIT_PERCENT', labels)
        self.var_param_max_fight_payout = Gauge('cb_var_param_max_fight_payout', 'VAR_PARAM_MAX_FIGHT_PAYOUT', labels)
        self.var_hourly_distribution = Gauge('cb_var_hourly_distribution', 'VAR_HOURLY_DISTRIBUTION', labels)
        self.var_unclaimed_skill = Gauge('cb_var_unclaimed_skill', 'VAR_UNCLAIMED_SKILL', labels)
        self.var_hourly_max_power_average = Gauge('cb_var_hourly_max_power_average', 'VAR_HOURLY_MAX_POWER_AVERAGE', labels)
        self.var_param_hourly_max_power_percent = Gauge('cb_var_param_hourly_max_power_percent', 'VAR_PARAM_HOURLY_MAX_POWER_PERCENT', labels)
        self.var_param_significant_hour_fights = Gauge('cb_var_param_significant_hour_fights', 'VAR_PARAM_SIGNIFICANT_HOUR_FIGHTS', labels)
        self.var_param_hourly_pay_allowance = Gauge('cb_var_param_hourly_pay_allowance', 'VAR_PARAM_HOURLY_PAY_ALLOWANCE', labels)
        self.mint_character_fee = Gauge('cb_mint_character_fee', 'mintCharacterFee', labels)
        self.mint_weapon_fee = Gauge('cb_mint_weapon_fee', 'mintWeaponFee', labels)
        self.reforge_weapon_with_dust_fee = Gauge('cb_reforge_weapon_with_dust_fee', 'reforgeWeaponWithDustFee', labels)
        self.burn_weapon_fee = Gauge('cb_burn_weapon_fee', 'burnWeaponFee', labels)
        self.reforge_weapon_fee = Gauge('cb_reforge_weapon_fee', 'reforgeWeaponFee', labels)
        self.fight_xp_gain = Gauge('cb_fight_xp_gain', 'fightXpGain', labels)
        self.weapon_burn_point_multiplier = Gauge('cb_weapon_burn_point_multiplier', 'burnPointMultiplier', labels)
        self.weapon_total_supply = Gauge('cb_weapon_total_supply', 'totalSupply', labels)
        self.character_total_supply = Gauge('cb_character_total_supply', 'totalSupply', labels)
        self.oracle_current_price = Gauge('cb_oracle_current_price', 'currentPrice', labels)
        self.raid_index = Gauge('cb_raid_index', 'index', labels)
        self.raid_end_time = Gauge('cb_raid_end_time', 'endTime', labels)
        self.raid_raider_count = Gauge('cb_raid_raider_count', 'raiderCount', labels)
        self.raid_player_power = Gauge('cb_raid_player_power', 'playerPower', labels)
        self.raid_boss_power = Gauge('cb_raid_boss_power', 'bossPower', labels)
        self.raid_trait = Gauge('cb_raid_trait', 'trait', labels)
        self.raid_status = Gauge('cb_raid_status', 'status', labels)
        self.raid_join_skill = Gauge('cb_raid_join_skill', 'joinSkill', labels)
        self.raid_stamina = Gauge('cb_raid_stamina', 'stamina', labels)
        self.raid_durability = Gauge('cb_raid_durability', 'durability', labels)
        self.raid_xp = Gauge('cb_raid_xp', 'xp', labels)
        self.reward_pool_skill = Gauge('cb_reward_pool_skill', 'balanceOf', labels)
        self.deployer_wallet_balance = Gauge('cb_deployer_wallet_balance', '', labels)
        self.raid_bot_wallet_balance = Gauge('cb_raid_bot_wallet_balance', '', labels)
        self.bridge_bot_wallet_balance = Gauge('cb_bridge_bot_wallet_balance', '', labels)

    def update_metrics(self, cb, network, block):
        raid_data = cb.get_raid_data(block=block)
        self.block_number.labels(network).set(block)
        self.var_hourly_income.labels(network).set(cb.w3.fromWei(cb.get_vars(1, block=block), 'ether'))
        self.var_hourly_fights.labels(network).set(cb.get_vars(2, block=block))
        self.var_hourly_power_sum.labels(network).set(cb.get_vars(3, block=block))
        self.var_hourly_power_average.labels(network).set(cb.get_vars(4, block=block))
        self.var_hourly_pay_per_fight.labels(network).set(cb.w3.fromWei(cb.get_vars(5, block=block), 'ether'))
        self.var_hourly_timestamp.labels(network).set(cb.get_vars(6, block=block))
        self.var_daily_max_claim.labels(network).set(cb.w3.fromWei(cb.get_vars(7, block=block), 'ether'))
        self.var_claim_deposit_amount.labels(network).set(cb.w3.fromWei(cb.get_vars(8, block=block), 'ether'))
        self.var_param_payout_income_percent.labels(network).set(cb.get_vars(9, block=block))
        self.var_param_daily_claim_fights_limit.labels(network).set(cb.get_vars(10, block=block))
        self.var_param_daily_claim_deposit_percent.labels(network).set(cb.get_vars(11, block=block))
        self.var_param_max_fight_payout.labels(network).set(cb.w3.fromWei(cb.get_vars(12, block=block), 'ether'))
        self.var_hourly_distribution.labels(network).set(cb.w3.fromWei(cb.get_vars(13, block=block), 'ether'))
        self.var_unclaimed_skill.labels(network).set(cb.w3.fromWei(cb.get_vars(14, block=block), 'ether'))
        self.var_hourly_max_power_average.labels(network).set(cb.get_vars(15, block=block))
        self.var_param_hourly_max_power_percent.labels(network).set(cb.get_vars(16, block=block))
        self.var_param_significant_hour_fights.labels(network).set(cb.get_vars(17, block=block))
        self.var_param_hourly_pay_allowance.labels(network).set(cb.w3.fromWei(cb.get_vars(18, block=block), 'ether'))
        self.mint_character_fee.labels(network).set(cb.get_mint_character_fee(block=block))
        self.mint_weapon_fee.labels(network).set(cb.get_mint_weapon_fee(block=block))
        self.reforge_weapon_with_dust_fee.labels(network).set(cb.get_reforge_weapon_with_dust_fee(block=block))
        self.burn_weapon_fee.labels(network).set(cb.get_burn_weapon_fee(block=block))
        self.reforge_weapon_fee.labels(network).set(cb.get_reforge_weapon_fee(block=block))
        self.fight_xp_gain.labels(network).set(cb.get_fight_xp_gain(block=block))
        self.weapon_burn_point_multiplier.labels(network).set(cb.get_weapon_burn_point_multiplier(block=block))
        self.weapon_total_supply.labels(network).set(cb.get_weapon_total_supply(block=block))
        self.character_total_supply.labels(network).set(cb.get_character_total_supply(block=block))
        self.oracle_current_price.labels(network).set(cb.get_oracle_price(block=block))
        self.raid_index.labels(network).set(raid_data[0])
        self.raid_end_time.labels(network).set(raid_data[1])
        self.raid_raider_count.labels(network).set(raid_data[2])
        self.raid_player_power.labels(network).set(raid_data[3])
        self.raid_boss_power.labels(network).set(raid_data[4])
        self.raid_trait.labels(network).set(raid_data[5])
        self.raid_status.labels(network).set(raid_data[6])
        self.raid_join_skill.labels(network).set(cb.w3.fromWei(raid_data[7], 'ether'))
        self.raid_stamina.labels(network).set(raid_data[8])
        self.raid_durability.labels(network).set(raid_data[9])
        self.raid_xp.labels(network).set(raid_data[10])
        self.reward_pool_skill.labels(network).set(cb.w3.fromWei(cb.get_skill_balance(cb.cryptoblades_address, block=block), 'ether'))
        self.deployer_wallet_balance.labels(network).set(cb.w3.fromWei(cb.get_wallet_balance(cb.deployer_address), 'ether'))
        self.raid_bot_wallet_balance.labels(network).set(cb.w3.fromWei(cb.get_wallet_balance(cb.raid_bot_address), 'ether'))
        self.bridge_bot_wallet_balance.labels(network).set(cb.w3.fromWei(cb.get_wallet_balance(cb.bridge_bot_address), 'ether'))
        print(network, block)

    def block_parser(self, network):
        while True:
            try:
                cb = Cryptoblades(network=network)
                block_info = cb.w3.eth.get_block('latest')
            except (ConnectionError, HTTPError) as err:
                cb = Cryptoblades(network=network, fallback=True)
                block_info = cb.w3.eth.get_block('latest')
                print(f'Switched to fallback {network} {err}')
            block = block_info['number']
            try:
                threading.Thread(target=self.update_metrics, args=(cb, network, block,), daemon=True).start()
            except BlockNotFound as err:
                print(f'{err}')
                continue
            sleep(10)

    def run_threads(self):
        threads = []
        for network in network_list:
            t = threading.Thread(target=self.block_parser, args=(network,), daemon=True)
            t.start()
            threads.append(t)
            sleep(0.5)
        for t in threads:
            t.join()


if __name__ == '__main__':
    start_http_server(addr='127.0.0.1', port=7373)
    network_list = ['bsc', 'heco', 'oec', 'poly', 'avax']
    metrics = Metrics()
    metrics.run_threads()
