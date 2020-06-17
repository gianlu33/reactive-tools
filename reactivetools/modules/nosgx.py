import asyncio
import logging
import os

from .base import Module

from ..nodes import NoSGXNode
from .. import tools
from .. import glob
from ..connection import Encryption

class Object():
    pass

class Error(Exception):
    pass


class NoSGXModule(Module):
    def __init__(self, name, node, priority, deployed, features, id=None, binary=None,
                    key=None, inputs=None, outputs=None, entrypoints=None):
        super().__init__(name, node, priority, deployed)

        self.__check_init_args(node, id, binary, key, inputs, outputs, entrypoints)

        self.__deploy_fut = tools.init_future(id) # not completely true
        self.__generate_fut = tools.init_future(inputs, outputs, entrypoints, key)
        self.__build_fut = tools.init_future(binary)

        self.features = [] if features is None else features
        self.id = id if id is not None else node.get_module_id()
        self.port = self.node.reactive_port + self.id
        self.output = tools.create_tmp_dir()

    # --- Properties --- #

    @property
    async def inputs(self):
        inputs, _outs, _entrys, _key = await self.generate_code()
        return inputs


    @property
    async def outputs(self):
        _ins, outputs, _entrys, _key = await self.generate_code()
        return outputs


    @property
    async def entrypoints(self):
        _ins, _outs, entrypoints, _key = await self.generate_code()
        return entrypoints


    @property
    async def key(self):
        _ins, _outs, _entrys, key = await self.generate_code()
        return key


    @property
    async def binary(self):
        if self.__build_fut is None:
            self.__build_fut = asyncio.ensure_future(self.__build())

        return await self.__build_fut


    # --- Implement abstract methods --- #

    async def deploy(self):
        if self.__deploy_fut is None:
            self.__deploy_fut = asyncio.ensure_future(self.node.deploy(self))

        await self.__deploy_fut


    async def call(self, entry, arg=None):
        return await self.node.call(self, entry, arg)


    async def get_id(self):
        return self.id


    async def get_input_id(self, input):
        inputs = await self.inputs

        if input not in inputs:
            raise Error("Input not present in inputs")

        return inputs[input]


    async def get_output_id(self, output):
        outputs = await self.outputs

        if output not in outputs:
            raise Error("Output not present in outputs")

        return outputs[output]


    async def get_entry_id(self, entry):
        entrypoints = await self.entrypoints

        if entry not in entrypoints:
            raise Error("Entry not present in entrypoints")

        return entrypoints[entry]


    async def get_key(self):
        return await self.key


    @staticmethod
    def get_supported_node_type():
        return NoSGXNode


    @staticmethod
    def get_supported_encryption():
        return [Encryption.AES, Encryption.SPONGENT]


    # --- Static methods --- #

    # --- Others --- #

    def __check_init_args(self, node, id, binary, key, inputs, outputs, entrypoints):
        if not isinstance(node, self.get_supported_node_type()):
            clsname = lambda o: type(o).__name__
            raise Error('A {} cannot run on a {}'
                    .format(clsname(self), clsname(node)))

        # For now, either all optionals should be given or none. This might be
        # relaxed later if necessary.
        optionals = (id, binary, key, inputs, outputs, entrypoints)

        if None in optionals and any(map(lambda x: x is not None, optionals)):
            raise Error('Either all of the optional node parameters '
                        'should be given or none')


    async def generate_code(self):
        if self.__generate_fut is None:
            self.__generate_fut = asyncio.ensure_future(self.__generate_code())

        return await self.__generate_fut


    async def __generate_code(self):
        try:
            import rustsgxgen
        except:
            raise Error("rust-sgx-gen not installed! Check README.md")

        args = Object()

        args.input = self.name
        args.output = self.output
        args.moduleid = self.id
        args.emport = self.node.deploy_port
        args.runner = rustsgxgen.Runner.NoSGX
        args.spkey = None
        args.print = None

        inputs, outputs, entrypoints, key = rustsgxgen.generate(args)
        logging.info("Generated code for module {}".format(self.name))

        return inputs, outputs, entrypoints, key


    async def __build(self):
        await self.generate_code()

        features = ""
        if self.features:
            features = "--features " + " ".join(self.features)

        cmd = glob.BUILD_APP.format(features, self.output).split()
        await tools.run_async_muted(*cmd)

        binary = "{}/target/{}/{}".format(self.output, glob.BUILD_MODE, self.name)

        logging.info("Built module {}".format(self.name))
        return binary
