import base64
import asyncio
import sancus.crypto
from enum import IntEnum

from . import tools
from . import glob

class Encryption(IntEnum):
    AES         = 0x0
    SPONGENT    = 0x1

    @staticmethod
    def from_str(str):
        lower_str = str.lower()

        if lower_str == "aes":
            return Encryption.AES
        if lower_str == "spongent":
            return Encryption.SPONGENT

        raise Error("No matching encryption type for {}".format(str))

    def to_str(self):
        if self == Encryption.AES:
            return "aes"
        if self == Encryption.SPONGENT:
            return "spongent"

    def get_key_size(self):
        if self == Encryption.AES:
            return 16
        if self == Encryption.SPONGENT:
            return tools.get_sancus_key_size()

    async def encrypt(self, key, ad, data):
        if self == Encryption.AES:
            return await encrypt_aes(key, ad, data)
        if self == Encryption.SPONGENT:
            return await encrypt_spongent(key, ad, data)


async def encrypt_aes(key, ad, data):
    args = [base64.b64encode(ad).decode(),
            base64.b64encode(data).decode(),
            base64.b64encode(key).decode()]

    out = await tools.run_async_output(glob.ENCRYPTOR, *args)
    return base64.b64decode(out)


async def encrypt_spongent(key, nonce, data):
    cipher, tag = sancus.crypto.wrap(connection.key,
                                    tools.pack_int16(connection.nonce),
                                    data)

    return cipher + tag
