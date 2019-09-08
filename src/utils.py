import functools
import json
import os
import re
from typing import Any

from aiohttp import web, hdrs
from aiohttp.web_routedef import _Deco, _HandlerType, RouteDef
from aiohttp_session import Session, get_session


def make_serializable(o):
    """Makes the given object JSON serializable by turning it into a structure of dicts and strings."""
    # if hasattr(o, 'asdict'):
    #     return o.asdict()
    if hasattr(o, 'dict_repr'):
        return o.dict_repr()
    if hasattr(o, '__dict__'):
        return {k: v for k, v in o.__dict__.items() if not k.startswith('_')}
    return str(o)


dumps = functools.partial(json.dumps, default=make_serializable)
dumps.__doc__ = """A version of json.dumps that uses make serializable recursively to make objects serializable"""


async def find_in_dir(filename, parent_directory=''):
    """Checks if the given file is present in the given directory and returns the file if found.
     Raises a HTTPNotFound exception otherwise
     """
    dir, file = os.path.split(filename)
    if dir is '' and file in os.listdir(parent_directory):
        path = os.path.join(parent_directory, file)
    else:
        raise web.HTTPNotFound()
    return path


class RouteTableDefDocs(web.RouteTableDef):
    """A custom RouteTableDef that also creates /docs pages with the docstring of the functions."""

    @staticmethod
    def get_docs_response(handler):
        """Creates a new function that returns the docs of the given function"""
        async def f(request: web.Request):
            return web.Response(text=handler.__doc__ or "The given route has no docs.")

        return f

    def route(self, method: str, path: str, **kwargs: Any) -> _Deco:
        """Adds the given function to routes, then attempts to add the docstring of the function to /docs"""
        def inner(handler: _HandlerType) -> _HandlerType:
            self._items.append(RouteDef(method, path, handler, kwargs))
            self._items.append(RouteDef(hdrs.METH_GET, '/docs' + path, self.get_docs_response(handler), {}))
            return handler

        return inner


def try_get(post, key, parser=None):
    """
    Attempt to get the value with key from post.

    :param post: The post request the value will be retrieved from
    :param key: Key used to retrieve the value
    :param parser: Will be used to parse the retrieved value if given
    :return: The retrieved and parsed value.
             Returns the first value if more than one value is found.
    :raise web.HTTPUnprocessableEntity: If a value with the given key is not found
    :raise web.HTTPBadRequest: If parsing of the value failed
    """
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
    """Attempt to get all values with the given key from the given post request.
    Attempts to parse the values using the parser if a parser is given.
    Raises a HTTPException if the key is not found or the parsing fails.
    """
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
    """Attempt to get the value with the given key from the given post request.
    Returns the first value if more than one value is found.
    Attempts to validate the value with the validator strings if found.
    Raises a HTTPException if the key is not found or the validation fails.
    """
    value = try_get(post, key)
    if not validator.match(value):
        raise web.HTTPUnprocessableEntity(reason=f'invalid {key} value, must match {validator_string}')
    return value


topic_validator = re.compile(r'\A[0-9]{0,4}\Z')


def try_get_topic(post):
    """Attempt to get the topic value from the given post request.
    Attempts to validate the topic value with the topic validator strings if found.
    Raises a HTTPException if the key is not found or the validation fails.
    """
    value = try_get(post, 'topic')
    if not topic_validator.match(value):
        raise web.HTTPUnprocessableEntity(reason=f'invalid topic value')
    return value


async def get_client(request):
    """Returns the client object belonging to the owner of the request."""
    session: Session = await get_session(request)
    if 'id' not in session or session['id'] not in request.app['clients']:
        raise web.HTTPForbidden()
    client = request.app['clients'][session['id']]
    return client
