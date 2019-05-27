import ast
import os

from aiohttp import web

from src.utils import RouteTableDefDocs, find_in_dir, dumps

routes = RouteTableDefDocs()


@routes.get('/blueprints/', name='blueprint_list')
async def blueprint_list(request: web.Request):
    """List all uploaded blueprints.

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
    init_docs, init_params = await retrieve_function_info(process_class.body, '__init__')
    start_docs, start_params = await retrieve_function_info(process_class.body,'start', 2)
    # input_names_def = list(n for n in process_class.body if isinstance(n, ast.Assign) and 'input_names' == n.targets[0].id)[-1].value
    # input_names = [name.s for name in input_names_def.elts]
    return web.json_response({
        'docs': docs,
        'init_docs': init_docs,
        'init_params': init_params,
        'start_docs': start_docs,
        'start_params': start_params,
        # 'input_names': input_names,
    }, dumps=dumps)


async def retrieve_function_info(body, function_name, end_ignore_args_index=1):
    function = list(n for n in body if isinstance(n, ast.FunctionDef) and n.name == function_name)[0]
    docs = ast.get_docstring(function)
    params = [{'name': a.arg, 'default': ''}
                    for a in function.args.args[end_ignore_args_index:]]
    defaults_start_index = len(params) - len(function.args.defaults)
    for i, v in enumerate(function.args.defaults):
        params[defaults_start_index + i]['default'] = getattr(v, v._fields[0], '')
    return docs, params
