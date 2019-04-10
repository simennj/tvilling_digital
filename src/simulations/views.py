import asyncio

from aiohttp import web
from aiohttp_session import get_session

from src.connections import Simulation, get_or_create_retriever

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
    retriever.subscribers[simulation_id] = sim
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
