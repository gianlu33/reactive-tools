import os
from pathlib import Path

# TODO temporary: should be an argument or something else
APP_PATH = "{}/Desktop/authentic-execution-sgx/app/".format(str(Path.home()))

# SGX build / sign
SGX_TARGET="x86_64-fortanix-unknown-sgx"
RA_SP_PUB_KEY = os.path.join(APP_PATH, "remote_attestation","ra_sp", "data", "keys", "public_key.pem")
VENDOR_PRIVATE_KEY = os.path.join(APP_PATH, "data", "vendor_keys", "private_key.pem")

# Apps
ENCRYPTOR = os.path.join(APP_PATH, "set_key_encryptor", "Cargo.toml")
RA_SP = os.path.join(APP_PATH, "remote_attestation", "ra_sp", "Cargo.toml")
RA_CLIENT = os.path.join(APP_PATH, "remote_attestation", "ra_client", "Cargo.toml")

# cargo commands
BUILD_APP = "cargo build --manifest-path={}/Cargo.toml"
BUILD_SGX_APP = "{} --target={}".format(BUILD_APP, SGX_TARGET)
CONVERT_SGX = "ftxsgx-elf2sgxs {} --heap-size 0x20000 --stack-size 0x20000 --threads 2 --debug"
SIGN_SGX = "sgxs-sign --key {} {{}} {{}} -d --xfrm 7/0 --isvprodid 0 --isvsvn 0".format(VENDOR_PRIVATE_KEY)
