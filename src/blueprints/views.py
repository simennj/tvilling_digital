import ast
import os
from typing import Tuple, List

from aiohttp import web

from src.utils import RouteTableDefDocs, find_in_dir, dumps

routes = RouteTableDefDocs()


@routes.get('/blueprints/', name='blueprint_list')
async def blueprint_list(request: web.Request):
    """
    List all uploaded blueprints.

    Append a blueprint id to get more information about a listed blueprint.
    """

    return web.json_response(os.listdir(request.app['settings'].BLUEPRINT_DIR))


@routes.get('/blueprints/{id}', name='blueprint_detail')
async def blueprint_detail(request: web.Request):
    """Get detailed information for the blueprint with the given id"""
    path = await find_in_dir(request.match_info['id'], request.app['settings'].BLUEPRINT_DIR)
    with open(os.path.join(path, '__init__.py'), 'r') as f:
        tree = ast.parse(f.read(), filename='__init__.py')
    docs = ast.get_docstring(tree)
    process_class = list(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'P')[0]
    init_docs, init_params = await retrieve_method_info(process_class.body, '__init__')
    start_docs, start_params = await retrieve_method_info(process_class.body, 'start', 2)
    return web.json_response({
        'docs': docs,
        'init_docs': init_docs,
        'init_params': init_params,
        'start_docs': start_docs,
        'start_params': start_params,
    }, dumps=dumps)


async def retrieve_method_info(class_body, method_name, params_ignore=1) -> Tuple[str, List]:
    """
    Retrieves docs and parameters from the method

    :param class_body: the body of the class the method belongs to
    :param method_name: the name of the method
    :param params_ignore: how many of the first params to ignore, defaults to 1 (only ignore self)
    :return: a tuple containing both the docstring of the method and a list of parameters with name and default value
    """
    function = list(n for n in class_body if isinstance(n, ast.FunctionDef) and n.name == method_name)[0]
    docs: str = ast.get_docstring(function)
    params = [{'name': a.arg, 'default': ''}
              for a in function.args.args[params_ignore:]]
    defaults_start_index = len(params) - len(function.args.defaults)
    for i, v in enumerate(function.args.defaults):
        params[defaults_start_index + i]['default'] = getattr(v, v._fields[0], '')
    return docs, params
