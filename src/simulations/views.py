import os

from aiohttp import web

from src.simulations.models import Simulation
from src.utils import find_in_dir, RouteTableDefDocs, try_get, dumps, try_get_all, get_client

routes = RouteTableDefDocs()


@routes.get('/simulations/', name='simulation_list')
async def simulation_list(request: web.Request):
    """List all simulations.

    Append an id to get more information about a listed simulation.
    Append /create to create a new simulation.
    """

    return web.json_response(request.app['simulations'], dumps=dumps)


@routes.post('/simulations/create', name='simulation_create')
async def simulation_create(request: web.Request):
    """Create a new simulation from post request.

    Post params:
    - id: id of created simulation
    - fmu: id of fmu to be used
    - datasource: id of datasource to use as input to simulation
    - output_ref: reference values to the outputs to be used
    - input_ref: reference values to the inputs to be used
    - measurement_ref: reference values to the measurement inputs to be used for the inputs.
      Must be in the same order as input_ref.
    - measurement_proportions: scale to be used on measurement values before inputting them.
      Must be in the same order as input_ref.
    - time_input_ref: timestep input reference for Fedem fmus.
      Will not be used if set to -1
    - time_measurement_ref: timestep measurement reference
    """

    post = await request.post()
    sim_id = try_get(post, 'id')  # TODO: Generate id instead?
    fmu = try_get(post, 'fmu')
    datasource_id = try_get(post, 'datasource')
    datasource = request.app['datasources'].get_source(datasource_id)
    try:
        input_refs = await try_get_all(post, 'input_ref', int)
        measurement_refs = await try_get_all(post, 'measurement_ref', int)
        measurement_proportions = await try_get_all(post, 'measurement_proportion', float)
        output_refs = await try_get_all(post, 'output_ref', int)
        time_input_ref = int(post.get('time_input_ref', '-1'))
        time_measurement_ref = int(post.get('time_measurement_ref', '-1'))
    except ValueError:
        raise web.HTTPUnprocessableEntity(reason='An unprocessable ref was given')
    sim: Simulation = Simulation(
        sim_id=sim_id,
        fmu=fmu,
        fmu_dir=request.app['settings'].FMU_DIR,
        datasource=datasource,
        time_input_ref=time_input_ref,
        time_measurement_ref=time_measurement_ref,
        sim_root_dir=request.app['settings'].SIMULATION_DIR,
        kafka_server=request.app['settings'].KAFKA_SERVER,
    )
    request.app['simulations'][sim_id] = sim
    sim.set_inputs(input_refs, measurement_refs, measurement_proportions)
    sim.set_outputs(output_refs)
    sim.start()
    raise web.HTTPAccepted()


@routes.get('/simulations/{id}', name='simulation_detail')
async def simulation_detail(request: web.Request):
    """Information about the simulation with the given id.

    To get the simulations result file append /res
    To get the simulations models append /models/
    To set the simulation outputs append /outputs
    To set the simulation inputs append /inputs
    To stop the simulation append /stop
    """

    return web.json_response(request.app['simulations'][request.match_info['id']].dict_repr())


@routes.post('/simulations/{id}/outputs', name='simulation_outputs_update')
async def simulation_outputs_update(request: web.Request):
    """Update the simulation outputs

        Post params:
        - output_ref: reference values to the outputs to be used
    """

    post = await request.post()
    sim_id = request.match_info['id']
    output_refs = await try_get_all(post, 'output_ref', int)
    request.app['simulations'][sim_id].set_outputs(output_refs)
    raise web.HTTPAccepted()


@routes.post('/simulations/{id}/inputs', name='simulation_inputs_update')
async def simulation_inputs_update(request: web.Request):
    """Update the simulation inputs

        Post params:
        - input_ref: reference values to the inputs to be used
        - measurement_ref: reference values to the measurement inputs to be used for the inputs.
          Must be in the same order as input_ref.
        - measurement_proportions: scale to be used on measurement values before inputting them.
          Must be in the same order as input_ref.
    """

    post = await request.post()
    sim_id = request.match_info['id']
    input_refs = await try_get_all(post, 'input_ref', int)
    measurement_refs = await try_get_all(post, 'measurement_ref', int)
    measurement_proportions = await try_get_all(post, 'measurement_proportion', float)
    request.app['simulations'][sim_id].set_inputs(input_refs, measurement_refs, measurement_proportions)
    raise web.HTTPAccepted()


@routes.get('/simulations/{id}/res', name='simulation_res')
async def simulation_res(request: web.Request):
    """Get the result file from the simulation."""
    sim_dir = await find_in_dir(request.match_info['id'], request.app['settings'].SIMULATION_DIR)
    return web.FileResponse(os.path.join(sim_dir, 'resources', 'model', 'fedem_solver.res'))


@routes.get('/simulations/{id}/models', name='simulation_models')
async def simulation_models(request: web.Request):
    """List the models in the given simulation.

    Append the model name to download the model file.
    """

    sim_dir = await find_in_dir(request.match_info['id'], request.app['settings'].SIMULATION_DIR)
    model_dir = os.path.join(sim_dir, 'resources', 'link_DB')
    files = next(os.walk(model_dir))[2]
    return web.json_response(files)


@routes.get('/simulations/{id}/models/{model}', name='simulation_model_file')
async def simulation_model_file(request: web.Request):
    """Download the given model file."""
    sim_dir = await find_in_dir(request.match_info['id'], request.app['settings'].SIMULATION_DIR)
    model_dir = os.path.join(sim_dir, 'resources', 'link_DB')
    model_file = await find_in_dir(request.match_info['model'], model_dir)
    return web.FileResponse(model_file)


@routes.get('/simulations/{id}/subscribe', name='simulation_subscribe')
async def simulation_subscribe(request: web.Request):
    """Subscribe to the simulation with the given id"""
    client = await get_client(request)
    simulation_id = request.match_info['id']
    if simulation_id in request.app['simulations']:
        topic = request.app['simulations'][simulation_id].topic
        request.app['subscribers'][topic].add(client)
        raise web.HTTPOk()
    raise web.HTTPNotFound()


@routes.post('/simulations/{id}/stop', name='simulation_stop')
async def simulation_stop(request: web.Request):
    """Stop the simulation."""
    simulation_id = request.match_info['id']
    if simulation_id not in request.app['simulations']:
        return web.json_response({
            'status': 'failed',
            'message': f'There is no running simulation with id {simulation_id}'
        })
    sim: Simulation = request.app['simulations'][simulation_id]
    sim.stop()
