import functools
import json
import os
import re
from typing import Any

from aiohttp import web, hdrs
from aiohttp.web_routedef import _Deco, _HandlerType, RouteDef
from aiohttp_session import Session, get_session


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


def try_get(post, key, parser=None):
    try:
        value = post[key]
        if parser:
            try:
                return parser(post[key])
            except ValueError:
                raise web.HTTPBadRequest(
                    reason=f'The value {value} from {key} was not parsable as {parser.__name__}'
                )
        return value
    except KeyError:
        raise web.HTTPUnprocessableEntity(reason=f'{key} is missing')


async def try_get_all(post, key, parser=None):
    try:
        if parser is not None:
            return [parser(s) for s in post.getall(key)]
        return [s for s in post.getall(key)]
    except KeyError:
        raise web.HTTPUnprocessableEntity(
            reason=f'Attempted to get {key} from request and failed'
        )
    except ValueError:
        raise web.HTTPBadRequest(
            reason=f'A value from {key} was not parsable as {parser.__name__}'
        )

validator_string = r'\A[a-zA-Z_][a-zA-Z0-9_]{0,20}\Z'

validator = re.compile(r'\A[a-zA-Z_][a-zA-Z0-9_]{0,20}\Z')


def try_get_validate(post, key):
    value = try_get(post, key)
    if not validator.match(value):
        raise web.HTTPUnprocessableEntity(reason=f'invalid {key} value, must match {validator_string}')
    return value


topic_validator = re.compile(r'\A[0-9]{0,4}\Z')


def try_get_topic(post):
    value = try_get(post, 'topic')
    if not topic_validator.match(value):
        raise web.HTTPUnprocessableEntity(reason=f'invalid topic value')
    return value


async def get_client(request):
    session: Session = await get_session(request)
    if 'id' not in session or session['id'] not in request.app['clients']:
        raise web.HTTPForbidden()
    client = request.app['clients'][session['id']]
    return client
