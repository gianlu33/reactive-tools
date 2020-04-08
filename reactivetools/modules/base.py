from abc import ABC, abstractmethod

class Module(ABC):
    @abstractmethod
    async def deploy(self):
        pass
