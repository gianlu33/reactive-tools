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
