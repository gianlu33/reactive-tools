import asyncio
import collections
import logging
from abc import ABC, abstractmethod

from .base import Node

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
        pass


    async def set_key(self, module, io_name, key):
        logging.error("To be implemented")


    async def call(self, module, entry, arg=None):
        logging.error("To be implemented")


    def get_module_id(self):
        id = self.__moduleid
        self.__moduleid += 1

        return id
