import functools
import json
import os

from aiohttp import web


def make_serializable(o):
    # if hasattr(o, 'dict_repr'):
    #     return o.dict_repr()
    if hasattr(o, '__dict__'):
        return {k: v for k, v in o.__dict__.items() if not k.startswith('_')}
    return str(o)


dumps = functools.partial(json.dumps, default=make_serializable)


async def find_in_dir(filename, parent_directory=''):
    dir, file = os.path.split(filename)
    if dir is '' and file in os.listdir(parent_directory):
        path = os.path.join(parent_directory, file)
    else:
        raise web.HTTPNotFound()
    return path