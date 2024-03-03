import asyncio
import json
import logging
from typing import Any

from django.conf import settings
from django.core.management import BaseCommand
from django.core.management.base import CommandParser
from eth_abi import decode
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.middleware.signing import async_construct_sign_and_send_raw_middleware

from abis.constants import COSTON_RELAY, SEPOLIA_RELAY
from geth.client import GEthClient

logger = logging.getLogger(__name__)

relayAbi = json.load(open("abis/RelayGateway.json"))["abi"]
erc20abi = json.load(open("abis/ERC20abi.json"))

reqRel = filter(lambda f: ("name" in f) and (f["name"] == "requestRelay"), relayAbi)
reqRelTypes = [val["type"] for val in list(reqRel)[0]["inputs"]]
reqRel = filter(lambda f: ("name" in f) and (f["name"] == "RelayExecuted"), relayAbi)
relExeTypes = [val["type"] for val in list(reqRel)[0]["inputs"]]

relExeCode = "RelayExecuted(uint256,address,address,bytes,address,address,uint256)"
relayReqTopic = "0x4599a14afb01d51b75540a961262ad1157de6ef44f1780ef686af91fef984be7"


async def callOtherSide(callData, chain: str):
    relayAddr = SEPOLIA_RELAY if chain == "sepolia" else COSTON_RELAY

    uid, relayInitiator, relayTarget, additionalCalldata, sourceToken, targetToken, amount = callData

    EMPTY_BYTES = "0x" + "0" * 64

    callDataDict = {
        "uid": uid,
        "relayInitiator": AsyncWeb3.to_checksum_address(relayInitiator),
        "relayTarget": AsyncWeb3.to_checksum_address(relayTarget),
        "additionalCalldata": additionalCalldata,
        "sourceToken": AsyncWeb3.to_checksum_address(sourceToken),
        "targetToken": AsyncWeb3.to_checksum_address(targetToken),
        "amount": amount,
        "executionResult": 0,
        "relayDataHash": EMPTY_BYTES,
    }

    gethClient = await GEthClient.__async_init__(chain)
    account: LocalAccount = Account.from_key(settings.PRIVATE_KEY)
    gethClient.geth.middleware_onion.add(await async_construct_sign_and_send_raw_middleware(account))

    transaction = {
        "from": account.address,
    }

    erc20contract = gethClient.geth.eth.contract(callDataDict["targetToken"], abi=erc20abi)

    tx_hash = await erc20contract.functions.transfer(relayAddr, amount).transact(transaction)

    await gethClient.geth.eth.wait_for_transaction_receipt(tx_hash)

    print("Allowance tx hash: ", tx_hash.hex())

    transaction = {
        "from": account.address,
    }

    relayerContract = gethClient.geth.eth.contract(relayAddr, abi=relayAbi)  # type: ignore

    ex = await relayerContract.functions.executeRelay(callDataDict).transact(transaction)
    print("Execute relay hash: ", ex.hex())


async def listener(chain: str):
    gethClient = await GEthClient.__async_init__(chain)
    last_block = await gethClient.geth.eth.block_number
    relayAddr = SEPOLIA_RELAY if chain == "sepolia" else COSTON_RELAY

    to_chain = "coston" if chain == "sepolia" else "sepolia"

    while True:
        current_block = await gethClient.geth.eth.block_number

        while last_block < current_block:
            block = await gethClient.geth.eth.get_block(last_block, full_transactions=True)
            last_block += 1
            logger.info(f"Checking block: {last_block}")

            assert "transactions" in block
            for tx in block["transactions"]:
                if tx["to"] == relayAddr:  # type: ignore
                    tx_rec = await gethClient.geth.eth.get_transaction_receipt(tx["hash"])  # type: ignore
                    logs = tx_rec["logs"]

                    for log in logs:
                        if log["topics"][0].hex() == relayReqTopic:
                            logger.info("Found new relay")
                            data = log["data"]

                            # TODO: this has never been checked
                            callData = decode(relExeTypes, data)

                            await callOtherSide(callData, to_chain)

        await asyncio.sleep(1)


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("chain", nargs=1, type=str)

    def handle(self, *args: Any, **options: Any) -> str | None:
        logger.info("Starting listener")

        asyncio.run(listener(options["chain"][0]))
