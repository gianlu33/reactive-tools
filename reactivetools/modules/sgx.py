import asyncio
import logging
import subprocess
import os

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
        with open(glob.RA_SP_PUB_KEY, "r") as f:
            key = f.read()
    except:
        raise Error("Failed to load ra_sp public key")

    return key


class SGXModule(Module):
    _sp_key_fut = asyncio.ensure_future(_get_sp_key())

    def __init__(self, name, node):
        self.__check_init_args(node)

        self.name = name
        self.node = node
        self.id = node.get_module_id()
        self.output = tools.create_tmp_dir()

    def __check_init_args(self, node):
        if not isinstance(node, self.get_supported_node_type()):
            clsname = lambda o: type(o).__name__
            raise Error('A {} cannot run on a {}'
                    .format(clsname(self), clsname(node)))


    @staticmethod
    def get_supported_node_type():
        return SGXNode


    async def deploy(self):
        # code injection
        logging.info("Generating code for module {}".format(self.name))
        await self.__generate_code()

        # build
        logging.info("Building module {}".format(self.name))
        self.__build()

        logging.info("Converting & signing module {}".format(self.name))
        self.__convert_sign()

        #call deploy on the node
        logging.info("Deploying on node")
        await self.node.deploy(self)

        # TODO remote attestation


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


    def __build(self):
        args = ["cargo", "build", "--manifest-path={}/Cargo.toml".format(self.output), "--target={}".format(glob.SGX_TARGET)]

        retval = subprocess.call(args, stdout=open(os.devnull, 'wb'), stderr=subprocess.STDOUT)

        if retval != 0:
            raise Error("Build {} failed".format(self.name))

        self.binary = "{}/target/{}/debug/{}".format(self.output, glob.SGX_TARGET, self.name)

        #logging.debug("Executable in: {}".format(self.binary))


    def __convert_sign(self):
        convert_args = ["ftxsgx-elf2sgxs", self.binary, "--heap-size", "0x20000", "--stack-size", "0x20000", "--threads", "2", "--debug"]

        # converting
        retval = subprocess.call(convert_args, stdout=open(os.devnull, 'wb'), stderr=subprocess.STDOUT)
        if retval != 0:
            raise Error("Conversion of {} failed".format(self.name))

        self.sgxs = "{}.sgxs".format(self.binary)
        self.sig = "{}.sig".format(self.binary)

        # signing
        # TODO check arguments
        sign_args = ["sgxs-sign", "--key", glob.VENDOR_PRIVATE_KEY, self.sgxs, self.sig, "-d", "--xfrm", "7/0", "--isvprodid", "0", "--isvsvn", "0"]
        retval = subprocess.call(sign_args, stdout=open(os.devnull, 'wb'), stderr=subprocess.STDOUT)
        if retval != 0:
            raise Error("Signature of {} failed".format(sm))
