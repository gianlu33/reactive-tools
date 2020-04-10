import asyncio
import collections
import logging

from .server import ServerNode, _ReactiveCommand, Error


class SGXNode(ServerNode):
    async def deploy(self, module):
        logging.info("Sending {} to {}".format(module.name, self.name))

        with open(module.sgxs, "rb") as f: # TODO async?
            sgxs = f.read()

        with open(module.sig, "rb") as f: # TODO async?
            sig = f.read()


        payload =   self._pack_int(_ReactiveCommand.Load)       + \
                    self._pack_int32(len(sgxs))                 + \
                    sgxs                                        + \
                    self._pack_int32(len(sig))                  + \
                    sig

        await self._send_reactive_command(payload=payload)
