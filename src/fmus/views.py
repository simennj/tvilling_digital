import os

from aiohttp import web
from fmpy import read_model_description

from src.settings import FMU_DIR
from src.utils import dumps, find_in_dir

routes = web.RouteTableDef()


@routes.get('/fmus/', name='fmu_list')
async def fmu_list(request: web.Request):
    return web.json_response(os.listdir(FMU_DIR))


@routes.get('/fmus/{id}', name='fmu_detail')
async def fmu_detail(request: web.Request):
    file = await find_in_dir(request.match_info['id'], FMU_DIR)
    model_description = read_model_description(file)
    return web.json_response(model_description, dumps=dumps)
