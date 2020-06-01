import json
import binascii
import ipaddress
from pathlib import Path
import os
import asyncio
import functools
import binascii
import types
import logging

from .nodes import SancusNode, SGXNode, NoSGXNode
from .modules import SancusModule, SGXModule, NoSGXModule, Module
from .connection import Connection, Encryption
from .periodic_event import PeriodicEvent
from . import tools


class Error(Exception):
    pass


class Config:
    def __init__(self, file_name):
        self.path = Path(file_name).resolve()
        self.nodes = []
        self.modules = []
        self.connections = []

    def get_dir(self):
        return self.path.parent

    def get_node(self, name):
        for n in self.nodes:
            if n.name == name:
                return n

        raise Error('No node with name {}'.format(name))

    def get_module(self, name):
        for m in self.modules:
            if m.name == name:
                return m

        raise Error('No module with name {}'.format(name))

    async def install_async(self):
        futures = map(Connection.establish, self.connections)
        await asyncio.gather(*futures)

        # this is needed if we don't have any connections, to ensure that
        # the modules are actually deployed
        await self.deploy_modules_ordered_async()

        futures = map(PeriodicEvent.register, self.periodic_events)
        await asyncio.gather(*futures)

    def install(self):
        asyncio.get_event_loop().run_until_complete(self.install_async())

    async def deploy_modules_ordered_async(self):
        for module in self.modules:
            await module.deploy()

    def deploy_modules_ordered(self):
        asyncio.get_event_loop().run_until_complete(
                                self.deploy_modules_ordered_async())


    def cleanup(self):
        asyncio.get_event_loop().run_until_complete(self.cleanup_async())


    async def cleanup_async(self):
        await SGXModule.kill_ra_sp()


def load(file_name):
    with open(file_name, 'r') as f:
        contents = json.load(f)

    config = Config(file_name)

    config.nodes = _load_list(contents['nodes'], _load_node)
    config.modules = _load_list(contents['modules'],
                                lambda m: _load_module(m, config))

    try:
        config.connections = _load_list(contents['connections'],
                                        lambda c: _load_connection(c, config))
    except Exception as e:
        logging.warning("Error while loading 'connections' section of input file")
        logging.warning("{}".format(e))
        config.connections = []

    try:
        config.periodic_events = _load_list(contents['periodic-events'],
                                        lambda e: _load_periodic_event(e, config))
    except Exception as e:
        logging.warning("Error while loading 'periodic-events' section of input file")
        logging.warning("{}".format(e))
        config.periodic_events = []

    return config


def _load_list(l, load_func=lambda e: e):
    if l is None:
        return []
    else:
        return [load_func(e) for e in l]


def _load_node(node_dict):
    return _node_load_funcs[node_dict['type']](node_dict)


def _load_sancus_node(node_dict):
    name = node_dict['name']
    vendor_id = _parse_vendor_id(node_dict['vendor_id'])
    vendor_key = _parse_vendor_key(node_dict['vendor_key'])
    ip_address = ipaddress.ip_address(node_dict['ip_address'])
    reactive_port = node_dict['reactive_port']
    deploy_port = node_dict.get('deploy_port', reactive_port)

    return SancusNode(name, vendor_id, vendor_key,
                      ip_address, reactive_port, deploy_port)


def _load_sgx_node(node_dict):
    name = node_dict['name']
    ip_address = ipaddress.ip_address(node_dict['ip_address'])
    reactive_port = node_dict['reactive_port']
    deploy_port = node_dict.get('deploy_port', reactive_port)

    return SGXNode(name, ip_address, reactive_port, deploy_port)


def _load_nosgx_node(node_dict):
    name = node_dict['name']
    ip_address = ipaddress.ip_address(node_dict['ip_address'])
    reactive_port = node_dict['reactive_port']
    deploy_port = node_dict.get('deploy_port', reactive_port)

    return NoSGXNode(name, ip_address, reactive_port, deploy_port)


