import os

# TODO temporary: should be an argument or something else
APP_PATH = "/home/gianlu33/Desktop/authentic-execution-sgx/app/"

# SGX build / sign
SGX_TARGET="x86_64-fortanix-unknown-sgx"
RA_SP_PUB_KEY = os.path.join(APP_PATH, "remote_attestation","ra_sp", "data", "keys", "public_key.pem")
VENDOR_PRIVATE_KEY = os.path.join(APP_PATH, "data", "vendor_keys", "private_key.pem")
