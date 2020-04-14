import asyncio
import logging
import os

from .base import Module

from ..nodes import NoSGXNode
from .. import tools
from .. import glob

import rustsgxgen.main as generator

class Object():
    pass

class Error(Exception):
    pass


class NoSGXModule(Module):
    def __init__(self, name, node):
        self.__check_init_args(node)

        self.__deploy_fut = None
        self.__generate_fut = None
        self.__build_fut = None
        self.__gen_key_fut = None

        self.name = name
        self.node = node
        self.id = node.get_module_id()
        self.port = self.node.reactive_port + self.id
        self.output = tools.create_tmp_dir()
        self.inputs = None
        self.outputs = None
        self.entrypoints = None


    @property
    async def key(self):
        if self.__gen_key_fut is None:
            self.__gen_key_fut = asyncio.ensure_future(self.__generate_key())

        return await self.__gen_key_fut


    @property
    async def binary(self):
        if self.__build_fut is None:
            self.__build_fut = asyncio.ensure_future(self.__build())

        return await self.__build_fut


    def __check_init_args(self, node):
        if not isinstance(node, self.get_supported_node_type()):
            clsname = lambda o: type(o).__name__
            raise Error('A {} cannot run on a {}'
                    .format(clsname(self), clsname(node)))


    @staticmethod
    def get_supported_node_type():
        return NoSGXNode


    def get_input_id(self, input):
        if input not in self.inputs:
            raise Error("Input not present in inputs")

        return self.inputs[input]


    def get_output_id(self, output):
        if output not in self.outputs:
            raise Error("Output not present in outputs")

        return self.outputs[output]


    def get_entry_id(self, entry):
        if entry not in self.entrypoints:
            raise Error("Entry not present in entrypoints")

        return self.entrypoints[entry]


    async def deploy(self):
        if self.__deploy_fut is None:
            self.__deploy_fut = asyncio.ensure_future(self.__deploy())

        await self.__deploy_fut


    async def __deploy(self):
        await self.node.deploy(self)


    async def generate_code(self):
        if self.__generate_fut is None:
            self.__generate_fut = asyncio.ensure_future(self.__generate_code())

        await self.__generate_fut


    async def __generate_code(self):
        args = Object()

        args.input = self.name
        args.output = self.output
        args.moduleid = self.id
        args.key = await self.key
        args.emport = self.node.deploy_port
        args.runner = "runner_nosgx"
        args.spkey = None
        args.print = None


        self.inputs, self.outputs, self.entrypoints = generator.generate(args)
        logging.info("Generated code for module {}".format(self.name))


    async def __build(self):
        await self.generate_code()

        cmd = glob.BUILD_APP.format(self.output)
        await tools.run_async_muted(*cmd)

        binary = "{}/target/{}/{}".format(self.output, glob.BUILD_MODE, self.name)

        logging.info("Built module {}".format(self.name))
        return binary


    async def __generate_key(self):
        return tools.generate_key(16)
