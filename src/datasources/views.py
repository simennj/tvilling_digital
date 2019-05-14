import json
import os
import typing

from aiohttp import web

from src.datasources.models import generate_catman_outputs
from src.utils import RouteTableDefDocs, dumps, try_get, get_client, find_in_dir, try_get_validate

routes = RouteTableDefDocs()


@routes.get('/datasources/', name='datasource_list')
async def datasource_list(request: web.Request):
    """List all datasources.

    Listed datasources will contain true if currently running and false otherwise.
    Append an id to get more information about a listed datasource.
    Append /create to create a new datasource
    """

    running_sources = request.app['datasources'].get_sources().keys()
    sources = {
        s: s in running_sources
        for s in os.listdir(request.app['settings'].DATASOURCE_DIR)
    }
    return web.json_response(sources, dumps=dumps)


async def create_datasource(source_dir, source_id, addr, byte_format, output_names, time_index):
    path = os.path.join(source_dir, source_id)
    # if os.path.exists(path):
    #     raise web.HTTPUnprocessableEntity(reason=f'datasource with id {source_id} already exists')
    with open(path, 'w') as f:
        f.write(dumps({
            'source_id': source_id,
            'addr': addr,
            'byte_format': byte_format,
            'data_names': output_names,
            'time_index': time_index
        }))


@routes.post('/datasources/create', name='datasource_create')
async def datasource_create(request: web.Request):
    """Create a new datasource from post request.

    Post parameters:
    - id: the id to use for the source
    - address: the address to receive data from
    - port: the port to receive data from
    - output_name: the names of the outputs
      Must be all the outputs and in the same order as in the byte stream.
    - time_index: the index of the time value in the output_name list
    - byte_format: the python struct format string .
      Must be in the same order as name.
      Will not be used if catman is true.
    - catman: set to true to use catman byte format
      byte_format is not required if set
    - single: set to true if the data is single precision float
      Only used if catman is set to true
    returns redirect to created simulation page
    """

    post = await request.post()
    source_id = try_get_validate(post, 'id')
    addr: typing.Tuple[str, int] = (try_get(post, 'address'), int(try_get(post, 'port')))
    output_names = post.getall('output_name')
    if post.get('catman', ''):
        output_names, byte_format = generate_catman_outputs(
            output_names=output_names,
            single=bool(post.get('single', ''))
        )
    else:
        byte_format = try_get(post, 'byte_format')
    try:
        time_index = int(try_get(post, 'time_index'))
    except ValueError:
        raise web.HTTPBadRequest(reason='Invalid time_index')
    if byte_format[1:][time_index] is not 'd':
        raise web.HTTPBadRequest(reason=f'The time at time index must be a double (b) not {byte_format[time_index+1]}')
    await create_datasource(request.app['settings'].DATASOURCE_DIR, source_id, addr, byte_format, output_names, time_index)
    raise web.HTTPCreated()


@routes.get('/datasources/{id}', name='datasource_detail')
async def datasource_detail(request: web.Request):
    """Information about the datasource with the given id.
    To delete the datasource append /delete
    To subscribe to the datasource append /subscribe
    To start the datasource append /start
    To stop the datasource append /stop
    """

    source_id = request.match_info['id']
    if source_id not in os.listdir(request.app['settings'].DATASOURCE_DIR):
        return web.HTTPNotFound()
    with open(os.path.join(request.app['settings'].DATASOURCE_DIR, source_id)) as f:
        return web.json_response(text=f.read(), dumps=dumps)


def try_get_source(app, topic):
    try:
        source = app['datasources'].get_source(topic)
    except KeyError:
        raise web.HTTPNotFound()
    return source


@routes.get('/datasources/{id}/start', name='datasource_start')
async def datasource_start(request: web.Request):
    """Delete the datasource"""
    if id in request.app['datasources']:
        raise web.HTTPBadRequest(reason='Datasource must be stopped first')
    source_id = request.match_info['id']
    path = os.path.join(request.app['settings'].DATASOURCE_DIR, source_id)
    if not os.path.exists(path):
        raise web.HTTPBadRequest(reason=f'datasource with id {source_id} does not exists')
    with open(path, 'r') as f:
        kwargs = json.loads(f.read())
    kwargs['addr'] = tuple(kwargs['addr'])
    topic = f'{request.app["topic_counter"]:04}'
    request.app['topic_counter']+=1
    request.app['datasources'].set_source(topic=topic, **kwargs)
    return web.HTTPAccepted()


@routes.get('/datasources/{id}/delete', name='datasource_delete')
async def datasource_delete(request: web.Request):
    """Start the datasource"""
    if id in request.app['datasources']:
        raise web.HTTPBadRequest(reason='Datasource is already running')
    source_id = request.match_info['id']
    path = os.path.join(request.app['settings'].DATASOURCE_DIR, source_id)
    if not os.path.exists(path):
        raise web.HTTPBadRequest(reason=f'datasource with id {source_id} does not exists')
    os.remove(path)
    return web.HTTPAccepted()


@routes.get('/datasources/{id}/subscribe', name='datasource_subscribe')
async def datasource_subscribe(request: web.Request):
    """Subscribe to the datasource with the given id"""
    client = await get_client(request)
    datasource_id = request.match_info['id']
    topic = try_get_source(request.app, datasource_id).topic
    request.app['subscribers'][topic].add(client)
    raise web.HTTPOk()


@routes.post('/datasources/{id}/stop', name='datasource_stop')
async def datasource_stop(request: web.Request):
    """Stop the server from retrieving data from the datasource with the given id."""
    datasource_id = request.match_info['id']
    if datasource_id not in request.app['datasources']:
        raise web.HTTPUnprocessableEntity(text=f'Running datasource with id {datasource_id} could not be found')
    request.app['datasources'].remove_source(datasource_id)
    raise web.HTTPOk()
