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

from .nodes import SancusNode, SGXNode, NativeNode
from .modules import SancusModule, SGXModule, NativeModule, Module
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


    def get_connection(self, id):
        for c in self.connections:
            if c.id == id:
                return c

        raise Error('No connection with ID {}'.format(id))


    async def install_async(self):
        await self.deploy_priority_modules()

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
            await module.get_key() # trigger remote attestation for some modules (e.g. SGX)

    def deploy_modules_ordered(self):
        asyncio.get_event_loop().run_until_complete(
                                self.deploy_modules_ordered_async())


    def cleanup(self):
        asyncio.get_event_loop().run_until_complete(self.cleanup_async())


    async def cleanup_async(self):
        await SGXModule.kill_ra_sp()


    async def deploy_priority_modules(self):
        priority_modules = [sm for sm in self.modules if sm.priority is not None]
        priority_modules.sort(key=lambda sm : sm.priority)

        logging.debug("Priority modules: {}".format([sm.name for sm in priority_modules]))
        for module in priority_modules:
            await module.deploy()


def load(file_name, deploy=True):
    with open(file_name, 'r') as f:
        contents = json.load(f)

    config = Config(file_name)

    config.nodes = _load_list(contents['nodes'], _load_node)
    config.modules = _load_list(contents['modules'],
                                lambda m: _load_module(m, config))

    try:
        config.connections = _load_list(contents['connections'],
                                        lambda c: _load_connection(c, config, deploy))
    except Exception as e:
        logging.warning("Error while loading 'connections' section of input file")
        logging.warning("{}".format(e))
        config.connections = []

    try:
        config.periodic_events = _load_list(contents['periodic-events'],
                                        lambda e: _load_periodic_event(e, config))
    except Exception as e:
        logging.warning("'periodic-events' section not loaded.")
        #logging.warning("{}".format(e))
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
    vendor_key = _parse_sancus_key(node_dict['vendor_key'])
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


def _load_native_node(node_dict):
    name = node_dict['name']
    ip_address = ipaddress.ip_address(node_dict['ip_address'])
    reactive_port = node_dict['reactive_port']
    deploy_port = node_dict.get('deploy_port', reactive_port)

    return NativeNode(name, ip_address, reactive_port, deploy_port)


def _load_module(mod_dict, config):
    return _module_load_funcs[mod_dict['type']](mod_dict, config)


def _load_sancus_module(mod_dict, config):
    name = mod_dict['name']
    node = config.get_node(mod_dict['node'])
    priority = mod_dict.get('priority')
    deployed = mod_dict.get('deployed')
    files = _load_list(mod_dict['files'],
                       lambda f: _load_module_file(f, config))
    cflags = _load_list(mod_dict.get('cflags'))
    ldflags = _load_list(mod_dict.get('ldflags'))
    binary = mod_dict.get('binary')
    id = mod_dict.get('id')
    symtab = mod_dict.get('symtab')
    key = _parse_sancus_key(mod_dict.get('key'))
    return SancusModule(name, node, priority, deployed, files, cflags, ldflags,
                        binary, id, symtab, key)


def _load_sgx_module(mod_dict, config):
    name = mod_dict['name']
    node = config.get_node(mod_dict['node'])
    priority = mod_dict.get('priority')
    deployed = mod_dict.get('deployed')
    vendor_key = mod_dict['vendor_key']
    settings = mod_dict['ra_settings']
    features = mod_dict.get('features')
    id = mod_dict.get('id')
    binary = mod_dict.get('binary')
    key = _parse_key(mod_dict.get('key'))
    sgxs = mod_dict.get('sgxs')
    signature = mod_dict.get('signature')
    inputs = mod_dict.get('inputs')
    outputs = mod_dict.get('outputs')
    entrypoints = mod_dict.get('entrypoints')

    return SGXModule(name, node, priority, deployed, vendor_key, settings,
                    features, id, binary, key, sgxs, signature, inputs, outputs,
                    entrypoints)


