import asyncio
import logging
from abc import ABC, abstractmethod
import base64
import contextlib
import binascii

from reactivenet import *

from .base import Node
from ..connection import ConnectionIO
from .. import glob
from .. import tools

class Error(Exception):
    pass


class SGXBase(Node):
    def __init__(self, name, ip_address, reactive_port, deploy_port):
        super().__init__(name, ip_address, reactive_port, deploy_port)

        self.__moduleid = 1


    @abstractmethod
    async def deploy(self, module):
        pass


    async def connect(self, from_module, from_output, to_module, to_input):
        assert from_module.node is self

        results = await asyncio.gather(from_module.get_id(),
                                       from_module.get_output_id(from_output),
                                       to_module.get_id(),
                                       to_module.get_input_id(to_input))

        from_module_id, from_output_id, to_module_id, to_input_id = results

        payload = tools.pack_int16(from_module_id)                    + \
                  tools.pack_int16(from_output_id)                    + \
                  tools.pack_int16(to_module_id)                      + \
                  tools.pack_int16(to_input_id)                       + \
                  tools.pack_int16(to_module.node.reactive_port)      + \
                  to_module.node.ip_address.packed

        command = CommandMessage(ReactiveCommand.Connect,
                                Message.new(payload),
                                self.ip_address,
                                self.reactive_port)

        await self._send_reactive_command(
                command,
                log='Connecting {}:{} to {}:{} on {}'.format(
                 from_module.name, from_output,
                 to_module.name, to_input,
                 self.name)
                )


    async def set_key(self, module, io_name, encryption, key, conn_io):
        assert module.node is self
        assert encryption in module.get_supported_encryption()
        await module.deploy()

        if conn_io == ConnectionIO.OUTPUT:
            io_id = await module.get_output_id(io_name)
        else:
            io_id = await module.get_input_id(io_name)

        nonce = self._get_nonce(module)

        # encrypting key
        args = [str(encryption.value), str(io_id), str(nonce), base64.b64encode(key).decode(),
            base64.b64encode(await module.key).decode()]

        out = await tools.run_async_output(glob.ENCRYPTOR, *args)

        cipher = base64.b64decode(out)

        payload =   tools.pack_int16(module.id)                     + \
                    tools.pack_int16(ReactiveEntrypoint.SetKey)     + \
                    tools.pack_int8(encryption)                     + \
                    tools.pack_int16(io_id)                         + \
                    tools.pack_int16(nonce)                         + \
                    cipher

        command = CommandMessage(ReactiveCommand.Call,
                                Message.new(payload),
                                self.ip_address,
                                self.reactive_port)

        await self._send_reactive_command(
                command,
                log='Setting key of {}:{} on {} to {}'.format(
                     module.name, io_name, self.name,
                     binascii.hexlify(key).decode('ascii'))
                )


    async def call(self, module, entry, arg=None):
        assert module.node is self
        module_id = module.id
        entry_id = await module.get_entry_id(entry)

        payload = tools.pack_int16(module_id)       + \
                  tools.pack_int16(entry_id)        + \
                  (b'' if arg is None else arg)

        command = CommandMessage(ReactiveCommand.Call,
                                Message.new(payload),
                                self.ip_address,
                                self.reactive_port)

        await self._send_reactive_command(
                command,
                log='Sending call command to {}:{} ({}:{}) on {}'.format(
                     module.name, entry, module_id, entry_id, self.name)
                )


    def get_module_id(self):
        id = self.__moduleid
        self.__moduleid += 1

        return id
