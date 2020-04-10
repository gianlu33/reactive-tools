import asyncio
import logging
import subprocess
import os

from .base import Module

from ..nodes import NoSGXNode
from .. import tools

import rustsgxgen.main as generator

class Object():
    pass

class Error(Exception):
    pass


class NoSGXModule(Module):
    def __init__(self, name, node):
        self.__check_init_args(node)

        self.name = name
        self.node = node
        self.id = node.get_module_id()
        self.output = tools.create_tmp_dir()
        self.key = tools.generate_key(16)
        self.inputs = None
        self.outputs = None
        self.entrypoints = None
        self.binary = None


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
        # code injection
        logging.info("Generating code for module {}".format(self.name))
        self.__generate_code()

        # build
        logging.info("Building module {}".format(self.name))
        self.__build()

        #call deploy on the node
        await self.node.deploy(self)


    def __generate_code(self):
        args = Object()

        args.input = self.name
        args.output = self.output
        args.moduleid = self.id
        args.key = self.key
        args.emport = self.node.deploy_port
        args.runner = "runner_nosgx"
        args.spkey = None
        args.print = None


        self.inputs, self.outputs, self.entrypoints = generator.generate(args)


    def __build(self):
        args = ["cargo", "build", "--manifest-path={}/Cargo.toml".format(self.output)]

        retval = subprocess.call(args, stdout=open(os.devnull, 'wb'), stderr=subprocess.STDOUT)

        if retval != 0:
            raise Error("Build {} failed".format(self.name))

        self.binary = "{}/target/debug/{}".format(self.output, self.name)

        #logging.debug("Executable in: {}".format(self.binary))
