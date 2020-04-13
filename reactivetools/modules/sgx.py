import asyncio
import logging
import os
import aiofile

from .base import Module

from ..nodes import SGXNode
from .. import tools
from .. import glob

import rustsgxgen.main as generator

class Object():
    pass

class Error(Exception):
    pass


async def _get_sp_key():
    try:
        async with aiofile.AIOFile(glob.RA_SP_PUB_KEY, "r") as f:
            key = await f.read()
    except:
        raise Error("Failed to load ra_sp public key")

    return key


class SGXModule(Module):
    _sp_key_fut = asyncio.ensure_future(_get_sp_key())

    def __init__(self, name, node):
        self.__check_init_args(node)

        self.__deploy_fut = None
        self.__generate_fut = None
        self.__build_fut = None
        self.__convert_sign_fut = None
        self.__ra_fut = None

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
        if self.__ra_fut is None:
            self.__ra_fut = asyncio.ensure_future(self.__remote_attestation())

        return await self.__ra_fut


    @property
    async def binary(self):
        if self.__build_fut is None:
            self.__build_fut = asyncio.ensure_future(self.__build())

        return await self.__build_fut


    @property
    async def sgxs(self):
        if self.__convert_sign_fut is None:
            self.__convert_sign_fut = asyncio.ensure_future(self.__convert_sign())

        sgxs, _ = await self.__convert_sign_fut

        return sgxs


    @property
    async def sig(self):
        if self.__convert_sign_fut is None:
            self.__convert_sign_fut = asyncio.ensure_future(self.__convert_sign())

        _, sig = await self.__convert_sign_fut

        return sig


    def __check_init_args(self, node):
        if not isinstance(node, self.get_supported_node_type()):
            clsname = lambda o: type(o).__name__
            raise Error('A {} cannot run on a {}'
                    .format(clsname(self), clsname(node)))


    @staticmethod
    def get_supported_node_type():
        return SGXNode


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
        args.key = None
        args.emport = self.node.deploy_port
        args.runner = "runner_sgx"
        args.spkey = await self._sp_key_fut
        args.print = None


        self.inputs, self.outputs, self.entrypoints = generator.generate(args)
        logging.info("Generated code for module {}".format(self.name))


    async def __build(self):
        await self.generate_code()

        cmd = glob.BUILD_SGX_APP.format(self.output)
        await tools.run_async_shell(cmd)

        binary = "{}/target/{}/debug/{}".format(self.output, glob.SGX_TARGET, self.name)

        logging.info("Built module {}".format(self.name))

        return binary


    async def __convert_sign(self):
        binary = await self.binary

        sgxs = "{}.sgxs".format(binary)
        sig = "{}.sig".format(binary)

        cmd_convert = glob.CONVERT_SGX.format(binary)
        cmd_sign = glob.SIGN_SGX.format(sgxs, sig)

        await tools.run_async_shell(cmd_convert)
        await tools.run_async_shell(cmd_sign)

        logging.info("Converted & signed module {}".format(self.name))

        return sgxs, sig


    async def __remote_attestation(self):
        await self.deploy()
        
        cmd = "cargo run --manifest-path={} {} {} {}".format(
            glob.RA_CLIENT, self.node.ip_address, self.port, await self.sig)
        await tools.run_async_shell(cmd)

        await asyncio.sleep(1) # to let ra_sp write the key to file

        async with aiofile.AIOFile("{}.key".format(await self.binary), "rb") as f:
            key = await f.read()

        logging.info("Done Remote Attestation of {}".format(self.name))

        return key
