import asyncio
import logging
from typing import Any

from django.core.management import BaseCommand

from geth.client import GEthClient

logger = logging.getLogger(__name__)


async def async3():
    geth = await GEthClient.__async_init__()

    bl = await geth.geth.eth.get_block(7893338, full_transactions=True)
    assert "transactions" in bl
    # print(bl["transactions"])
    tx = bl["transactions"][3]

    tx_rec = await geth.geth.eth.get_transaction_receipt(tx["hash"])
    print("transaction receipt fields --------------------------------")
    for k in tx_rec:
        print(k)
    tx = await geth.geth.eth.get_transaction(tx["hash"])
    print("transaction fields -------------------------------------")
    for k in tx:
        print(k)

    for i, _ in enumerate(bl["transactions"]):
        print(bl["transactions"][i]["input"].hex()[:10])

    trace = await geth.debug_traceTransaction(tx["hash"])

    print(trace)


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:
        logger.info("running learning command")

        asyncio.run(async3())
