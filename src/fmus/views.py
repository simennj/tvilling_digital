import os

from aiohttp import web
from fmpy import read_model_description

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

    Append /models to get the 3d models if any
    """
    file = await find_in_dir(request.match_info['id'], request.app['settings'].FMU_DIR)
    model_description = read_model_description(file)
    return web.json_response(model_description, dumps=dumps)


# @routes.get('/fmus/{id}/vars', name='fmu_vars')
# async def fmu_vars(request: web.Request):
#     """Get sorted variables for the FMU with the given id"""
#     file = await find_in_dir(request.match_info['id'], request.app['settings'].FMU_DIR)
#     model_variables = simulation.ModelVariables(read_model_description(file))
#     return web.json_response(model_variables, dumps=dumps)


@routes.get('/fmus/{id}/models/', name='fmu_models')
async def fmu_models(request: web.Request):
    """List the 3d models belonging to the FMU if any exists

    Append the models id the get a specific model
    """
    fmu_id = request.match_info['id']
    fmu_model_root_dir = request.app['settings'].FMU_MODEL_DIR
    models = os.listdir(get_fmu_models_folder(fmu_id, fmu_model_root_dir))
    return web.json_response(models)


def get_fmu_models_folder(fmu_id, fmu_model_dir):
    if fmu_id in os.listdir(fmu_model_dir):
        model_folder = os.path.join(fmu_model_dir, fmu_id)
        return model_folder
    else:
        raise web.HTTPNotFound()


@routes.get('/fmus/{id}/models/{model}', name='fmu_model')
async def fmu_model(request: web.Request):
    """Get a 3d model belonging to the FMU if it exists"""
    fmu_id = request.match_info['id']
    fmu_model_root_dir = request.app['settings'].FMU_MODEL_DIR
    model_dir = get_fmu_models_folder(fmu_id, fmu_model_root_dir)
    model = request.match_info['model']
    if model not in os.listdir(model_dir):
        raise web.HTTPNotFound()
    return web.FileResponse(path=os.path.join(model_dir, model))
