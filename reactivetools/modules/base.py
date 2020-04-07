from abc import ABC, abstractmethod
from enum import Enum

class Type(Enum):
    NONE = 0,
    SANCUS = 1,
    SGX = 2,
    NOSGX = 3

class Module(ABC):
    type = Type.NONE

    @abstractmethod
    async def deploy(self):
        pass
