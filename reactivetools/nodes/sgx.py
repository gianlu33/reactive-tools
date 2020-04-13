import asyncio
import collections
import logging
import aiofile

from .server import ServerNode, _ReactiveCommand, Error


class SGXNode(ServerNode):
    async def deploy(self, module):
        async with aiofile.AIOFile(await module.sgxs, "rb") as f:
            sgxs = await f.read()

        async with aiofile.AIOFile(await module.sig, "rb") as f:
            sig = await f.read()


        payload =   self._pack_int(_ReactiveCommand.Load)       + \
                    self._pack_int32(len(sgxs))                 + \
                    sgxs                                        + \
                    self._pack_int32(len(sig))                  + \
                    sig

        await self._send_reactive_command(payload=payload)
        logging.info("Sent {} to {}".format(module.name, self.name))
