import json
import binascii
import ipaddress
import os
import asyncio
import logging

from .modules import Module
from .nodes import Node
from .connection import Connection
from .crypto import Encryption
from .periodic_event import PeriodicEvent
from . import tools
from .dumpers import *
from .loaders import *

from .nodes import node_funcs, node_cleanup_coros
from .modules import module_funcs, module_cleanup_coros

class Error(Exception):
    pass


class Config:
    def __init__(self):
        self.nodes = []
        self.modules = []
        self.connections = []


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


    def get_connection_by_id(self, id):
        for c in self.connections:
            if c.id == id:
                return c

        raise Error('No connection with ID {}'.format(id))


    def get_connection_by_name(self, name):
        for c in self.connections:
            if c.name == name:
                return c

        raise Error('No connection with name {}'.format(name))


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


    async def build_async(self):
        futures = [module.build() for module in self.modules]
        await asyncio.gather(*futures)


    def build(self):
        asyncio.get_event_loop().run_until_complete(self.build_async())


    async def cleanup_async(self):
        coros = list(map(lambda c: c(), node_cleanup_coros + module_cleanup_coros))
        await asyncio.gather(*coros)


    def cleanup(self):
        asyncio.get_event_loop().run_until_complete(self.cleanup_async())


    async def deploy_priority_modules(self):
        priority_modules = [sm for sm in self.modules if sm.priority is not None]
        priority_modules.sort(key=lambda sm : sm.priority)

        logging.debug("Priority modules: {}".format([sm.name for sm in priority_modules]))
        for module in priority_modules:
            await module.deploy()


def load(file_name, deploy=True):
    with open(file_name, 'r') as f:
        contents = json.load(f)

    config = Config()

    config.nodes = load_list(contents['nodes'], _load_node)
    config.modules = load_list(contents['modules'],
                                lambda m: _load_module(m, config))

    if 'connections' in contents:
        config.connections = load_list(contents['connections'],
                                        lambda c: _load_connection(c, config, deploy))
    else:
        config.connections = []

    if 'periodic-events' in contents:
        config.periodic_events = load_list(contents['periodic-events'],
                                        lambda e: _load_periodic_event(e, config))
    else:
        config.periodic_events = []

    return config


def _load_node(node_dict):
    return node_funcs[node_dict['type']](node_dict)


def _load_module(mod_dict, config):
    node = config.get_node(mod_dict['node'])
    return module_funcs[mod_dict['type']](mod_dict, node)


def _load_connection(conn_dict, config, deploy):
    evaluate_rules(connection_rules(conn_dict, deploy))

    direct = conn_dict.get('direct')
    from_module = config.get_module(conn_dict['from_module']) if is_present(conn_dict, 'from_module') else None
    from_output = conn_dict.get('from_output')
    from_request = conn_dict.get('from_request')
    to_module = config.get_module(conn_dict['to_module'])
    to_input = conn_dict.get('to_input')
    to_handler = conn_dict.get('to_handler')
    encryption = Encryption.from_str(conn_dict['encryption'])
    key = parse_key(conn_dict.get('key'))
    nonce = conn_dict.get('nonce')
    id = conn_dict.get('id')
    name = conn_dict.get('name')

    if deploy:
        id = Connection.get_connection_id() # incremental ID
        key = _generate_key(from_module, to_module, encryption) # auto-generated key
        nonce = 0 # only used for direct connections

    if from_module is not None:
        from_module.connections += 1
    to_module.connections += 1

    if name is None:
        name = "conn{}".format(id)

    return Connection(name, from_module, from_output, from_request, to_module,
        to_input, to_handler, encryption, key, id, nonce, direct)


def _load_periodic_event(events_dict, config):
    module = config.get_module(events_dict['module'])
    entry = events_dict['entry']
    frequency = parse_positive_number(events_dict['frequency'], bits=32)

    return PeriodicEvent(module, entry, frequency)


def _generate_key(module1, module2, encryption):
    if (module1 is not None and encryption not in module1.get_supported_encryption()) \
        or encryption not in module2.get_supported_encryption():
       raise Error('Encryption {} not supported between {} and {}'.format(
            str(encryption), module1.name, module2.name))

    return tools.generate_key(encryption.get_key_size())


def dump_config(config, file_name):
    with open(file_name, 'w') as f:
        json.dump(dump(config), f, indent=4)


@dump.register(list)
def _(l):
    return [dump(e) for e in l]


@dump.register(Config)
def _(config):
    dump(config.nodes)
    return {
            'nodes': dump(config.nodes),
            'modules': dump(config.modules),
            'connections': dump(config.connections),
            'periodic-events' : dump(config.periodic_events)
        }


@dump.register(Node)
def _(node):
    return node.dump()


@dump.register(Module)
def _(module):
    return module.dump()


@dump.register(Connection)
def _(conn):
    from_module = None if conn.direct else conn.from_module.name

    return {
        "name": conn.name,
        "from_module": from_module,
        "from_output": conn.from_output,
        "from_request": conn.from_request,
        "to_module": conn.to_module.name,
        "to_input": conn.to_input,
        "to_handler": conn.to_handler,
        "encryption": conn.encryption.to_str(),
        "key": dump(conn.key),
        "id": conn.id,
        "direct": conn.direct,
        "nonce": conn.nonce
    }


@dump.register(PeriodicEvent)
def _(event):
    return {
        "module": event.module.name,
        "entry": event.entry,
        "frequency": event.frequency
    }


# Rules
def evaluate_rules(rules):
    bad_rules = [r for r in rules if not rules[r]]

    for rule in bad_rules:
        logging.error("Broken rule: {}".format(rule))

    if bad_rules:
        raise Error("Bad JSON configuration")


def is_present(dict, key):
    return key in dict and dict[key] is not None

def has_value(dict, key, value):
    return is_present(dict, key) and dict[key] == value

def authorized_keys(dict, keys):
    for key in dict:
        if key not in keys:
            return False

    return True

def connection_rules(dict, deploy):
    return {
        "to_module not present":
            is_present(dict, "to_module"),
        "encryption not present":
            is_present(dict, "encryption"),

        "either direct=True or from_module + from_{output, request}":
            has_value(dict, "direct", True) != (is_present(dict, "from_module") \
            and (is_present(dict, "from_output") != is_present(dict, "from_request"))),

        "either one between to_input and to_handler":
            is_present(dict, "to_input") != is_present(dict, "to_handler"),

        "direct or from_output->to_input or from_request->to_handler":
            has_value(dict, "direct", True) or (is_present(dict, "from_output") and is_present(dict, "to_input")) \
            or (is_present(dict, "from_request") and is_present(dict, "to_handler")),

        "key present ONLY after deployment":
            (deploy and not is_present(dict, "key")) or (not deploy and is_present(dict, "key")),

        "nonce present ONLY after deployment":
            (deploy and not is_present(dict, "nonce")) or (not deploy and is_present(dict, "nonce")),

        "id present ONLY after deployment":
            (deploy and not is_present(dict, "id")) or (not deploy and is_present(dict, "id")),

        "name mandatory after deployment":
            deploy or (not deploy and is_present(dict, "name")),

        "direct mandatory after deployment":
            deploy or (not deploy and is_present(dict, "direct")),

        "from_module and to_module must be different":
            dict.get("from_module") != dict["to_module"],

        "only authorized keys":
            authorized_keys(dict, ["name", "from_module", "from_output",
                "from_request", "to_module", "to_input", "to_handler",
                "encryption", "key", "id", "direct", "nonce"])
    }
