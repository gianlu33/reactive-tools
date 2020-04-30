import asyncio
import collections
import logging
from abc import ABC, abstractmethod
import struct
from enum import IntEnum
import base64
import contextlib

from .base import Node, ReactiveCommand, ReactiveResultCode, ReactiveResult

from ..connection import ConnectionIO
from .. import glob
from .. import tools

class Error(Exception):
    pass


class SGXBase(Node):
    def __init__(self, name, ip_address, reactive_port, deploy_port):
        super().__init__(name, ip_address, reactive_port, deploy_port)

        self.__nonces = collections.Counter()
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

        payload = self._pack_int16(from_module_id)                    + \
                  self._pack_int16(from_output_id)                    + \
                  self._pack_int16(to_module_id)                      + \
                  self._pack_int16(to_input_id)                       + \
                  self._pack_int16(to_module.node.reactive_port)      + \
                  to_module.node.ip_address.packed

        await self._send_reactive_command(payload, ReactiveCommand.Connect)
        logging.info('Connected %s:%s to %s:%s on %s', from_module.name, from_output,
             to_module.name, to_input, self.name)


    async def set_key(self, module, io_name, encryption, key, conn_io):
        assert module.node is self
        assert encryption in module.get_supported_encryption()
        await module.deploy()

        if conn_io == ConnectionIO.OUTPUT:
            io_id = await module.get_output_id(io_name)
        else:
            io_id = await module.get_input_id(io_name)

        nonce = self.__get_nonce(module)

        # encrypting key
        args = [str(encryption.value), str(io_id), str(nonce), base64.b64encode(key).decode(),
            base64.b64encode(await module.key).decode()]

        out = await tools.run_async_output(glob.ENCRYPTOR, *args)

        cipher = base64.b64decode(out)

        payload =   self._pack_int16(module.id)                + \
                    self._pack_int16(_CallEntrypoint.SetKey)   + \
                    self._pack_int8(encryption)                + \
                    self._pack_int16(io_id)                    + \
                    self._pack_int16(nonce)                    + \
                    cipher

        await self._send_reactive_command(payload, ReactiveCommand.Call)
        logging.info("Set the key of {}:{}".format(module.name, io_name))


    async def call(self, module, entry, arg=None):
        assert module.node is self
        module_id = module.id
        entry_id = await module.get_entry_id(entry)

        payload = self._pack_int16(module_id)       + \
                  self._pack_int16(entry_id)        + \
                  (b'' if arg is None else arg)

        await self._send_reactive_command(payload, ReactiveCommand.Call)
        logging.info("Sent call to {}:{} ({}:{}) on {}".format(module.name, entry, module_id, entry_id, self.name))


    def get_module_id(self):
        id = self.__moduleid
        self.__moduleid += 1

        return id


    async def _send_reactive_command(self, payload, command=None, result_len=0):
        if command is not None:
            packet = self.__create_reactive_packet(command, payload)
        else:
            packet = payload

        reader, writer = await asyncio.open_connection(str(self.ip_address),
                                                       self.reactive_port)

        with contextlib.closing(writer):
            writer.write(packet)
            raw_result = await reader.readexactly(result_len + 1)
            code = ReactiveResultCode(raw_result[0])

            if code != ReactiveResultCode.Ok:
                raise Error('Reactive command {} failed with code {}'
                                .format(command, code))

            return ReactiveResult(code, raw_result[1:])


    def __create_reactive_packet(self, command, payload):
        return self._pack_int16(command)      + \
               self._pack_int16(len(payload)) + \
               payload


    def __get_nonce(self, module):
        nonce = self.__nonces[module]
        self.__nonces[module] += 1
        return nonce
