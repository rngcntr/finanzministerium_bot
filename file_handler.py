import simplejson

def read_token (secret_token_filename):
    secret_token_file = open(secret_token_filename, "r")
    secret_token = secret_token_file.readline().strip()
    secret_token_file.close()
    return secret_token

def write_dict (dict_obj, filename):
    json_dict = simplejson.dumps(dict_obj)
    f = open(filename, "w")
    f.write(json_dict)
    f.close()

def load_dict (filename):
    f = open(filename, "r")
    json_dict = f.read()
    return simplejson.loads(json_dict)
