import tiktoken

def registered_encodings_ready():
    names=tiktoken.list_encoding_names()
    return bool(names) and all(tiktoken.get_encoding(name).encode('offline acceptance') for name in names)
