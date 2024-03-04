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

from geth.client import GEthClient
from relay.models import Block

logger = logging.getLogger(__name__)

relayAbi = json.load(open("abis/RelayABI.json"))
erc20Abi = json.load(open("abis/ERC20ABI.json"))
counterAbi = json.load(open("abis/CounterABI.json"))

relExe = filter(lambda f: ("name" in f) and (f["name"] == "RelayExecuted"), relayAbi)
relExeTypes = [val["type"] for val in next(iter(relExe))["inputs"]]

setCounter = filter(lambda f: ("name" in f) and (f["name"] == "setCounter"), counterAbi)
setCounterTypes = [val["type"] for val in next(iter(setCounter))["inputs"]]

relExeCode = "RelayExecuted(uint256,address,address,bytes,address,address,uint256)"
relayReqTopic = "0x4599a14afb01d51b75540a961262ad1157de6ef44f1780ef686af91fef984be7"


async def callOtherSide(callData, chain: str):
    relayAddr = settings.SEPOLIA_RELAY if chain == "sepolia" else settings.COSTON_RELAY

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

    erc20contract = gethClient.geth.eth.contract(callDataDict["targetToken"], abi=erc20Abi)

    tx_hash = await erc20contract.functions.transfer(relayAddr, amount).transact(transaction)

    await gethClient.geth.eth.wait_for_transaction_receipt(tx_hash)

    print("Allowance tx hash: ", tx_hash.hex())

    transaction = {
        "from": account.address,
    }
    counterAddr = settings.SEPOLIA_COUNTER if chain == "sepolia" else settings.COSTON_COUNTER
    counterContract = gethClient.geth.eth.contract(counterAddr, abi=counterAbi)
    counter = await counterContract.functions.getCounter().call()
    print("CURRENT COUNTER : ", counter)
    print(chain, "-----------")
    relayerContract = gethClient.geth.eth.contract(relayAddr, abi=relayAbi)  # type: ignore
    ex = await relayerContract.functions.executeRelay(callDataDict).transact(transaction)
    print("Execute relay hash: ", ex.hex())

    # reads current counter
    counter = await counterContract.functions.getCounter().call()
    print("CURRENT COUNTER : ", counter)

    otherCounterAddr = settings.COSTON_COUNTER if chain == "sepolia" else settings.SEPOLIA_COUNTER
    otherClient = await GEthClient.__async_init__("coston" if chain == "sepolia" else "sepolia")
    otherCounterContract = otherClient.geth.eth.contract(otherCounterAddr, abi=counterAbi)
    otherCounter = await otherCounterContract.functions.getCounter().call()
    print(otherCounter)

    # callData = decode(setCounterTypes, additionalCalldata)
    # dataList = [
    #     callData[0],
    #     AsyncWeb3.to_checksum_address(callData[1]),
    #     callData[2],
    #     AsyncWeb3.to_checksum_address(callData[3]),
    # ]
    # print("data List: ", dataList)
    # exCounter = await counterContract.functions.setCounter(*dataList).call()
    # print("Counter hash: ", exCounter.hex())

    # counter = await counterContract.functions.getCounter().call()
    # print("CURRENT COUNTER : ", counter)


async def listener(chain: str):
    gethClient = await GEthClient.__async_init__(chain)
    last_block, created = await Block.objects.aget_or_create(chain=chain, defaults={"number": 0, "timestamp": 0})
    if created:
        last_block.number = await gethClient.geth.eth.block_number
    relayAddr = settings.SEPOLIA_RELAY if chain == "sepolia" else settings.COSTON_RELAY

    to_chain = "coston" if chain == "sepolia" else "sepolia"

    while True:
        current_block_n = await gethClient.geth.eth.block_number

        while last_block.number < current_block_n:
            block = await gethClient.geth.eth.get_block(last_block.number, full_transactions=True)
            logger.info(f"Checking block: {last_block.number}")

            assert "transactions" in block
            for tx in block["transactions"]:
                if tx["to"] == relayAddr:  # type: ignore
                    tx_rec = await gethClient.geth.eth.get_transaction_receipt(tx["hash"])  # type: ignore
                    logs = tx_rec["logs"]

                    for log in logs:
                        if log["topics"][0].hex() == relayReqTopic:
                            logger.info("Found new relay")
                            data = log["data"]

                            callData = decode(relExeTypes, data)

                            await callOtherSide(callData, to_chain)
            last_block.number += 1
            await last_block.asave()
        await asyncio.sleep(1)


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("chain", nargs=1, type=str)

    def handle(self, *args: Any, **options: Any) -> str | None:
        logger.info("Starting listener")

        assert options["chain"][0] in ["sepolia", "coston"], "Chain name is incorrect"

        asyncio.run(listener(options["chain"][0]))