def _load_module(mod_dict, config):
    return _module_load_funcs[mod_dict['type']](mod_dict, config)


def _load_sancus_module(mod_dict, config):
    name = mod_dict['name']
    files = _load_list(mod_dict['files'],
                       lambda f: _load_module_file(f, config))
    cflags = _load_list(mod_dict.get('cflags'))
    ldflags = _load_list(mod_dict.get('ldflags'))
    node = config.get_node(mod_dict['node'])
    binary = mod_dict.get('binary')
    id = mod_dict.get('id')
    symtab = mod_dict.get('symtab')
    key = mod_dict.get('key')
    return SancusModule(name, files, cflags, ldflags, node,
                        binary, id, symtab, key)


def _load_sgx_module(mod_dict, config):
    name = mod_dict['name']
    node = config.get_node(mod_dict['node'])
    vendor_key = mod_dict['vendor_key']
    settings = mod_dict['ra_settings']
    id = mod_dict.get('id')
    binary = mod_dict.get('binary')
    key = mod_dict.get('key')
    sgxs = mod_dict.get('sgxs')
    signature = mod_dict.get('signature')
    inputs = mod_dict.get('inputs')
    outputs = mod_dict.get('outputs')
    entrypoints = mod_dict.get('entrypoints')

    return SGXModule(name, node, vendor_key, settings, id, binary, key, sgxs,
                        signature, inputs, outputs, entrypoints)


def _load_nosgx_module(mod_dict, config):
    name = mod_dict['name']
    node = config.get_node(mod_dict['node'])
    id = mod_dict.get('id')
    binary = mod_dict.get('binary')
    key = mod_dict.get('key')
    inputs = mod_dict.get('inputs')
    outputs = mod_dict.get('outputs')
    entrypoints = mod_dict.get('entrypoints')

    return NoSGXModule(name, node, id, binary, key, inputs, outputs, entrypoints)


def _load_connection(conn_dict, config):
    from_module = config.get_module(conn_dict['from_module'])
    from_output = conn_dict['from_output']
    to_module = config.get_module(conn_dict['to_module'])
    to_input = conn_dict['to_input']
    encryption = Encryption.from_str(conn_dict['encryption'])

    if from_module == to_module:
        raise Error("Cannot establish a within the same module!")

    from_module.connections += 1
    to_module.connections += 1

    # Don't use dict.get() here because we don't want to call os.urandom() when
    # not strictly necessary.
    if 'key' in conn_dict:
        key = conn_dict['key']
    else:
        key = _generate_key(from_module, to_module, encryption)

    return Connection(from_module, from_output, to_module, to_input, encryption, key)


def _load_periodic_event(events_dict, config):
    module = config.get_module(events_dict['module'])
    entry = events_dict['entry']
    frequency = _parse_frequency(events_dict['frequency'])

    return PeriodicEvent(module, entry, frequency)


def _generate_key(module1, module2, encryption):
    if encryption not in module1.get_supported_encryption() or \
       encryption not in module2.get_supported_encryption():
       raise Error('Encryption "{}" not supported between {} and {}'.format(
            encryption, module1.name, module2.name))

    return tools.generate_key(encryption.get_key_size())


def _parse_vendor_id(id):
    if not 1 <= id <= 2**16 - 1:
        raise Error('Vendor ID out of range')

    return id


def _parse_vendor_key(key_str):
    key = binascii.unhexlify(key_str)

    keysize = tools.get_sancus_key_size()

    if len(key) != keysize:
        raise Error('Keys should be {} bytes'.format(keysize))

    return key


def _parse_frequency(freq):
    if not 1 <= freq <= 2**32 - 1:
        raise Error('Frequency out of range')

    return freq


def _load_module_file(file_name, config):
    path = Path(file_name)
    return path if path.is_absolute() else config.get_dir() / path


