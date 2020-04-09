import asyncio
import collections
import logging
from abc import ABC, abstractmethod
import struct
from enum import IntEnum
import subprocess
import base64
import contextlib

from .base import Node
from ..connection import ConnectionIO
from .. import glob

class ServerNode(Node):
    def __init__(self, name, ip_address, deploy_port, reactive_port=None):
        self.name = name
        self.ip_address = ip_address
        self.deploy_port = deploy_port

        if reactive_port is None:
            self.reactive_port = deploy_port
        else:
            self.reactive_port = reactive_port

        self.__nonces = collections.Counter()
        self.__moduleid = 1


    @abstractmethod
    async def deploy(self, module):
        pass


    async def connect(self, from_module, from_output, to_module, to_input):
        assert from_module.node is self

        logging.info('Connecting %s:%s to %s:%s on %s',
             from_module.name, from_output,
             to_module.name, to_input,
             self.name))

        payload = self.__pack_int(from_module.id)   + \
                  self.__pack_int(from_module.get_output_id(from_output))   + \
                  self.__pack_int(to_module.id)     + \
                  self.__pack_int(to_module.get_input_id(to_input))     + \
                  self.__pack_int(to_module.node.reactive_port)     + \
                  to_module.node.ip_address.packed

        await self.__send_reactive_command(_ReactiveCommand.Connect, payload)


    async def set_key(self, module, io_name, key, conn_io):
        logging.info("Setting the key of {}:{}".format(module.name, io_name))

        nonce = self.__get_nonce(module)
        args = ["cargo", "run", "--manifest-path={}".format(glob.ENCRYPTOR), str(io_name), str(nonce), key, module.key]

        out = subprocess.check_output(args, stderr=open("/dev/null", "wb"))
        cipher = base64.b64decode(out)

        if conn_io == ConnectionIO.OUTPUT:
            io_id = module.get_output_id(io_name)
        else:
            io_id = module.get_input_id(io_name)

        payload =   self.__pack_int(module.id)                + \
                    self.__pack_int(_CallEntrypoint.SetKey)   + \
                    self.__pack_int(io_id)                    + \
                    self.__pack_int(nonce)                    + \
                    cipher

        await self.__send_reactive_command(_ReactiveCommand.Call, payload)

        # TODO wait for response?!


    async def call(self, module, entry, arg=None):
        logging.error("To be implemented")


    def get_module_id(self):
        id = self.__moduleid
        self.__moduleid += 1

        return id


    # TODO
    async def __send_reactive_command(self, command, payload, result_len=0,
                                      *, log=None):
        packet = self.__create_reactive_packet(command, payload)

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
        return self.__pack_int(command)      + \
               self.__pack_int(len(payload)) + \
               payload


    def __get_nonce(self, module):
        nonce = self.__nonces[module]
        self.__nonces[module] += 1
        return nonce


    @staticmethod
    def __pack_int(i):
        return struct.pack('!H', i)

    @staticmethod
    def __unpack_int(i):
        return struct.unpack('!H', i)[0]


class _ReactiveCommand(IntEnum):
    Connect   = 0x0
    Call      = 0x1
    Load      = 0x3
    Ping      = 0x5


class _CallEntrypoint(IntEnum):
    SetKey  = 0x0


# TODO
class _ReactiveResultCode(IntEnum):
    Ok                = 0x0
    ErrIllegalCommand = 0x1
    ErrPayloadFormat  = 0x2
    ErrInternal       = 0x3


class _ReactiveResult:
    def __init__(self, code, payload=bytearray()):
        self.code = code
        self.payload = payload