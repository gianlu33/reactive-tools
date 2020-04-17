import asyncio
import collections
import logging
from abc import ABC, abstractmethod
import struct
from enum import IntEnum
import base64
import contextlib

from .base import Node
from ..connection import ConnectionIO
from .. import glob
from .. import tools

class Error(Exception):
    pass


class ServerNode(Node):
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

        payload = self._pack_int(from_module_id)                    + \
                  self._pack_int(from_output_id)                    + \
                  self._pack_int(to_module_id)                      + \
                  self._pack_int(to_input_id)                       + \
                  self._pack_int(to_module.node.reactive_port)      + \
                  to_module.node.ip_address.packed

        await self._send_reactive_command(payload, _ReactiveCommand.Connect)
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

        payload =   self._pack_int(module.id)                + \
                    self._pack_int(_CallEntrypoint.SetKey)   + \
                    self._pack_int8(encryption)              + \
                    self._pack_int(io_id)                    + \
                    self._pack_int(nonce)                    + \
                    cipher

        await self._send_reactive_command(payload, _ReactiveCommand.Call)
        logging.info("Set the key of {}:{}".format(module.name, io_name))


    async def call(self, module, entry, arg=None):
        assert module.node is self
        module_id = module.id
        entry_id = await module.get_entry_id(entry)

        payload = self._pack_int(module_id) + \
                  self._pack_int(entry_id)  + \
                  (b'' if arg is None else arg)

        await self._send_reactive_command(payload, _ReactiveCommand.Call)
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
            code = _ReactiveResultCode(raw_result[0])

            if code != _ReactiveResultCode.Ok:
                raise Error('Reactive command {} failed with code {}'
                                .format(command, code))

            return _ReactiveResult(code, raw_result[1:])


    def __create_reactive_packet(self, command, payload):
        return self._pack_int(command)      + \
               self._pack_int(len(payload)) + \
               payload


    def __get_nonce(self, module):
        nonce = self.__nonces[module]
        self.__nonces[module] += 1
        return nonce


    @staticmethod
    def _pack_int(i):
        return struct.pack('!H', i)

    @staticmethod
    def _unpack_int(i):
        return struct.unpack('!H', i)[0]

    @staticmethod
    def _pack_int32(i):
        return struct.pack('!i', i)

    @staticmethod
    def _unpack_int32(i):
        return struct.unpack('!i', i)[0]

    @staticmethod
    def _pack_int8(i):
        return struct.pack('!B', i)

    @staticmethod
    def _unpack_int8(i):
        return struct.unpack('!B', i)[0]


class _ReactiveCommand(IntEnum):
    Connect   = 0x0
    Call      = 0x1
    Load      = 0x3
    Ping      = 0x5


class _CallEntrypoint(IntEnum):
    SetKey  = 0x0


class _ReactiveResultCode(IntEnum):
    Ok                = 0x0
    ErrIllegalCommand = 0x1
    ErrPayloadFormat  = 0x2
    ErrInternal       = 0x3


class _ReactiveResult:
    def __init__(self, code, payload=bytearray()):
        self.code = code
        self.payload = payload
