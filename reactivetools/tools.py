import logging
import tempfile
import os
import asyncio
import base64


class ProcessRunError(Exception):
    def __init__(self, args, result):
        self.args = args
        self.result = result

    def __str__(self):
        return 'Command "{}" exited with code {}' \
                    .format(' '.join(self.args), self.result)


async def run_async(*args):
    logging.info(' '.join(args))
    process = await asyncio.create_subprocess_exec(*args)
    result = await process.wait()

    if result != 0:
        raise ProcessRunError(args, result)


async def run_async_muted(*args, output_file=os.devnull):
    logging.info(' '.join(args))
    process = await asyncio.create_subprocess_exec(*args, stdout=open(output_file, 'wb'), stderr=asyncio.subprocess.STDOUT)
    result = await process.wait()

    if result != 0:
        raise ProcessRunError(args, result)


async def run_async_background(*args):
    logging.info(' '.join(args))
    process = await asyncio.create_subprocess_exec(*args, stdout=open(os.devnull, 'wb'), stderr=asyncio.subprocess.STDOUT)

    return process


async def run_async_output(*args):
    logging.info(' '.join(args))
    process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await process.communicate()

    #logging.info(err)

    return out


async def run_async_shell(*args):
    cmd = ' '.join(args)
    logging.info(cmd)
    process = await asyncio.create_subprocess_shell(cmd, stdout=open(os.devnull, 'wb'), stderr=asyncio.subprocess.STDOUT)
    result = await process.wait()

    if result != 0:
        raise ProcessRunError(args, result)


def create_tmp(suffix=''):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def create_tmp_dir():
    return tempfile.mkdtemp()


# just used for NoSGX modules, so for testing
def generate_key(length):
    return os.urandom(length)
