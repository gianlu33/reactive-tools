import binascii
import os

from . import tools

class Error(Exception):
    pass


def load_list(l, load_func=lambda e: e):
    if l is None:
        return []
    else:
        return [load_func(e) for e in l]


def parse_vendor_id(id):
    if not 1 <= id <= 2**16 - 1:
        raise Error('Vendor ID out of range')

    return id


def parse_sancus_key(key_str):
    if key_str is None:
        return None

    key = binascii.unhexlify(key_str)

    keysize = tools.get_sancus_key_size()

    if len(key) != keysize:
        raise Error('Keys should be {} bytes'.format(keysize))

    return key


def parse_key(key_str):
    if key_str is None:
        return None

    return binascii.unhexlify(key_str)


def parse_frequency(freq):
    if not 1 <= freq <= 2**32 - 1:
        raise Error('Frequency out of range')

    return freq


def parse_file_name(file_name):
    return os.path.abspath(file_name)
