import asyncio
import json
import logging
import random

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3.middleware.signing import async_construct_sign_and_send_raw_middleware

from abis.constants import COSTON_RELAY, SEPOLIA_RELAY
from geth.client import GEthClient

logger = logging.getLogger(__name__)

relayAbi = json.load(open("abis/RelayGateway.json"))["abi"]
erc20abi = json.load(open("abis/ERC20abi.json"))


async def txSpammer(chain: str):
    # Same idea works for another part of the relay
    gethClient = await GEthClient.__async_init__(chain)
    relayAddr = SEPOLIA_RELAY if chain == "sepolia" else COSTON_RELAY

    account: LocalAccount = Account.from_key(settings.PRIVATE_KEY)
    gethClient.geth.middleware_onion.add(await async_construct_sign_and_send_raw_middleware(account))

    transaction = {
        "from": account.address,
    }

    # Get random token
    tokenId = random.randint(0, 10)

    relayer_contract = gethClient.geth.eth.contract(relayAddr, abi=relayAbi)  # type: ignore

    # We just call it to get the result
    token_address: str = await relayer_contract.functions.availableTokens(tokenId).call()
    print("Token address: ", token_address)

    # We allow the contract to later take our tokens
    amount_to_send = 123
    erc20contract = gethClient.geth.eth.contract(token_address, abi=erc20abi)  # type: ignore
    tx = await erc20contract.functions.approve(relayAddr, amount_to_send).transact(transaction)

    # Wait for some time
    # TODO urban: https://web3py.readthedocs.io/en/stable/web3.eth.html#web3.eth.Eth.get_transaction_receipt
    await gethClient.geth.eth.wait_for_transaction_receipt(tx)

    print("Allowance tx_hash:", tx.hex())
    request_tx_hash = await relayer_contract.functions.requestRelay(
        account.address,  # Target is me on the other side - to make it easier to return the transaction
        "0x",  # Empty calldata for now
        token_address,  # Token address the source token - the other side is calculated on contract
        amount_to_send,
    ).transact(transaction)

    print("Request relay hash: ", request_tx_hash.hex())


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("chain", nargs=1, type=str)

    def handle(self, *args, **options):
        asyncio.run(txSpammer(options["chain"][0]))
