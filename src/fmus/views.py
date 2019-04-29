import os

from aiohttp import web
from fmpy import read_model_description

from src import simulation
from src.utils import dumps, find_in_dir, RouteTableDefDocs

routes = RouteTableDefDocs()


@routes.get('/fmus/', name='fmu_list')
async def fmu_list(request: web.Request):
    """List all uploaded FMUs.

    Append an FMU id to get more information about a listed FMU.
    """

    return web.json_response(os.listdir(request.app['settings'].FMU_DIR))


@routes.get('/fmus/{id}', name='fmu_detail')
async def fmu_detail(request: web.Request):
    """Get detailed information for the FMU with the given id

    Append /vars to get sorted variables
    """
    file = await find_in_dir(request.match_info['id'], request.app['settings'].FMU_DIR)
    model_description = read_model_description(file)
    return web.json_response(model_description, dumps=dumps)


@routes.get('/fmus/{id}/vars', name='fmu_vars')
async def fmu_vars(request: web.Request):
    """Get sorted variables for the FMU with the given id"""
    file = await find_in_dir(request.match_info['id'], request.app['settings'].FMU_DIR)
    model_variables = simulation.ModelVariables(read_model_description(file))
    return web.json_response(model_variables, dumps=dumps)