def _load_native_module(mod_dict, config):
    name = mod_dict['name']
    node = config.get_node(mod_dict['node'])
    priority = mod_dict.get('priority')
    deployed = mod_dict.get('deployed')
    features = mod_dict.get('features')
    id = mod_dict.get('id')
    binary = mod_dict.get('binary')
    key = _parse_key(mod_dict.get('key'))
    inputs = mod_dict.get('inputs')
    outputs = mod_dict.get('outputs')
    entrypoints = mod_dict.get('entrypoints')

    return NativeModule(name, node, priority, deployed, features, id, binary, key,
                                inputs, outputs, entrypoints)


def _load_connection(conn_dict, config, deploy):
    # direct connection: from Deployer to SM
    # non-direct connection: from SM to SM
    direct = conn_dict.get('direct')
    if direct is None or not direct:
        direct = False
        from_module = config.get_module(conn_dict['from_module'])
        from_output = conn_dict['from_output']
    else:
        from_module = None
        from_output = None

    to_module = config.get_module(conn_dict['to_module'])
    to_input = conn_dict['to_input']
    encryption = Encryption.from_str(conn_dict['encryption'])

    if from_module == to_module:
        raise Error("Cannot establish a connection within the same module!")

    if from_module is not None:
        from_module.connections += 1
    to_module.connections += 1

    if deploy:
        id = Connection.get_connection_id() # incremental ID
        key = _generate_key(from_module, to_module, encryption) # auto-generated key
        nonce = 0 # only used for direct connections
    else:
        id = conn_dict['id']
        key = _parse_key(conn_dict['key'])
        nonce = conn_dict['nonce']

    return Connection(from_module, from_output, to_module, to_input, encryption, key, id, direct, nonce)


def _load_periodic_event(events_dict, config):
    module = config.get_module(events_dict['module'])
    entry = events_dict['entry']
    frequency = _parse_frequency(events_dict['frequency'])

    return PeriodicEvent(module, entry, frequency)


def _generate_key(module1, module2, encryption):
    if (module1 is not None and encryption not in module1.get_supported_encryption()) \
        or encryption not in module2.get_supported_encryption():
       raise Error('Encryption "{}" not supported between {} and {}'.format(
            encryption, module1.name, module2.name))

    return tools.generate_key(encryption.get_key_size())


def _parse_vendor_id(id):
    if not 1 <= id <= 2**16 - 1:
        raise Error('Vendor ID out of range')

    return id


def _parse_sancus_key(key_str):
    if key_str is None:
        return None

    key = binascii.unhexlify(key_str)

    keysize = tools.get_sancus_key_size()

    if len(key) != keysize:
        raise Error('Keys should be {} bytes'.format(keysize))

    return key


def _parse_key(key_str):
    if key_str is None:
        return None

    return binascii.unhexlify(key_str)


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
    'native': _load_native_node
}


_module_load_funcs = {
    'sancus': _load_sancus_module,
    'sgx': _load_sgx_module,
    'native': _load_native_module
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
        "features": module.features,
        "id": module.id,
        "binary": _dump(module.binary),
        "sgxs": _dump(module.sgxs),
        "signature": _dump(module.sig),
        "key": _dump(module.key),
        "inputs": _dump(module.inputs),
        "outputs": _dump(module.outputs),
        "entrypoints": _dump(module.entrypoints)
    }


@_dump.register(NativeNode)
def _(node):
    return {
        "type": "native",
        "name": node.name,
        "ip_address": str(node.ip_address),
        "reactive_port": node.reactive_port,
        "deploy_port": node.deploy_port
    }


@_dump.register(NativeModule)
def _(module):
    return {
        "type": "native",
        "name": module.name,
        "node": module.node.name,
        "features": module.features,
        "id": module.id,
        "binary": _dump(module.binary),
        "key": _dump(module.key),
        "inputs": _dump(module.inputs),
        "outputs": _dump(module.outputs),
        "entrypoints": _dump(module.entrypoints)
    }


@_dump.register(Connection)
def _(conn):
    from_module = None if conn.direct else conn.from_module.name

    return {
        "from_module": from_module,
        "from_output": conn.from_output,
        "to_module": conn.to_module.name,
        "to_input": conn.to_input,
        "encryption": conn.encryption.to_str(),
        "key": _dump(conn.key),
        "id": conn.id,
        "direct": conn.direct,
        "nonce": conn.nonce
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
