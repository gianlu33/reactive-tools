import asyncio
import collections
import logging

from .server import ServerNode

class SGXNode(ServerNode):
    async def deploy(self, module):
        logging.error("Not implemented")
