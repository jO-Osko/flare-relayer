import asyncio
import json
import logging
from typing import Any

from django.core.management import BaseCommand
from eth_abi import decode

from geth.client import GEthClient
from lib.constants import COSTON_RELAY

logger = logging.getLogger(__name__)

# TODO: save this better
# TODO: should we have contracts?
relayJsonF = open("lib/RelayGateway.json")
relayAbi = json.load(relayJsonF)["abi"]


async def listener():
    costonGeth = await GEthClient.__async_init__("Coston")
    # sepoliaGeth = await GEthClient.__async_init__("Sepolia")
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
                        decoded = decode(relayAbi, data)
                        print(decoded)

                    # pprint.pprint(tx)
                    # pprint.pprint(tx_rec)

        await asyncio.sleep(1)


# this goes directly, if the above has any errors
async def byHand():
    costonGeth = await GEthClient.__async_init__("Coston")
    # this one has call to Coston relayer
    block_nr = 12408899
    block = await costonGeth.geth.eth.get_block(block_nr, full_transactions=True)
    assert "transactions" in block
    for tx in block["transactions"]:
        if tx["to"] == COSTON_RELAY:
            tx_rec = await costonGeth.geth.eth.get_transaction_receipt(tx["hash"])

            logs = tx_rec("logs")
            for log in logs:
                data = log["data"]
                print(data)

                # TODO: this has never been checked
                decoded = decode(relayAbi, data)
                print(decoded)


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:
        logger.info("starting listener")

        asyncio.run(listener())
        # asyncio.run(byHand())
