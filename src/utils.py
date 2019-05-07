import functools
import json
import os
from typing import Any

from aiohttp import web, hdrs
from aiohttp.web_routedef import _Deco, _HandlerType, RouteDef


def make_serializable(o):
    # if hasattr(o, 'asdict'):
    #     return o.asdict()
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


class RouteTableDefDocs(web.RouteTableDef):

    @staticmethod
    def get_docs_response(handler):
        async def asdf(request: web.Request):
            return web.Response(text=handler.__doc__ or "The given route has no docs.")

        return asdf

    def route(self, method: str, path: str, **kwargs: Any) -> _Deco:
        def inner(handler: _HandlerType) -> _HandlerType:
            self._items.append(RouteDef(method, path, handler, kwargs))
            self._items.append(RouteDef(hdrs.METH_GET, '/docs' + path, self.get_docs_response(handler), {}))
            return handler

        return inner


def try_get(post, key):
    try:
        return post[key]
    except KeyError:
        raise web.HTTPUnprocessableEntity(reason=f'Attempted to get {key} from request and failed')


async def try_get_all(post, key, parser=None):
    try:
        if parser is not None:
            return [parser(s) for s in post.getall(key)]
        return [s for s in post.getall(key)]
    except KeyError:
        raise web.HTTPUnprocessableEntity(reason=f'Attempted to get {key} from request and failed')
