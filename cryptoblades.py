import json

import yaml
from web3 import Web3
from web3.middleware import geth_poa_middleware


class Cryptoblades:
    def __init__(self, network, path=None, fallback=False):
        with open('config.yaml') as f:
            config = yaml.full_load(f)
        if network == 'bsc':
            self.config = config['bsc']
        elif network == 'heco':
            self.config = config['heco']
        elif network == 'oec':
            self.config = config['oec']
        elif network == 'poly':
            self.config = config['poly']
        elif network == 'avax':
            self.config = config['avax']
        else:
            raise TypeError(f'Wrong network {network}')
        if path is not None:
            self.w3 = Web3(Web3.IPCProvider(path))
        elif not fallback:
            self.w3 = Web3(Web3.HTTPProvider(self.config['path_http']))
        else:
            self.w3 = Web3(Web3.HTTPProvider(self.config['path_http_fallback']))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        # cryptoblades
        self.cryptoblades_address = self.w3.toChecksumAddress(self.config['cryptoblades_address'])
        with open(config['abi']['cryptoblades']) as f:
            self.cryptoblades_abi = json.loads(f.read())
        self.cryptoblades_contract = self.w3.eth.contract(address=self.cryptoblades_address, abi=self.cryptoblades_abi)
        # weapons
        self.weapons_address = self.w3.toChecksumAddress(self.config['weapons_address'])
        with open(config['abi']['weapons']) as f:
            self.weapons_abi = json.loads(f.read())
        self.weapons_contract = self.w3.eth.contract(address=self.weapons_address, abi=self.weapons_abi)
        # characters
        self.characters_address = self.w3.toChecksumAddress(self.config['characters_address'])
        with open(config['abi']['characters']) as f:
            self.characters_abi = json.loads(f.read())
        self.characters_contract = self.w3.eth.contract(address=self.characters_address, abi=self.characters_abi)
        # shields
        self.shields_address = self.w3.toChecksumAddress(self.config['shields_address'])
        with open(config['abi']['shields']) as f:
            self.shields_abi = json.loads(f.read())
        self.shields_contract = self.w3.eth.contract(address=self.shields_address, abi=self.shields_abi)
        # market
        self.market_address = self.w3.toChecksumAddress(self.config['market_address'])
        with open(config['abi']['market']) as f:
            self.market_abi = json.loads(f.read())
        self.market_contract = self.w3.eth.contract(address=self.market_address, abi=self.market_abi)
        # raid
        self.raid_address = self.w3.toChecksumAddress(self.config['raid_address'])
        with open(config['abi']['raid']) as f:
            self.raid_abi = json.loads(f.read())
        self.raid_contract = self.w3.eth.contract(address=self.raid_address, abi=self.raid_abi)
        # skill
        self.skill_address = self.w3.toChecksumAddress(self.config['skill_address'])
        with open(config['abi']['skill']) as f:
            self.skill_abi = json.loads(f.read())
        self.skill_contract = self.w3.eth.contract(address=self.skill_address, abi=self.skill_abi)
        # treasury
        self.treasury_address = self.w3.toChecksumAddress(self.config['treasury_address'])
        with open(config['abi']['treasury']) as f:
            self.treasury_abi = json.loads(f.read())
        self.treasury_contract = self.w3.eth.contract(address=self.treasury_address, abi=self.treasury_abi)
        # pvp
        self.pvp_address = self.w3.toChecksumAddress(self.config['pvp_address'])
        with open(config['abi']['pvp']) as f:
            self.pvp_abi = json.loads(f.read())
        self.pvp_contract = self.w3.eth.contract(address=self.pvp_address, abi=self.pvp_abi)
        # quests
        self.quests_address = self.w3.toChecksumAddress(self.config['quests_address'])
        with open(config['abi']['quests']) as f:
            self.quests_abi = json.loads(f.read())
        self.quests_contract = self.w3.eth.contract(address=self.quests_address, abi=self.quests_abi)
        # bridge
        self.bridge_address = self.w3.toChecksumAddress(self.config['bridge_address'])
        # deployer
        self.deployer_address = self.w3.toChecksumAddress(self.config['deployer_address'])
        # raid_bot
        self.raid_bot_address = self.w3.toChecksumAddress(self.config['raid_bot_address'])
        # bridge_bot
        self.bridge_bot_address = self.w3.toChecksumAddress(self.config['bridge_bot_address'])
        # pvp_bot
        self.pvp_bot_address = self.w3.toChecksumAddress(self.config['pvp_bot_address'])
        # skill_treasury
        self.treasury_skill_id = self.config['treasury_skill_id']
        if network == 'bsc':
            # king
            self.king_address = self.w3.toChecksumAddress(self.config['king_address'])
            with open(config['abi']['king']) as f:
                self.king_abi = json.loads(f.read())
            self.king_contract = self.w3.eth.contract(address=self.king_address, abi=self.king_abi)
            # king tax
            self.king_tax_address = self.w3.toChecksumAddress(self.config['king_tax_address'])

    def get_wallet_balance(self, address):
        return self.w3.eth.getBalance(self.w3.toChecksumAddress(address))

    def get_latest_block_number(self):
        return self.w3.eth.block_number

    def get_block_by_number(self, block_number):
        return self.w3.eth.get_block(block_number, full_transactions=True)

    def decode_input_market(self, txn_input):
        return self.market_contract.decode_function_input(txn_input)

    def decode_input_cryptoblades(self, txn_input):
        return self.cryptoblades_contract.decode_function_input(txn_input)

    def get_vars(self, var, block='latest'):
        return self.cryptoblades_contract.functions.vars(var).call(block_identifier=block)

    def get_raid_data(self, block='latest'):
        return self.raid_contract.functions.getRaidData().call(block_identifier=block)

    def get_character_total_supply(self, block='latest'):
        return self.characters_contract.functions.totalSupply().call(block_identifier=block)

    def get_character_level(self, character_id, block='latest'):
        return self.characters_contract.functions.getLevel(character_id).call(block_identifier=block)

    def get_character_vars(self, character_id, var):
        return self.characters_contract.functions.nftVars(character_id, var).call()

    def get_weapon_total_supply(self, block='latest'):
        return self.weapons_contract.functions.totalSupply().call(block_identifier=block)

    def get_weapon_burn_point_multiplier(self, block='latest'):
        return self.weapons_contract.functions.burnPointMultiplier().call(block_identifier=block)

    def get_mint_character_fee(self, block='latest'):
        return self.cryptoblades_contract.functions.mintCharacterFee().call(block_identifier=block)

    def get_mint_weapon_fee(self, block='latest'):
        return self.cryptoblades_contract.functions.mintWeaponFee().call(block_identifier=block)

    def get_reforge_weapon_with_dust_fee(self, block='latest'):
        return self.cryptoblades_contract.functions.reforgeWeaponWithDustFee().call(block_identifier=block)

    def get_burn_weapon_fee(self, block='latest'):
        return self.cryptoblades_contract.functions.burnWeaponFee().call(block_identifier=block)

    def get_reforge_weapon_fee(self, block='latest'):
        return self.cryptoblades_contract.functions.reforgeWeaponFee().call(block_identifier=block)

    def get_fight_xp_gain(self, block='latest'):
        return self.cryptoblades_contract.functions.fightXpGain().call(block_identifier=block)

    def get_market_tax(self, block='latest'):
        return self.market_contract.functions.defaultTax().call(block_identifier=block)

    def get_target_buyer(self, token_address, token_id):
        return self.market_contract.functions.getTargetBuyer(self.w3.toChecksumAddress(token_address), token_id).call()

    def check_market_ban(self, user_address):
        return self.market_contract.functions.isUserBanned(self.w3.toChecksumAddress(user_address)).call()

    def get_seller_price(self, token_address, token_id):
        return self.market_contract.functions.getSellerPrice(self.w3.toChecksumAddress(token_address), token_id).call()

    def get_character_stats(self, character_id, block='latest'):
        return self.characters_contract.functions.get(character_id).call(block_identifier=block)

    def get_character_stamina(self, character_id, block='latest'):
        return self.characters_contract.functions.getStaminaPoints(character_id).call(block_identifier=block)

    def get_character_power(self, character_id, block='latest'):
        return self.characters_contract.functions.getPower(character_id).call(block_identifier=block)

    def get_character_total_power(self, character_id, block='latest'):
        return self.characters_contract.functions.getTotalPower(character_id).call(block_identifier=block)

    def get_unclaimed_exp(self, character_id, block='latest'):
        return self.cryptoblades_contract.functions.getXpRewards([character_id]).call(block_identifier=block)[0]

    def get_weapon_trait(self, weapon_id, block='latest'):
        return self.weapons_contract.functions.getTrait(weapon_id).call(block_identifier=block)

    def get_weapon_stars(self, weapon_id, block='latest'):
        return self.weapons_contract.functions.getStars(weapon_id).call(block_identifier=block)

    def get_weapon_fight_data(self, weapon_id, character_trait, block='latest'):
        return self.weapons_contract.functions.getFightData(weapon_id, character_trait).call(block_identifier=block)

    def get_weapon_stats(self, weapon_id, block='latest'):
        return self.weapons_contract.functions.get(weapon_id).call(block_identifier=block)

    def get_weapon_pattern(self, weapon_id, block='latest'):
        return self.weapons_contract.functions.getStatPattern(weapon_id).call(block_identifier=block)

    def get_shield_stars(self, shield_id, block='latest'):
        return self.shields_contract.functions.getStars(shield_id).call(block_identifier=block)

    def get_shield_fight_data(self, shield_id, character_trait, block='latest'):
        return self.shields_contract.functions.getFightData(shield_id, character_trait).call(block_identifier=block)

    def get_shield_trait(self, shield_id, block='latest'):
        return self.shields_contract.functions.getTrait(shield_id).call(block_identifier=block)

    def get_shield_stats(self, shield_id, block='latest'):
        return self.shields_contract.functions.get(shield_id).call(block_identifier=block)

    def get_shield_pattern(self, shield_id, block='latest'):
        return self.shields_contract.functions.getStatPattern(shield_id).call(block_identifier=block)

    def get_skill_balance(self, address, block='latest'):
        return self.skill_contract.functions.balanceOf(self.w3.toChecksumAddress(address)).call(block_identifier=block)

    def get_treasury_multiplier(self, project_id, block='latest'):
        return self.treasury_contract.functions.getProjectMultiplier(project_id).call(block_identifier=block)

    def get_treasury_remaining_supply(self, project_id, block='latest'):
        return self.treasury_contract.functions.getRemainingPartnerTokenSupply(project_id).call(block_identifier=block)

    def get_quests(self, quest_id, block='latest'):
        return self.quests_contract.functions.quests(quest_id).call(block_identifier=block)

    def ether(self, wei: int) -> float:
        return float(self.w3.fromWei(wei, 'ether'))

    def wei(self, ether: float) -> int:
        return int(self.w3.toWei(ether, 'ether'))

    def gwei(self, ether: float) -> int:
        return int(self.w3.toWei(ether, 'gwei'))
