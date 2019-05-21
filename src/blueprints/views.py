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
    """Get detailed information for the blueprint with the given id

    """
    path = await find_in_dir(request.match_info['id'], request.app['settings'].BLUEPRINT_DIR)
    with open(os.path.join(path, 'main.py'), 'r') as f:
        tree = ast.parse(f.read(), filename='main.py')
    docs = ast.get_docstring(tree)
    process_class = list(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'P')[0]
    init_function = list(n for n in process_class.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')[0]
    init_docs = ast.get_docstring(init_function)
    init_params = [a.arg for a in init_function.args.args[1:]]
    start_function = list(n for n in process_class.body if isinstance(n, ast.FunctionDef) and n.name == 'start')[0]
    start_docs = ast.get_docstring(start_function)
    start_params = [a.arg for a in start_function.args.args[1:]]
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
