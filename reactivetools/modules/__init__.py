from .base import Module
from .sancus import SancusModule
from .native import NativeModule
from .sgx import SGXModule

module_funcs = {
    "sancus"    : SancusModule.load,
    "sgx"       : SGXModule.load,
    "native"    : NativeModule.load
}

module_cleanup_coros = [
    SancusModule.cleanup,
    SGXModule.cleanup,
    NativeModule.cleanup
]
