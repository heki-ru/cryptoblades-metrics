import json

import yaml
from web3 import Web3
from web3.middleware import geth_poa_middleware


class Cryptoblades:
    def __init__(self, network, path=None, fallback=False):
        with open('./config.yaml') as f:
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
        with open(config['cryptoblades_abi']) as f:
            self.cryptoblades_abi = json.loads(f.read())
        self.cryptoblades_contract = self.w3.eth.contract(address=self.cryptoblades_address, abi=self.cryptoblades_abi)
        # weapons
        self.weapons_address = self.w3.toChecksumAddress(self.config['weapons_address'])
        with open(config['weapons_abi']) as f:
            self.weapons_abi = json.loads(f.read())
        self.weapons_contract = self.w3.eth.contract(address=self.weapons_address, abi=self.weapons_abi)
        # characters
        self.characters_address = self.w3.toChecksumAddress(self.config['characters_address'])
        with open(config['characters_abi']) as f:
            self.characters_abi = json.loads(f.read())
        self.characters_contract = self.w3.eth.contract(address=self.characters_address, abi=self.characters_abi)
        # raid
        self.raid_address = self.w3.toChecksumAddress(self.config['raid_address'])
        with open(config['raid_abi']) as f:
            self.raid_abi = json.loads(f.read())
        self.raid_contract = self.w3.eth.contract(address=self.raid_address, abi=self.raid_abi)
        # oracle
        self.oracle_address = self.w3.toChecksumAddress(self.config['oracle_address'])
        with open(config['oracle_abi']) as f:
            self.oracle_abi = json.loads(f.read())
        self.oracle_contract = self.w3.eth.contract(address=self.oracle_address, abi=self.oracle_abi)

    def get_vars(self, var, block='latest'):
        return self.cryptoblades_contract.functions.vars(var).call(block_identifier=block)

    def get_raid_data(self, block='latest'):
        return self.raid_contract.functions.getRaidData().call(block_identifier=block)

    def get_oracle_price(self, block='latest'):
        return self.oracle_contract.functions.currentPrice().call(block_identifier=block)

    def get_character_total_supply(self, block='latest'):
        return self.characters_contract.functions.totalSupply().call(block_identifier=block)

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
