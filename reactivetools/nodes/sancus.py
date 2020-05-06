import asyncio
import contextlib
import logging
import binascii
import aiofile

from reactivenet import *

from .base import Node
from .. import tools


class Error(Exception):
    pass

class SancusNode(Node):
    def __init__(self, name, vendor_id, vendor_key,
                 ip_address, reactive_port, deploy_port):
        super().__init__(name, ip_address, reactive_port, deploy_port, need_lock=True)

        self.vendor_id = vendor_id
        self.vendor_key = vendor_key


    async def deploy(self, module):
        assert module.node is self

        async with aiofile.AIOFile(await module.binary, "rb") as f:
            file_data = await f.read()

        # The packet format is [NAME \0 VID ELF_FILE]
        payload =   module.name.encode('ascii') + b'\0'   + \
                    tools.pack_int16(self.vendor_id)      + \
                    file_data

        command = CommandMessage(ReactiveCommand.Load,
                                Message.new(payload),
                                self.ip_address,
                                self.deploy_port)

        res = await self._send_reactive_command(
                command,
                log='Deploying {} on {}'.format(module.name, self.name)
                )


        sm_id = tools.unpack_int16(res.message.payload[:2])
        if sm_id == 0:
            raise Error('Deploying {} on {} failed'
                            .format(module.name, self.name))

        symtab = res.message.payload[2:]
        symtab_file = tools.create_tmp(suffix='.ld')

        async with aiofile.AIOFile(symtab_file, "wb") as f:
            await f.write(symtab[:-1]) # Drop last 0 byte
            await f.fsync()

        return sm_id, symtab_file


    async def connect(self, from_module, from_output, to_module, to_input):
        assert from_module.node is self

        results = await asyncio.gather(from_module.get_id(),
                                       from_module.get_output_id(from_output),
                                       to_module.get_id(),
                                       to_module.get_input_id(to_input))
        from_module_id, from_output_id, to_module_id, to_input_id = results

        payload = tools.pack_int16(from_module_id)                      + \
                  tools.pack_int16(from_output_id)                      + \
                  tools.pack_int16(to_module_id)                        + \
                  tools.pack_int16(to_input_id)                         + \
                  tools.pack_int16(to_module.node.reactive_port)        + \
                  to_module.node.ip_address.packed

        command = CommandMessage(ReactiveCommand.Connect,
                                Message.new(payload),
                                self.ip_address,
                                self.reactive_port)

        await self._send_reactive_command(
                command,
                log='Connecting {}:{} to {}:{} on {}'.format(
                 from_module.name, from_output,
                 to_module.name, to_input,
                 self.name)
                )

    async def set_key(self, module, io_name, encryption, key, conn_io):
        assert module.node is self
        assert encryption in module.get_supported_encryption()

        try:
            import sancus.crypto
        except:
            raise Error("Sancus python lib not installed! Check README.md")

        module_id, module_key, io_id = await asyncio.gather(
                               module.id, module.key, module.get_io_id(io_name))

        nonce = tools.pack_int16(self.__get_nonce(module))
        io_id = tools.pack_int16(io_id)
        ad = nonce + io_id
        cipher, tag = sancus.crypto.wrap(module_key, ad, key)

        # The payload format is [sm_id, entry_id, 16 bit nonce, index, wrapped(key), tag]
        # where the tag includes the nonce and the index.
        payload =       tools.pack_int16(module_id)                     + \
                        tools.pack_int16(ReactiveEntrypoint.SetKey)     + \
                        ad                                              + \
                        cipher                                          + \
                        tag

        command = CommandMessage(ReactiveCommand.Call,
                                Message.new(payload),
                                self.ip_address,
                                self.reactive_port)

        res = await self._send_reactive_command(
                command,
                log='Setting key of {}:{} on {} to {}'.format(
                     module.name, io_name, self.name,
                     binascii.hexlify(key).decode('ascii'))
                )

        # The result format is [tag] where the tag includes the nonce
        set_key_tag = result.message.payload
        expected_tag = sancus.crypto.mac(module_key, nonce)

        if set_key_tag != expected_tag:
            raise Error('Module response has wrong tag')


    async def call(self, module, entry, arg=None):
        assert module.node is self

        module_id, entry_id = \
            await asyncio.gather(module.id, module.get_entry_id(entry))

        payload = tools.pack_int16(module_id) + \
                  tools.pack_int16(entry_id)  + \
                  (b'' if arg is None else arg)

        command = CommandMessage(ReactiveCommand.Call,
                                Message.new(payload),
                                self.ip_address,
                                self.reactive_port)

        await self._send_reactive_command(
                command,
                log='Sending call command to {}:{} ({}:{}) on {}'.format(
                     module.name, entry, module_id, entry_id, self.name)
                )
