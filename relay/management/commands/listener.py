import asyncio
import json
import logging
from typing import Any

from django.conf import settings
from django.core.management import BaseCommand
from eth_abi import decode
from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncWeb3
from web3.middleware.signing import async_construct_sign_and_send_raw_middleware

from geth.client import GEthClient
from lib.constants import COSTON_RELAY, SEPOLIA_RELAY

logger = logging.getLogger(__name__)

# TODO: save this better
# TODO: should we have contracts?
relayJsonF = open("lib/RelayGateway.json")
relayAbi = json.load(relayJsonF)["abi"]

reqRel = filter(lambda f: ("name" in f) and (f["name"] == "requestRelay"), relayAbi)
reqRelTypes = [val["type"] for val in list(reqRel)[0]["inputs"]]
reqRel = filter(lambda f: ("name" in f) and (f["name"] == "RelayExecuted"), relayAbi)
relExeTypes = [val["type"] for val in list(reqRel)[0]["inputs"]]

relExeCode = "RelayExecuted(uint256,address,address,bytes,address,address,uint256)"
relExeKeccak = "0x8d80bcc3460b53031d8aa27a772098820b942987d9c639cb66c8318541841e81"


async def listenerCoston():
    costonGeth = await GEthClient.__async_init__("Coston")
    last_block = await costonGeth.geth.eth.block_number

    # pprint.pprint(relayAbi)

    while True:
        logger.info("new listen")
        current_block = await costonGeth.geth.eth.block_number
        logger.info(f"block nr {current_block}")

        while last_block < current_block:
            block = await costonGeth.geth.eth.get_block(last_block, full_transactions=True)
            last_block += 1
            logger.info(f"checking block {last_block}")

            assert "transactions" in block
            for tx in block["transactions"]:
                if tx["to"] == COSTON_RELAY:
                    tx_rec = await costonGeth.geth.eth.get_transaction_receipt(tx["hash"])

                    logs = tx_rec["logs"]

                    for log in logs:
                        data = log["data"]
                        print(data)

                        # TODO: this has never been checked
                        decoded = decode(relExeTypes, data)

                        print(decoded)

                    # pprint.pprint(tx)
                    # pprint.pprint(tx_rec)

        await asyncio.sleep(1)


async def callOtherSide(callData):
    # Coston currently not working
    uid, relayInitiator, relayTarget, additionalCalldata, sourceToken, targetToken, amount = callData
    # relayInitiator = relayInitiator[2:]
    # relayTarget = relayTarget[2:]
    # sourceToken = sourceToken[2:]
    # targetToken = targetToken[2:]
    # print(targetToken)

    dataDict = {
        "uid": uid,
        "relayInitiator": relayInitiator,
        "relayTarget": relayTarget,
        "additionalCalldata": additionalCalldata,
        "sourceToken": sourceToken,
        "targetToken": targetToken,
        "amount": amount,
        "executionResult": 0,
        "relayDataHash": "0x" + "0" * 64,
    }

    callData = list(callData)
    callData[1] = AsyncWeb3.to_checksum_address(relayInitiator)
    callData[2] = AsyncWeb3.to_checksum_address(relayTarget)
    callData[4] = AsyncWeb3.to_checksum_address(sourceToken)
    callData[5] = AsyncWeb3.to_checksum_address(targetToken)

    data = tuple(callData + [0, "0x" + "0" * 64])

    costonGeth = await GEthClient.__async_init__("Sepolia")

    relayerContract = costonGeth.geth.eth.contract(SEPOLIA_RELAY, abi=relayAbi)
    # pprint.pprint(relayAbi)
    # return

    # decoded = relayerContract.decode_function_input(logData)
    # print(decoded)
    # print(relayerContract.events.RelayExecuted())

    ex = await relayerContract.caller.executeRelay(data).transact()
    # exCall = ex.call()
    # print(ex)
    # print(exCall)

    # function = relayerContract.get_function_by_name("executeRelay")
    # print(await relayerContract.get_function_by_name("executeRelay")(dataDict).call())

    # print(callData)

    # con = relayerContract.functions.executeRelay(
    #     [(uid, relayInitiator, relayTarget, additionalCalldata, sourceToken, targetToken, amount, 0, bytes(0))]
    # ).transact()
    # # con = relayerContract.functions.executeRelay(*callData)
    # print(con)


async def listenerSepolia():
    sepoliaGeth = await GEthClient.__async_init__("Sepolia")
    last_block = await sepoliaGeth.geth.eth.block_number

    # pprint.pprint(relayAbi)

    while True:
        logger.info("new listen")
        current_block = await sepoliaGeth.geth.eth.block_number

        while last_block < current_block:
            block = await sepoliaGeth.geth.eth.get_block(last_block, full_transactions=True)
            last_block += 1
            logger.info(f"checking block {last_block}")

            assert "transactions" in block
            for tx in block["transactions"]:
                if tx["to"] == SEPOLIA_RELAY:
                    tx_rec = await sepoliaGeth.geth.eth.get_transaction_receipt(tx["hash"])

                    logs = tx_rec["logs"]

                    for log in logs:
                        if log["topics"][0].hex() == relExeKeccak:
                            data = log["data"]
                            print(data)

                            # TODO: this has never been checked
                            callData = decode(relExeTypes, data)
                            print(callData)

                            await callOtherSide(callData)

                    # pprint.pprint(tx)
                    # pprint.pprint(tx_rec)

        await asyncio.sleep(1)


# this goes directly, if the above has any errors
async def byHand():
    # print(relExeTypes)
    sepoliaGeth = await GEthClient.__async_init__("Sepolia")
    account: LocalAccount = Account.from_key(settings.PRIVATE_KEY)
    sepoliaGeth.geth.middleware_onion.add(await async_construct_sign_and_send_raw_middleware(account))
    print("------------------------------")
    # this one has call to Coston relayer
    block_nr = 5393458
    block = await sepoliaGeth.geth.eth.get_block(block_nr, full_transactions=True)
    assert "transactions" in block
    for tx in block["transactions"]:
        # print(tx["to"])
        if tx["to"] == SEPOLIA_RELAY:
            # print(tx["hash"].hex())
            tx_rec = await sepoliaGeth.geth.eth.get_transaction_receipt(tx["hash"])
            print(tx["hash"].hex())

            logs = tx_rec["logs"]
            for log in logs:
                # print(log["topics"][0].hex())
                if log["topics"][0].hex() == relExeKeccak:

                    data = log["data"]
                    # print(data)
                    callData = decode(relExeTypes, data)
                    print(callData)

                    await callOtherSide(callData)


async def testing():

    for f in relayAbi:
        if ("name" in f) and (f["name"] == "requestRelay"):
            print(f)
            print("--------")
            print(f["inputs"])
            types = [val["type"] for val in f["inputs"]]
            print(types)

        # for name in f:
        #     print(name)
        #     print(f[name])
        #     print(f["name"])
        #     # print("-----------------------------------------------")
        #     # if f["name"] == "requestRelay":
        #     #     pprint.pprint(f)


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:

        logger.info("starting listener")

        # asyncio.run(listenerSepolia())
        # asyncio.run(listenerCoston())
        asyncio.run(byHand())
        # asyncio.run(testing())
