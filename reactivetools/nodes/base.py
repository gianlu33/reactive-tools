from abc import ABC, abstractmethod
import asyncio

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
