import asyncio
import struct

from abc import ABC, abstractmethod
from enum import IntEnum

class Node(ABC):
    def __init__(self, name, ip_address, reactive_port, deploy_port):
        self.name = name
        self.ip_address = ip_address
        self.reactive_port = reactive_port
        self.deploy_port = deploy_port

    @abstractmethod
    async def deploy(self, module):
        pass

    @abstractmethod
    async def connect(self, from_module, from_output, to_module, to_input):
        pass

    @abstractmethod
    async def set_key(self, module, io_name, encryption, key, conn_io):
        pass

    @abstractmethod
    async def call(self, module, entry, arg=None):
        pass

    @staticmethod
    def _pack_int16(i):
        return struct.pack('!H', i)

    @staticmethod
    def _unpack_int16(i):
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


class ReactiveCommand(IntEnum):
    Connect             = 0x0
    Call                = 0x1
    RemoteOutput        = 0x2
    Load                = 0x3
    Ping                = 0x4
    Output              = 0x5 # called by software modules in SGX and NoSGX


class ReactiveResultCode(IntEnum):
    Ok                  = 0x0
    IllegalCommand      = 0x1
    IllegalPayload      = 0x2
    InternalError       = 0x3
    BadRequest          = 0x4
    CryptoError         = 0x5
    GenericError        = 0x6


class ReactiveEntrypoint(IntEnum):
    SetKey              = 0x0
    HandleInput         = 0x1


class ReactiveResult:
    def __init__(self, code, payload=bytearray()):
        self.code = code
        self.payload = payload
