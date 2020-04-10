import asyncio
import collections
import logging

from .server import ServerNode, _ReactiveCommand, Error


class NoSGXNode(ServerNode):
    async def deploy(self, module):
        logging.info("Sending {} to {}".format(module.name, self.name))

        with open(module.binary, "rb") as f: # TODO async?
            binary = f.read()

        payload =   self._pack_int(_ReactiveCommand.Load)    + \
                    self._pack_int32(len(binary))            + \
                    binary

        await self._send_reactive_command(payload=payload)
