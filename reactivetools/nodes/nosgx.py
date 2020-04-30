import asyncio
import collections
import logging
import aiofile

from .sgxbase import SGXBase, Error
from .base import ReactiveCommand

class NoSGXNode(SGXBase):
    async def deploy(self, module):
        async with aiofile.AIOFile(await module.binary, "rb") as f:
            binary = await f.read()

        payload =   self._pack_int16(ReactiveCommand.Load)    + \
                    self._pack_int32(len(binary))             + \
                    binary

        await self._send_reactive_command(payload=payload)
        logging.info("Sent {} to {}".format(module.name, self.name))
