import asyncio
import aiofile

from reactivenet import Message, CommandMessage, ReactiveCommand

from .sgxbase import SGXBase
from .. import tools


class SGXNode(SGXBase):
    async def deploy(self, module):
        async with aiofile.AIOFile(await module.sgxs, "rb") as f:
            sgxs = await f.read()

        async with aiofile.AIOFile(await module.sig, "rb") as f:
            sig = await f.read()


        payload =   tools.pack_int16(_ReactiveCommand.Load)         + \
                    tools.pack_int32(len(sgxs))                     + \
                    sgxs                                            + \
                    tools.pack_int32(len(sig))                      + \
                    sig

        command = CommandMessage(ReactiveCommand.Load,
                                Message.new(payload),
                                self.ip_address,
                                self.deploy_port)

        await self._send_reactive_command(
            command,
            log='Deploying {} on {}'.format(module.name, self.name)
            )
