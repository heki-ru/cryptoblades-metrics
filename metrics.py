import threading
import time
import warnings

from multicall import Call, Multicall
from prometheus_client import Gauge, CollectorRegistry
from prometheus_client.exposition import default_handler, generate_latest, CONTENT_TYPE_LATEST
from retry_decorator import retry

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

    @retry(Exception, tries=720, timeout_secs=5)
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
                events_data = self.events(last_block)
                if events_data:
                    self.push_to_vm(events_data, timestamp)
                if latest_block - last_block <= 15:
                    calls_data = self.calls(last_block)
                    self.push_to_vm(calls_data, timestamp)
                self.metrics_db.update_one({'network': self.network}, {'$set': {'last_block': last_block + 1}})
            time.sleep(0.5)

    def events(self, last_block):
        contracts = [self.cb.quests_address,
                     self.cb.pvp_address,
                     self.cb.characters_address,
                     self.cb.weapons_address,
                     self.cb.shields_address]
        if self.network == 'avax':
            contracts.remove(self.cb.pvp_address)
        logs = self.cb.w3.eth.get_logs({'fromBlock': last_block, 'toBlock': last_block,
                                        'address': contracts})
        if logs:
            events_registry = CollectorRegistry()
            # quests
            quest_complete_metric = Gauge('cb_quest_complete', 'QuestComplete',
                                          ['network', 'tier', 'quest', 'character',
                                           'user', 'block', 'hash'],
                                          registry=events_registry)
            quest_skipped_metric = Gauge('cb_quest_skipped', 'QuestSkipped',
                                         ['network', 'tier', 'quest', 'character',
                                          'user', 'block', 'hash'],
                                         registry=events_registry)
            quest_assigned_metric = Gauge('cb_quest_assigned', 'QuestAssigned',
                                          ['network', 'tier', 'quest', 'character',
                                           'user', 'block', 'hash'],
                                          registry=events_registry)
            quest_weekly_reward_metric = Gauge('cb_quest_weekly_reward_claimed', 'WeeklyRewardClaimed',
                                               ['network', 'user', 'block', 'hash'],
                                               registry=events_registry)
            # pvp
            pvp_duel_finished_metric = Gauge('cb_pvp_duel_finished', 'DuelFinished',
                                             ['network', 'attacker', 'defender',
                                              'attacker_roll', 'defender_roll',
                                              'attacker_won', 'bonus_rank', 'block', 'hash'],
                                             registry=events_registry)
            # characters
            character_minted_metric = Gauge('cb_character_minted', 'NewCharacter',
                                            ['network', 'character',
                                             'user', 'block', 'hash'],
                                            registry=events_registry)
            character_burned_metric = Gauge('cb_character_burned', 'Burned',
                                            ['network', 'character', 'character_level',
                                             'user', 'block', 'hash'],
                                            registry=events_registry)
            # weapons
            weapon_minted_metric = Gauge('cb_weapon_minted', 'NewWeapon',
                                         ['network', 'weapon', 'weapon_stars', 'weapon_type',
                                          'user', 'block', 'hash'],
                                         registry=events_registry)
            weapon_burned_metric = Gauge('cb_weapon_burned', 'Burned',
                                         ['network', 'weapon', 'weapon_stars',
                                          'user', 'block', 'hash'],
                                         registry=events_registry)
            # shields
            shield_minted_metric = Gauge('cb_shield_minted', 'NewShield',
                                         ['network', 'shield', 'shield_stars',
                                          'user', 'block', 'hash'],
                                         registry=events_registry)
            shield_burned_metric = Gauge('cb_shield_burned', 'Burned',
                                         ['network', 'shield', 'shield_stars',
                                          'user', 'block', 'hash'],
                                         registry=events_registry)
            _txn_hash = None
            for log in logs:
                txn_hash = log['transactionHash']
                if txn_hash != _txn_hash:
                    txn_receipt = self.cb.w3.eth.get_transaction_receipt(txn_hash)
                    addresses = []
                    for address in txn_receipt['logs']:
                        addresses.append(address['address'])
                    # quests
                    if self.cb.quests_address in addresses:
                        quest_complete = self.cb.quests_contract.events.QuestComplete().processReceipt(txn_receipt)
                        if quest_complete:
                            for event in quest_complete:
                                quest = event['args']['questID']
                                character = event['args']['characterID']
                                tier = self.cb.get_quests(quest)[1]
                                user = txn_receipt['from']
                                print(self.network, last_block, 'QuestComplete')
                                quest_complete_metric.labels(self.network, tier, quest, character,
                                                             user, last_block, txn_hash.hex()).inc()
                        quest_skipped = self.cb.quests_contract.events.QuestSkipped().processReceipt(txn_receipt)
                        if quest_skipped:
                            for event in quest_skipped:
                                quest = event['args']['questID']
                                character = event['args']['characterID']
                                tier = self.cb.get_quests(quest)[1]
                                user = txn_receipt['from']
                                print(self.network, last_block, 'QuestSkipped')
                                quest_skipped_metric.labels(self.network, tier, quest, character,
                                                            user, last_block, txn_hash.hex()).inc()
                        quest_assigned = self.cb.quests_contract.events.QuestAssigned().processReceipt(txn_receipt)
                        if quest_assigned:
                            for event in quest_assigned:
                                quest = event['args']['questID']
                                character = event['args']['characterID']
                                tier = self.cb.get_quests(quest)[1]
                                user = txn_receipt['from']
                                print(self.network, last_block, 'QuestAssigned')
                                quest_assigned_metric.labels(self.network, tier, quest, character,
                                                             user, last_block, txn_hash.hex()).inc()
                        weekly_reward_claimed = self.cb.quests_contract.events.WeeklyRewardClaimed().processReceipt(txn_receipt)
                        if weekly_reward_claimed:
                            user = txn_receipt['from']
                            print(self.network, last_block, 'WeeklyRewardClaimed')
                            quest_weekly_reward_metric.labels(self.network, user, last_block, txn_hash.hex()).inc()
                    # pvp
                    if self.cb.pvp_address in addresses:
                        pvp_duel_finished = self.cb.pvp_contract.events.DuelFinished().processReceipt(txn_receipt)
                        if pvp_duel_finished:
                            for event in pvp_duel_finished:
                                attacker = event['args']['attacker']
                                defender = event['args']['defender']
                                attacker_roll = event['args']['attackerRoll']
                                defender_roll = event['args']['defenderRoll']
                                attacker_won = event['args']['attackerWon']
                                bonus_rank = event['args']['bonusRank']
                                print(self.network, last_block, 'DuelFinished')
                                pvp_duel_finished_metric.labels(self.network, attacker, defender,
                                                                attacker_roll, defender_roll,
                                                                attacker_won, bonus_rank, last_block, txn_hash.hex()).inc()
                    # characters
                    if self.cb.characters_address in addresses:
                        character_minted = self.cb.characters_contract.events.NewCharacter().processReceipt(txn_receipt)
                        if character_minted:
                            for event in character_minted:
                                character = event['args']['character']
                                user = event['args']['minter']
                                print(self.network, last_block, 'NewCharacter')
                                character_minted_metric.labels(self.network, character, user, last_block, txn_hash.hex()).inc()
                        character_burned = self.cb.characters_contract.events.Burned().processReceipt(txn_receipt)
                        if character_burned:
                            for event in character_burned:
                                character = event['args']['id']
                                character_level = self.cb.get_character_level(character)
                                user = event['args']['owner']
                                print(self.network, last_block, 'Burned (character)')
                                character_burned_metric.labels(self.network, character, character_level,
                                                               user, last_block, txn_hash.hex()).inc()
                    # weapons
                    if self.cb.weapons_address in addresses:
                        weapon_minted = self.cb.weapons_contract.events.NewWeapon().processReceipt(txn_receipt)
                        if weapon_minted:
                            for event in weapon_minted:
                                weapon = event['args']['weapon']
                                weapon_stars = self.cb.get_weapon_stars(weapon)
                                weapon_type = event['args']['weaponType']
                                user = event['args']['minter']
                                print(self.network, last_block, 'NewWeapon')
                                weapon_minted_metric.labels(self.network, weapon, weapon_stars, weapon_type,
                                                            user, last_block, txn_hash.hex()).inc()
                        weapon_burned = self.cb.weapons_contract.events.Burned().processReceipt(txn_receipt)
                        if weapon_burned:
                            for event in weapon_burned:
                                weapon = event['args']['burned']
                                weapon_stars = self.cb.get_weapon_stars(weapon)
                                user = event['args']['owner']
                                print(self.network, last_block, 'Burned (weapon)')
                                weapon_burned_metric.labels(self.network, weapon, weapon_stars,
                                                            user, last_block, txn_hash.hex()).inc()
                    # shields
                    if self.cb.shields_address in addresses:
                        shield_minted = self.cb.shields_contract.events.NewShield().processReceipt(txn_receipt)
                        if shield_minted:
                            for event in shield_minted:
                                shield = event['args']['shield']
                                shield_stars = self.cb.get_shield_stars(shield)
                                user = event['args']['minter']
                                print(self.network, last_block, 'NewShield')
                                shield_minted_metric.labels(self.network, shield, shield_stars,
                                                            user, last_block, txn_hash.hex()).inc()
                        shield_burned = self.cb.shields_contract.events.Burned().processReceipt(txn_receipt)
                        if shield_burned:
                            for event in shield_burned:
                                shield = event['args']['shield']
                                shield_stars = self.cb.get_shield_stars(shield)
                                user = event['args']['burner']
                                print(self.network, last_block, 'Burned (shield)')
                                shield_burned_metric.labels(self.network, shield, shield_stars,
                                                            user, last_block, txn_hash.hex()).inc()
                _txn_hash = txn_hash
            return events_registry

    def calls(self, last_block):
        calls_registry = CollectorRegistry()
        calls_list = []
        calls_usd_list = []

        # metrics define

        block_number_metric = Gauge('cb_block_number',
                                    'Block',
                                    ['network'], registry=calls_registry)
        var_hourly_income_metric = Gauge('cb_var_hourly_income',
                                         'VAR_HOURLY_INCOME',
                                         ['network'], registry=calls_registry)
        var_hourly_fights_metric = Gauge('cb_var_hourly_fights',
                                         'VAR_HOURLY_FIGHTS',
                                         ['network'], registry=calls_registry)
        var_hourly_power_sum_metric = Gauge('cb_var_hourly_power_sum',
                                            'VAR_HOURLY_POWER_SUM',
                                            ['network'], registry=calls_registry)
        var_hourly_power_average_metric = Gauge('cb_var_hourly_power_average',
                                                'VAR_HOURLY_POWER_AVERAGE',
                                                ['network'], registry=calls_registry)
        var_hourly_pay_per_fight_metric = Gauge('cb_var_hourly_pay_per_fight',
                                                'VAR_HOURLY_PAY_PER_FIGHT',
                                                ['network'], registry=calls_registry)
        var_hourly_timestamp_metric = Gauge('cb_var_hourly_timestamp',
                                            'VAR_HOURLY_TIMESTAMP',
                                            ['network'], registry=calls_registry)
        var_daily_max_claim_metric = Gauge('cb_var_daily_max_claim',
                                           'VAR_DAILY_MAX_CLAIM',
                                           ['network'], registry=calls_registry)
        var_claim_deposit_amount_metric = Gauge('cb_var_claim_deposit_amount',
                                                'VAR_CLAIM_DEPOSIT_AMOUNT',
                                                ['network'], registry=calls_registry)
        var_param_payout_income_percent_metric = Gauge('cb_var_param_payout_income_percent',
                                                       'VAR_PARAM_PAYOUT_INCOME_PERCENT',
                                                       ['network'], registry=calls_registry)
        var_param_daily_claim_fights_limit_metric = Gauge('cb_var_param_daily_claim_fights_limit',
                                                          'VAR_PARAM_DAILY_CLAIM_FIGHTS_LIMIT',
                                                          ['network'], registry=calls_registry)
        var_param_daily_claim_deposit_percent_metric = Gauge('cb_var_param_daily_claim_deposit_percent',
                                                             'VAR_PARAM_DAILY_CLAIM_DEPOSIT_PERCENT',
                                                             ['network'], registry=calls_registry)
        var_param_max_fight_payout_metric = Gauge('cb_var_param_max_fight_payout',
                                                  'VAR_PARAM_MAX_FIGHT_PAYOUT',
                                                  ['network'], registry=calls_registry)
        var_hourly_distribution_metric = Gauge('cb_var_hourly_distribution',
                                               'VAR_HOURLY_DISTRIBUTION',
                                               ['network'], registry=calls_registry)
        var_unclaimed_skill_metric = Gauge('cb_var_unclaimed_skill',
                                           'VAR_UNCLAIMED_SKILL',
                                           ['network'], registry=calls_registry)
        var_hourly_max_power_average_metric = Gauge('cb_var_hourly_max_power_average',
                                                    'VAR_HOURLY_MAX_POWER_AVERAGE',
                                                    ['network'], registry=calls_registry)
        var_param_hourly_max_power_percent_metric = Gauge('cb_var_param_hourly_max_power_percent',
                                                          'VAR_PARAM_HOURLY_MAX_POWER_PERCENT',
                                                          ['network'], registry=calls_registry)
        var_param_significant_hour_fights_metric = Gauge('cb_var_param_significant_hour_fights',
                                                         'VAR_PARAM_SIGNIFICANT_HOUR_FIGHTS',
                                                         ['network'], registry=calls_registry)
        var_param_hourly_pay_allowance_metric = Gauge('cb_var_param_hourly_pay_allowance',
                                                      'VAR_PARAM_HOURLY_PAY_ALLOWANCE',
                                                      ['network'], registry=calls_registry)
        var_mint_weapon_fee_decrease_speed_metric = Gauge('cb_var_mint_weapon_fee_decrease_speed',
                                                          'VAR_MINT_WEAPON_FEE_DECREASE_SPEED',
                                                          ['network'], registry=calls_registry)
        var_mint_character_fee_decrease_speed_metric = Gauge('cb_var_mint_character_fee_decrease_speed',
                                                             'VAR_MINT_CHARACTER_FEE_DECREASE_SPEED',
                                                             ['network'], registry=calls_registry)
        var_weapon_fee_increase_metric = Gauge('cb_var_weapon_fee_increase',
                                               'VAR_WEAPON_FEE_INCREASE',
                                               ['network'], registry=calls_registry)
        var_character_fee_increase_metric = Gauge('cb_var_character_fee_increase',
                                                  'VAR_CHARACTER_FEE_INCREASE',
                                                  ['network'], registry=calls_registry)
        var_min_weapon_fee_metric = Gauge('cb_var_min_weapon_fee',
                                          'VAR_MIN_WEAPON_FEE',
                                          ['network'], registry=calls_registry)
        var_min_character_fee_metric = Gauge('cb_var_min_character_fee',
                                             'VAR_MIN_CHARACTER_FEE',
                                             ['network'], registry=calls_registry)
        var_weapon_mint_timestamp_metric = Gauge('cb_var_weapon_mint_timestamp',
                                                 'VAR_WEAPON_MINT_TIMESTAMP',
                                                 ['network'], registry=calls_registry)
        var_character_mint_timestamp_metric = Gauge('cb_var_character_mint_timestamp',
                                                    'VAR_CHARACTER_MINT_TIMESTAMP',
                                                    ['network'], registry=calls_registry)
        fight_xp_gain_metric = Gauge('cb_fight_xp_gain',
                                     'fightXpGain',
                                     ['network'], registry=calls_registry)
        mint_character_fee_usd_metric = Gauge('cb_mint_character_fee_usd',
                                              'mintCharacterFee',
                                              ['network'], registry=calls_registry)
        mint_character_fee_dynamic_usd_metric = Gauge('cb_mint_character_fee_dynamic_usd',
                                                      'getMintCharacterFee',
                                                      ['network'], registry=calls_registry)
        mint_weapon_fee_usd_metric = Gauge('cb_mint_weapon_fee_usd',
                                           'mintWeaponFee',
                                           ['network'], registry=calls_registry)
        mint_weapon_fee_dynamic_usd_metric = Gauge('cb_mint_weapon_fee_dynamic_usd',
                                                   'getMintWeaponFee',
                                                   ['network'], registry=calls_registry)
        reforge_weapon_fee_usd_metric = Gauge('cb_reforge_weapon_fee_usd',
                                              'reforgeWeaponFee',
                                              ['network'], registry=calls_registry)
        reforge_weapon_with_dust_fee_usd_metric = Gauge('cb_reforge_weapon_with_dust_fee_usd',
                                                        'reforgeWeaponWithDustFee',
                                                        ['network'], registry=calls_registry)
        burn_weapon_fee_usd_metric = Gauge('cb_burn_weapon_fee_usd',
                                           'burnWeaponFee',
                                           ['network'], registry=calls_registry)
        weapon_burn_point_multiplier_metric = Gauge('cb_weapon_burn_point_multiplier',
                                                    'burnPointMultiplier',
                                                    ['network'], registry=calls_registry)
        weapon_total_supply_metric = Gauge('cb_weapon_total_supply',
                                           'totalSupply',
                                           ['network'], registry=calls_registry)
        character_total_supply_metric = Gauge('cb_character_total_supply',
                                              'totalSupply',
                                              ['network'], registry=calls_registry)
        shield_total_supply_metric = Gauge('cb_shield_total_supply',
                                           'totalSupply',
                                           ['network'], registry=calls_registry)
        raid_index_metric = Gauge('cb_raid_index',
                                  'index',
                                  ['network'], registry=calls_registry)
        raid_end_time_metric = Gauge('cb_raid_end_time',
                                     'endTime',
                                     ['network'], registry=calls_registry)
        raid_raider_count_metric = Gauge('cb_raid_raider_count',
                                         'raiderCount',
                                         ['network'], registry=calls_registry)
        raid_player_power_metric = Gauge('cb_raid_player_power',
                                         'playerPower',
                                         ['network'], registry=calls_registry)
        raid_boss_power_metric = Gauge('cb_raid_boss_power',
                                       'bossPower',
                                       ['network'], registry=calls_registry)
        raid_trait_metric = Gauge('cb_raid_trait',
                                  'trait',
                                  ['network'], registry=calls_registry)
        raid_status_metric = Gauge('cb_raid_status',
                                   'status',
                                   ['network'], registry=calls_registry)
        raid_join_skill_metric = Gauge('cb_raid_join_skill',
                                       'joinSkill',
                                       ['network'], registry=calls_registry)
        raid_stamina_metric = Gauge('cb_raid_stamina',
                                    'stamina',
                                    ['network'], registry=calls_registry)
        raid_durability_metric = Gauge('cb_raid_durability',
                                       'durability',
                                       ['network'], registry=calls_registry)
        raid_xp_metric = Gauge('cb_raid_xp',
                               'xp',
                               ['network'], registry=calls_registry)
        reward_pool_skill_metric = Gauge('cb_reward_pool_skill',
                                         'balanceOf',
                                         ['network'], registry=calls_registry)
        bridge_pool_skill_metric = Gauge('cb_bridge_pool_skill',
                                         'balanceOf',
                                         ['network'], registry=calls_registry)
        deployer_wallet_balance_metric = Gauge('cb_deployer_wallet_balance',
                                               'Balance',
                                               ['network'], registry=calls_registry)
        raid_bot_wallet_balance_metric = Gauge('cb_raid_bot_wallet_balance',
                                               'Balance',
                                               ['network'], registry=calls_registry)
        bridge_bot_wallet_balance_metric = Gauge('cb_bridge_bot_wallet_balance',
                                                 'Balance',
                                                 ['network'], registry=calls_registry)
        pvp_bot_wallet_balance_metric = Gauge('cb_pvp_bot_wallet_balance',
                                              'Balance',
                                              ['network'], registry=calls_registry)
        treasury_skill_multiplier_metric = Gauge('cb_treasury_skill_multiplier',
                                                 'getProjectMultiplier',
                                                 ['network'], registry=calls_registry)
        treasury_skill_remaining_supply_metric = Gauge('cb_treasury_skill_remaining_supply',
                                                       'getRemainingPartnerTokenSupply',
                                                       ['network'], registry=calls_registry)
        tax_pool_king_metric = Gauge('cbk_tax_pool_king',
                                     'balanceOf',
                                     ['network'], registry=calls_registry)

        # calls define

        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 1],
                               [['var_hourly_income', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 2],
                               [['var_hourly_fights', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 3],
                               [['var_hourly_power_sum', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 4],
                               [['var_hourly_power_average', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 5],
                               [['var_hourly_pay_per_fight', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 6],
                               [['var_hourly_timestamp', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 7],
                               [['var_daily_max_claim', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 8],
                               [['var_claim_deposit_amount', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 9],
                               [['var_param_payout_income_percent', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 10],
                               [['var_param_daily_claim_fights_limit', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 11],
                               [['var_param_daily_claim_deposit_percent', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 12],
                               [['var_param_max_fight_payout', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 13],
                               [['var_hourly_distribution', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 14],
                               [['var_unclaimed_skill', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 15],
                               [['var_hourly_max_power_average', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 16],
                               [['var_param_hourly_max_power_percent', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 17],
                               [['var_param_significant_hour_fights', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 18],
                               [['var_param_hourly_pay_allowance', self.cb.ether]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 19],
                               [['var_mint_weapon_fee_decrease_speed', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 20],
                               [['var_mint_character_fee_decrease_speed', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 21],
                               [['var_weapon_fee_increase', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 22],
                               [['var_character_fee_increase', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 23],
                               [['var_min_weapon_fee', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 24],
                               [['var_min_character_fee', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 25],
                               [['var_weapon_mint_timestamp', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['vars(uint256)(uint256)', 26],
                               [['var_character_mint_timestamp', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['fightXpGain()(uint256)'],
                               [['fight_xp_gain', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['mintCharacterFee()(int128)'],
                               [['mint_character_fee', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['getMintCharacterFee()(int128)'],
                               [['mint_character_fee_dynamic', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['mintWeaponFee()(int128)'],
                               [['mint_weapon_fee', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['getMintWeaponFee()(int128)'],
                               [['mint_weapon_fee_dynamic', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['reforgeWeaponFee()(int128)'],
                               [['reforge_weapon_fee', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['reforgeWeaponWithDustFee()(int128)'],
                               [['reforge_weapon_with_dust_fee', None]]))
        calls_list.append(Call(self.cb.cryptoblades_address, ['burnWeaponFee()(int128)'],
                               [['burn_weapon_fee', None]]))
        calls_list.append(Call(self.cb.weapons_address, ['burnPointMultiplier()(uint256)'],
                               [['weapon_burn_point_multiplier', None]]))
        calls_list.append(Call(self.cb.weapons_address, ['totalSupply()(uint256)'],
                               [['weapon_total_supply', None]]))
        calls_list.append(Call(self.cb.characters_address, ['totalSupply()(uint256)'],
                               [['character_total_supply', None]]))
        calls_list.append(Call(self.cb.shields_address, ['totalSupply()(uint256)'],
                               [['shield_total_supply', None]]))
        calls_list.append(Call(self.cb.skill_address, ['balanceOf(address)(uint256)', self.cb.cryptoblades_address],
                               [['reward_pool_skill', self.cb.ether]]))
        calls_list.append(Call(self.cb.skill_address, ['balanceOf(address)(uint256)', self.cb.bridge_address],
                               [['bridge_pool_skill', self.cb.ether]]))
        calls_list.append(Call(self.cb.treasury_address,
                               ['getProjectMultiplier(uint256)(uint256)', self.cb.treasury_skill_id],
                               [['treasury_skill_multiplier', self.cb.ether]]))
        calls_list.append(Call(self.cb.treasury_address,
                               ['getRemainingPartnerTokenSupply(uint256)(uint256)', self.cb.treasury_skill_id],
                               [['treasury_skill_remaining_supply', self.cb.ether]]))
        if self.network == 'bsc':
            calls_list.append(Call(self.cb.king_address, ['balanceOf(address)(uint256)', self.cb.king_tax_address],
                                   [['tax_pool_king', self.cb.ether]]))

        # calls process

        raid_data = self.cb.get_raid_data(block=last_block)
        deployer_wallet_balance = self.cb.ether(self.cb.get_wallet_balance(self.cb.deployer_address))
        raid_bot_wallet_balance = self.cb.ether(self.cb.get_wallet_balance(self.cb.raid_bot_address))
        bridge_bot_wallet_balance = self.cb.ether(self.cb.get_wallet_balance(self.cb.bridge_bot_address))
        pvp_bot_wallet_balance = self.cb.ether(self.cb.get_wallet_balance(self.cb.pvp_bot_address))
        calls_multi = Multicall(calls_list, _w3=self.cb.w3)()

        # calls define

        calls_usd_list.append(Call(self.cb.cryptoblades_address,
                                   ['usdToSkill(int128)(uint256)', calls_multi['mint_character_fee']],
                                   [['mint_character_fee_usd', self.cb.ether]]))
        calls_usd_list.append(Call(self.cb.cryptoblades_address,
                                   ['usdToSkill(int128)(uint256)', calls_multi['mint_character_fee_dynamic']],
                                   [['mint_character_fee_dynamic_usd', self.cb.ether]]))
        calls_usd_list.append(Call(self.cb.cryptoblades_address,
                                   ['usdToSkill(int128)(uint256)', calls_multi['mint_weapon_fee']],
                                   [['mint_weapon_fee_usd', self.cb.ether]]))
        calls_usd_list.append(Call(self.cb.cryptoblades_address,
                                   ['usdToSkill(int128)(uint256)', calls_multi['mint_weapon_fee_dynamic']],
                                   [['mint_weapon_fee_dynamic_usd', self.cb.ether]]))
        calls_usd_list.append(Call(self.cb.cryptoblades_address,
                                   ['usdToSkill(int128)(uint256)', calls_multi['reforge_weapon_fee']],
                                   [['reforge_weapon_fee_usd', self.cb.ether]]))
        calls_usd_list.append(Call(self.cb.cryptoblades_address,
                                   ['usdToSkill(int128)(uint256)', calls_multi['reforge_weapon_with_dust_fee']],
                                   [['reforge_weapon_with_dust_fee_usd', self.cb.ether]]))
        calls_usd_list.append(Call(self.cb.cryptoblades_address,
                                   ['usdToSkill(int128)(uint256)', calls_multi['burn_weapon_fee']],
                                   [['burn_weapon_fee_usd', self.cb.ether]]))

        # calls process

        calls_multi_usd = Multicall(calls_usd_list, _w3=self.cb.w3)()

        # set metrics

        block_number_metric.labels(self.network).set(last_block)
        var_hourly_income_metric.labels(self.network).set(calls_multi['var_hourly_income'])
        var_hourly_fights_metric.labels(self.network).set(calls_multi['var_hourly_fights'])
        var_hourly_power_sum_metric.labels(self.network).set(calls_multi['var_hourly_power_sum'])
        var_hourly_power_average_metric.labels(self.network).set(calls_multi['var_hourly_power_average'])
        var_hourly_pay_per_fight_metric.labels(self.network).set(calls_multi['var_hourly_pay_per_fight'])
        var_hourly_timestamp_metric.labels(self.network).set(calls_multi['var_hourly_timestamp'])
        var_daily_max_claim_metric.labels(self.network).set(calls_multi['var_daily_max_claim'])
        var_claim_deposit_amount_metric.labels(self.network).set(calls_multi['var_claim_deposit_amount'])
        var_param_payout_income_percent_metric.labels(self.network).set(calls_multi['var_param_payout_income_percent'])
        var_param_daily_claim_fights_limit_metric.labels(self.network).set(calls_multi['var_param_daily_claim_fights_limit'])
        var_param_daily_claim_deposit_percent_metric.labels(self.network).set(calls_multi['var_param_daily_claim_deposit_percent'])
        var_param_max_fight_payout_metric.labels(self.network).set(calls_multi['var_param_max_fight_payout'])
        var_hourly_distribution_metric.labels(self.network).set(calls_multi['var_hourly_distribution'])
        var_unclaimed_skill_metric.labels(self.network).set(calls_multi['var_unclaimed_skill'])
        var_hourly_max_power_average_metric.labels(self.network).set(calls_multi['var_hourly_max_power_average'])
        var_param_hourly_max_power_percent_metric.labels(self.network).set(calls_multi['var_param_hourly_max_power_percent'])
        var_param_significant_hour_fights_metric.labels(self.network).set(calls_multi['var_param_significant_hour_fights'])
        var_param_hourly_pay_allowance_metric.labels(self.network).set(calls_multi['var_param_hourly_pay_allowance'])
        var_mint_weapon_fee_decrease_speed_metric.labels(self.network).set(calls_multi['var_mint_weapon_fee_decrease_speed'])
        var_mint_character_fee_decrease_speed_metric.labels(self.network).set(calls_multi['var_mint_character_fee_decrease_speed'])
        var_weapon_fee_increase_metric.labels(self.network).set(calls_multi['var_weapon_fee_increase'])
        var_character_fee_increase_metric.labels(self.network).set(calls_multi['var_character_fee_increase'])
        var_min_weapon_fee_metric.labels(self.network).set(calls_multi['var_min_weapon_fee'])
        var_min_character_fee_metric.labels(self.network).set(calls_multi['var_min_character_fee'])
        var_weapon_mint_timestamp_metric.labels(self.network).set(calls_multi['var_weapon_mint_timestamp'])
        var_character_mint_timestamp_metric.labels(self.network).set(calls_multi['var_character_mint_timestamp'])
        fight_xp_gain_metric.labels(self.network).set(calls_multi['fight_xp_gain'])
        mint_character_fee_usd_metric.labels(self.network).set(calls_multi_usd['mint_character_fee_usd'])
        mint_character_fee_dynamic_usd_metric.labels(self.network).set(calls_multi_usd['mint_character_fee_dynamic_usd'])
        mint_weapon_fee_usd_metric.labels(self.network).set(calls_multi_usd['mint_weapon_fee_usd'])
        mint_weapon_fee_dynamic_usd_metric.labels(self.network).set(calls_multi_usd['mint_weapon_fee_dynamic_usd'])
        reforge_weapon_fee_usd_metric.labels(self.network).set(calls_multi_usd['reforge_weapon_fee_usd'])
        reforge_weapon_with_dust_fee_usd_metric.labels(self.network).set(calls_multi_usd['reforge_weapon_with_dust_fee_usd'])
        burn_weapon_fee_usd_metric.labels(self.network).set(calls_multi_usd['burn_weapon_fee_usd'])
        weapon_burn_point_multiplier_metric.labels(self.network).set(calls_multi['weapon_burn_point_multiplier'])
        weapon_total_supply_metric.labels(self.network).set(calls_multi['weapon_total_supply'])
        character_total_supply_metric.labels(self.network).set(calls_multi['character_total_supply'])
        shield_total_supply_metric.labels(self.network).set(calls_multi['shield_total_supply'])
        raid_index_metric.labels(self.network).set(raid_data[0])
        raid_end_time_metric.labels(self.network).set(raid_data[1])
        raid_raider_count_metric.labels(self.network).set(raid_data[2])
        raid_player_power_metric.labels(self.network).set(raid_data[3])
        raid_boss_power_metric.labels(self.network).set(raid_data[4])
        raid_trait_metric.labels(self.network).set(raid_data[5])
        raid_status_metric.labels(self.network).set(raid_data[6])
        raid_join_skill_metric.labels(self.network).set(self.cb.ether(raid_data[7]))
        raid_stamina_metric.labels(self.network).set(raid_data[8])
        raid_durability_metric.labels(self.network).set(raid_data[9])
        raid_xp_metric.labels(self.network).set(raid_data[10])
        reward_pool_skill_metric.labels(self.network).set(calls_multi['reward_pool_skill'])
        bridge_pool_skill_metric.labels(self.network).set(calls_multi['bridge_pool_skill'])
        deployer_wallet_balance_metric.labels(self.network).set(deployer_wallet_balance)
        raid_bot_wallet_balance_metric.labels(self.network).set(raid_bot_wallet_balance)
        bridge_bot_wallet_balance_metric.labels(self.network).set(bridge_bot_wallet_balance)
        pvp_bot_wallet_balance_metric.labels(self.network).set(pvp_bot_wallet_balance)
        treasury_skill_remaining_supply_metric.labels(self.network).set(calls_multi['treasury_skill_remaining_supply'])
        if calls_multi['treasury_skill_remaining_supply'] > 0:
            treasury_skill_multiplier_metric.labels(self.network).set(calls_multi['treasury_skill_multiplier'])
        if self.network == 'bsc':
            tax_pool_king_metric.labels(self.network).set(calls_multi['tax_pool_king'])

        # pvp

        # if self.network != 'avax':
        #     pvp_matchable_player_count = Gauge('cb_pvp_matchable_player_count', 'getMatchablePlayerCount',
        #                                        ['network', 'pvp_tier'], registry=calls_registry)
        #     pvp_ranking_pool = Gauge('cb_pvp_ranking_pool', 'rankingsPoolByTier',
        #                              ['network', 'pvp_tier'], registry=calls_registry)
        #     pvp_queue = Gauge('cb_pvp_queue', 'getDuelQueue',
        #                       ['network'], registry=calls_registry)
        #     pvp_tax_coffer = Gauge('cb_pvp_tax_coffer', 'gameCofferTaxDue',
        #                            ['network'], registry=calls_registry)
        #     pvp_tiers = range(11)
        #     pvp_call_list = []
        #     for tier in pvp_tiers:
        #         pvp_call_list.append(Call(self.cb.pvp_address, ['getMatchablePlayerCount(uint256)(uint256)',
        #                                   self.cb.config['pvp_tiers'][tier]], [['match_' + str(tier), None]]))
        #         pvp_call_list.append(Call(self.cb.pvp_address, ['rankingsPoolByTier(uint8)(uint256)', tier],
        #                                   [['pool_' + str(tier), self.cb.ether]]))
        #     pvp_call_list.append(Call(self.cb.pvp_address, ['getDuelQueue()(uint256[])'], [['queue', len]]))
        #     pvp_call_list.append(Call(self.cb.pvp_address, ['gameCofferTaxDue()(uint256)'], [['tax', self.cb.ether]]))
        #     pvp_multi = Multicall(pvp_call_list, _w3=self.cb.w3, block_id=last_block)()
        #     for result in pvp_multi:
        #         if 'match_' in result:
        #             pvp_matchable_player_count.labels(self.network, result.split('match_')[1]).set(pvp_multi[result])
        #         elif 'pool_' in result:
        #             pvp_ranking_pool.labels(self.network, result.split('pool_')[1]).set(pvp_multi[result])
        #     pvp_queue.labels(self.network).set(pvp_multi['queue'])
        #     pvp_tax_coffer.labels(self.network).set(pvp_multi['tax'])

        print(self.network, last_block, 'MultiCall')
        return calls_registry

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
    network_list = ['bsc', 'heco', 'oec', 'poly', 'avax']
    run_threads()
