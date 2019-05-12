import ast
import json
import os
from json import JSONDecodeError

from aiohttp import web

from src.filters.models import Filter
from src.utils import dumps, find_in_dir, RouteTableDefDocs, try_get, try_get_all, try_get_validate

routes = RouteTableDefDocs()


@routes.get('/filters/', name='filter_list')
async def filter_list(request: web.Request):
    """List all uploaded filters.

    Append an filter id to get more information about a listed filter.
    Append /create to create a new filter instance
    """

    return web.json_response(os.listdir(request.app['settings'].FILTER_DIR))


@routes.get('/filters/{id}', name='filter_detail')
async def filter_detail(request: web.Request):
    """Get detailed information for the filter with the given id

    """
    path = await find_in_dir(request.match_info['id'], request.app['settings'].FILTER_DIR)
    with open(os.path.join(path, 'main.py'), 'r') as f:
        docs = ast.get_docstring(ast.parse(f.read(), filename='main.py'))
    return web.json_response(docs, dumps=dumps)


@routes.get('/filters/{id}/instances/', name='filter__instance_list')
async def filter_instance_list(request: web.Request):
    """List all instances of filter.

    Append an instance id to get more information about a listed instance.
    Append /create to create a new filter instance
    """

    return web.json_response(os.listdir(request.app['settings'].FILTER_DIR))


@routes.post('/filters/create', name='filter_create')
async def filter_create(request: web.Request):
    """Start a new filter from post request.

    Post params:
    - id:* id of new filter instance (must match [a-zA-Z_][a-zA-Z0-9_]{0,20})
    - filter:* id of filter to be used (must match [a-zA-Z_][a-zA-Z0-9_]{0,20})
    - filter_vars: the filter specific variables as json
    - datasource:* id of datasource to use as input to filter
    - input_ref: reference values to the inputs to be used
    - measurement_ref: reference values to the measurement inputs to be used for the inputs.
      Must be in the same order as input_ref.
    - time_measurement_ref:* timestep measurement reference
    - min_transmit_interval: the shortest time allowed between each transmit from filter
    """

    post = await request.post()
    instance_id = try_get_validate(post, 'id')  # TODO: Generate id instead?
    filter_id = try_get_validate(post, 'filter')
    try:
        filter_vars = json.loads(post.getall('filter_vars', '{}'))
    except JSONDecodeError:
        raise web.HTTPUnprocessableEntity(reason='Could not process filter_vars as json')
    input_refs = await try_get_all(post, 'input_ref', int)
    measurement_refs = await try_get_all(post, 'measurement_ref', int)
    datasource_id = try_get(post, 'datasource')
    datasource = request.app['datasources'].get_source(datasource_id)  # TODO: accept filters
    try:
        time_measurement_ref = int(post.get('time_measurement_ref', '-1'))
        min_transmit_interval = float(post.get('min_transmit_interval', '0'))
    except ValueError:
        raise web.HTTPUnprocessableEntity(reason='An unprocessable time ref was given')
    filter_instance: Filter = Filter(
        instance_id=instance_id,
        filter_id=filter_id,
        source_topic=datasource.topic,
        source_format=datasource.format,
        time_source_ref=time_measurement_ref,
        min_transmit_interval=min_transmit_interval,
        filter_root_dir=request.app['settings'].FILTER_DIR,
        kafka_server=request.app['settings'].KAFKA_SERVER,
        filter_vars=filter_vars
    )
    request.app['filters'][instance_id] = filter_instance
    filter_instance.set_inputs(input_refs, measurement_refs, measurement_proportions)
    filter_instance.set_outputs(output_refs)


    filter_instance.start(kwargs)
    raise web.HTTPAccepted()
