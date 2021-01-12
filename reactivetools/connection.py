import asyncio
import logging
from enum import IntEnum

from .crypto import Encryption

class Error(Exception):
    pass

class Connection:
    cnt = 0

    def __init__(self, from_module, from_output, to_module, to_input,
                    encryption, key, id, direct, nonce):
        self.from_module = from_module
        self.from_output = from_output
        self.to_module = to_module
        self.to_input = to_input
        self.encryption = encryption
        self.key = key
        self.id = id
        self.direct = direct
        self.nonce = nonce

    async def establish(self):
        if self.direct:
            await self.__establish_direct()
        else:
            await self.__establish_normal()


    async def __establish_normal(self):
        from_node, to_node = self.from_module.node, self.to_module.node

        # TODO check if the module is the same: if so, abort!

        connect = from_node.connect(self.to_module, self.id)
        set_key_from = from_node.set_key(self.from_module, self.id, self.from_output,
                                     self.encryption, self.key, ConnectionIO.OUTPUT)
        set_key_to = to_node.set_key(self.to_module, self.id, self.to_input,
                                     self.encryption, self.key, ConnectionIO.INPUT)

        await asyncio.gather(connect, set_key_from, set_key_to)

        logging.info('Connection %d from %s:%s on %s to %s:%s on %s established',
                     self.id, self.from_module.name, self.from_output, from_node.name,
                     self.to_module.name, self.to_input, to_node.name)


    async def __establish_direct(self):
        to_node = self.to_module.node

        await to_node.set_key(self.to_module, self.id, self.to_input,
                                     self.encryption, self.key, ConnectionIO.INPUT)

        logging.info('Direct connection %d to %s:%s on %s established',
                     self.id, self.to_module.name, self.to_input, to_node.name)


    @staticmethod
    def get_connection_id():
        id = Connection.cnt
        Connection.cnt += 1
        return id


class ConnectionIO(IntEnum):
    OUTPUT  = 0x0
    INPUT   = 0x1
