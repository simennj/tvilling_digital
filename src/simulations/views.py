import asyncio
import os

from aiohttp import web
from aiohttp_session import get_session

from src.connections import Simulation, get_or_create_retriever
from src.settings import SIMULATION_DIR
from src.utils import find_in_dir

routes = web.RouteTableDef()


@routes.get('/simulations/', name='simulation_list')
async def simulation_list(request: web.Request):
    return web.json_response({id: s.dict_repr() for id, s in request.app['simulations'].items()})


@routes.post('/simulations/create', name='simulation_create')
async def simulation_start(request: web.Request):
    post = await request.post()
    _, retriever = await get_or_create_retriever(request)
    session_id = (await get_session(request))['id']
    simulation_id = post['id']
    sim: Simulation = Simulation(asyncio.get_event_loop(), post['fmu'], retriever.byte_format)
    request.app['simulations'][simulation_id] = sim
    client = request.app['ws'][session_id]
    sim.output_refs = [int(s) for s in post.getall('output_refs')]  # [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    input_refs = [int(s) for s in post.getall('input_refs')]
    measurement_refs = [int(s) for s in post.getall('measurement_refs')]
    sim.set_inputs(input_refs, measurement_refs)
    return web.HTTPTemporaryRedirect(
        request.app.router['simulation'].url_for(id=simulation_id)
    )


@routes.get('/simulations/{id}', name='simulation_detail')
async def simulation_detail(request: web.Request):
    return web.json_response(request.app['simulations'][request.match_info['id']].dict_repr())


@routes.get('/simulations/{id}/res', name='simulation_res')
async def simulation_res(request: web.Request):
    sim_dir = await find_in_dir(request.match_info['id'], SIMULATION_DIR)
    return web.FileResponse(os.path.join(sim_dir, 'resources', 'model', 'fedem_solver.res'))


@routes.get('/simulations/{id}/models', name='simulation_models')
async def simulation_models(request: web.Request):
    sim_dir = await find_in_dir(request.match_info['id'], SIMULATION_DIR)
    model_dir = os.path.join(sim_dir, 'resources', 'link_DB')
    files = next(os.walk(model_dir))[2]
    return web.json_response(files)


@routes.get('/simulations/{id}/models/{model}', name='simulation_model_file')
async def simulation_model_file(request: web.Request):
    sim_dir = await find_in_dir(request.match_info['id'], SIMULATION_DIR)
    model_dir = os.path.join(sim_dir, 'resources', 'link_DB')
    model_file = await find_in_dir(request.match_info['model'], model_dir)
    return web.FileResponse(model_file)


@routes.post('/simulations/{id}/stop', name='simulation_stop')
async def simulation_stop(request: web.Request):
    simulation_id = request.match_info['id']
    if simulation_id not in request.app['simulations']:
        return web.json_response({
            'status': 'failed',
            'message': f'There is no running simulation with id {simulation_id}'
        })
    sim: Simulation = request.app['simulations'][simulation_id]
    sim.stop()
