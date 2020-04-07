from abc import ABC, abstractmethod
from enum import Enum
import asyncio

class Type(Enum):
    NONE = 0,
    SANCUS = 1,
    SGX = 2,
    NOSGX = 3

class Node(ABC):
    type = Type.NONE

    @abstractmethod
    async def deploy(self, module):
        pass

    @abstractmethod
    async def connect(self, from_module, from_output, to_module, to_input):
        pass

    @abstractmethod
    async def set_key(self, module, io_name, key):
        pass
