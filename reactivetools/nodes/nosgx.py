import asyncio
import aiofile

from reactivenet import CommandMessageLoad

from .sgxbase import SGXBase
from .. import tools


class NoSGXNode(SGXBase):
    async def deploy(self, module):
        async with aiofile.AIOFile(await module.binary, "rb") as f:
            binary = await f.read()

        payload =   tools.pack_int32(len(binary))             + \
                    binary

        command = CommandMessageLoad(payload,
                                self.ip_address,
                                self.deploy_port)

        await self._send_reactive_command(
            command,
            log='Deploying {} on {}'.format(module.name, self.name)
            )