_node_load_funcs = {
    'sancus': _load_sancus_node,
    'sgx': _load_sgx_node,
    'nosgx': _load_nosgx_node
}


_module_load_funcs = {
    'sancus': _load_sancus_module,
    'sgx': _load_sgx_module,
    'nosgx': _load_nosgx_module
}


def dump(config, file_name):
    with open(file_name, 'w') as f:
        json.dump(_dump(config), f, indent=4)


@functools.singledispatch
def _dump(obj):
    assert False, 'No dumper for {}'.format(type(obj))


@_dump.register(Config)
def _(config):
    return {
        'nodes': _dump(config.nodes),
        'modules': _dump(config.modules),
        'connections': _dump(config.connections),
        'periodic-events' : _dump(config.periodic_events)
    }


@_dump.register(list)
def _(l):
    return [_dump(e) for e in l]


@_dump.register(SancusNode)
def _(node):
    return {
        "type": "sancus",
        "name": node.name,
        "ip_address": str(node.ip_address),
        "vendor_id": node.vendor_id,
        "vendor_key": _dump(node.vendor_key),
        "reactive_port": node.reactive_port,
        "deploy_port": node.deploy_port
    }


@_dump.register(SancusModule)
def _(module):
    return {
        "type": "sancus",
        "name": module.name,
        "files": _dump(module.files),
        "node": module.node.name,
        "binary": _dump(module.binary),
        "symtab": _dump(module.symtab),
        "id": _dump(module.id),
        "key": _dump(module.key)
    }


@_dump.register(SGXNode)
def _(node):
    return {
        "type": "sgx",
        "name": node.name,
        "ip_address": str(node.ip_address),
        "reactive_port": node.reactive_port,
        "deploy_port": node.deploy_port
    }


@_dump.register(SGXModule)
def _(module):
    return {
        "type": "sgx",
        "name": module.name,
        "node": module.node.name,
        "vendor_key": module.vendor_key,
        "ra_settings": module.ra_settings,
        "id": module.id,
        "binary": _dump(module.binary),
        "sgxs": _dump(module.sgxs),
        "signature": _dump(module.sig),
        "key": _dump(module.key),
        "inputs": _dump(module.inputs),
        "outputs": _dump(module.outputs),
        "entrypoints": _dump(module.entrypoints)
    }


@_dump.register(NoSGXNode)
def _(node):
    return {
        "type": "nosgx",
        "name": node.name,
        "ip_address": str(node.ip_address),
        "reactive_port": node.reactive_port,
        "deploy_port": node.deploy_port
    }


@_dump.register(NoSGXModule)
def _(module):
    return {
        "type": "nosgx",
        "name": module.name,
        "node": module.node.name,
        "id": module.id,
        "binary": _dump(module.binary),
        "key": _dump(module.key),
        "inputs": _dump(module.inputs),
        "outputs": _dump(module.outputs),
        "entrypoints": _dump(module.entrypoints)
    }


@_dump.register(Connection)
def _(conn):
    return {
        "from_module": conn.from_module.name,
        "from_output": conn.from_output,
        "to_module": conn.to_module.name,
        "to_input": conn.to_input,
        "encryption": conn.encryption.to_str(),
        "key": _dump(conn.key)
    }


@_dump.register(PeriodicEvent)
def _(event):
    return {
        "module": event.module.name,
        "entry": event.entry,
        "frequency": event.frequency
    }


@_dump.register(bytes)
@_dump.register(bytearray)
def _(bs):
    return binascii.hexlify(bs).decode('ascii')


@_dump.register(str)
@_dump.register(int)
def _(x):
    return x


@_dump.register(Path)
def _(path):
    return str(path)


@_dump.register(tuple)
def _(t):
    return { t[1] : t[0] }


@_dump.register(types.CoroutineType)
def _(coro):
    return _dump(asyncio.get_event_loop().run_until_complete(coro))


@_dump.register(dict)
def _(dict):
    return dict
