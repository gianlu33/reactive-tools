import yaml
import os
import logging

__deploy = None

def is_present(dict, key):
    return key in dict and dict[key] is not None

def has_value(dict, key, value):
    return is_present(dict, key) and dict[key] == value

def authorized_keys(dict, keys):
    for key in dict:
        if key not in keys:
            return False

    return True

def set_deploy(deploy):
    global __deploy
    __deploy = deploy

def is_deploy():
    return __deploy


# folder, file: names (not paths!) of a folder in this directory and the file in the folder where the rules are stored
# e.g., nodes/sancus.yaml -> folder == "nodes", file == "sancus.yaml"
def load_rules(folder, file):
    try:
        path = os.path.join(os.path.dirname(__file__), folder, file)
        with open(path) as f:
            data = yaml.load(f, Loader=yaml.FullLoader)

        return data if data is not None else {}
    except:
        logging.warning("Something went wrong during load of {}".format(file))
        return {}
