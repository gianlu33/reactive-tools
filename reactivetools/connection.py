from collections import namedtuple
import asyncio
import logging
from enum import IntEnum


class Connection(namedtuple('Connection', ['from_module', 'from_output',
                                           'to_module', 'to_input',
                                           'key'])):
    async def establish(self):
        from_node, to_node = self.from_module.node, self.to_module.node

        connect = from_node.connect(self.from_module, self.from_output,
                                    self.to_module, self.to_input)
        set_key_from = from_node.set_key(self.from_module, self.from_output,
                                         self.key, ConnectionIO.OUTPUT)
        set_key_to = to_node.set_key(self.to_module, self.to_input, self.key, ConnectionIO.INPUT)

        await asyncio.gather(connect, set_key_from, set_key_to)

        logging.info('Connection from %s:%s on %s to %s:%s on %s established',
                     self.from_module.name, self.from_output, from_node.name,
                     self.to_module.name, self.to_input, to_node.name)


class ConnectionIO(IntEnum):
    OUTPUT  = 0x0
    INPUT   = 0x1
