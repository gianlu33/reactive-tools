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


def parse_key(key_str):
    if key_str is None:
        return None

    return binascii.unhexlify(key_str)


def parse_positive_number(val, bits=16):
    if val is None:
        return None

    if not isinstance(val, int):
        raise Error("value {} is not an integer".format(val))

    if not 1 <= val <= 2**bits - 1:
        raise Error("value {} is not a positive {}-bit number".format(val, bits))

    return val


def parse_file_name(file_name):
    if file_name is None:
        return None

    return os.path.abspath(file_name)
