import typing

from aiohttp import web
from aiohttp_session import get_session, Session

from src.datasources.models import generate_catman_byte_formats
from src.utils import RouteTableDefDocs, dumps, try_get

routes = RouteTableDefDocs()


@routes.get('/datasources/', name='datasource_list')
async def datasource_list(request: web.Request):
    """List all datasources.

    Append an id to get more information about a listed datasource.
    Append /create to create a new datasource
    """

    return web.json_response(request.app['datasources'].get_sources(), dumps=dumps)


@routes.post('/datasources/create', name='datasource_create')
async def datasource_start(request: web.Request):
    """Create a new datasource from post request.

    Post parameters:
    - id: the id to use for the source
    - address: the address to receive data from
    - port: the port to receive data from
    - output_name: the names of the outputs
      Must be all the outputs and in the same order as in the byte stream.
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
    source_id = try_get(post, 'id')
    if not source_id:
        raise web.HTTPUnprocessableEntity(reason='Invalid id')
    addr: typing.Tuple[str, int] = (try_get(post, 'address'), int(try_get(post, 'port')))
    topic = f'UDP_{addr[0]}_{addr[1]}'
    output_names = post.getall('output_name')
    if post.get('catman', ''):
        byte_format = generate_catman_byte_formats(
            output_names=output_names,
            single=bool(post.get('single', ''))
        )
    else:
        byte_format = try_get(post, 'byte_format')
    request.app['datasources'].set_source(
        source_id=source_id,
        addr=addr,
        topic=topic,
        byte_format=byte_format,
        data_names=output_names
    )
    raise web.HTTPCreated()


@routes.get('/datasources/{id}', name='datasource_detail')
async def datasource_detail(request: web.Request):
    """Information about the datasource with the given id.
    To subscribe to the simulation append /subscribe
    To stop the simulation append /stop
    """

    source = await get_source(request.app, request.match_info['id'])
    return web.json_response(source, dumps=dumps)


async def get_source(app, topic):
    try:
        source = app['datasources'].get_source(topic)
    except KeyError:
        raise web.HTTPNotFound()
    return source


@routes.get('/datasources/{id}/subscribe', name='datasource_subscribe')
async def datasource_subscribe(request: web.Request):
    """Subscribe to the datasource with the given id"""
    session: Session = await get_session(request)
    if 'id' not in session or session['id'] not in request.app['clients']:
        raise web.HTTPForbidden()
    client = request.app['clients'][session['id']]
    datasource_id = request.match_info['id']
    if datasource_id in request.app['datasources']:
        topic = request.app['datasources'].get_source(datasource_id).topic
        request.app['subscribers'][topic].add(client)
        raise web.HTTPOk()
    raise web.HTTPNotFound()


@routes.post('/datasources/{id}/stop', name='datasource_stop')
async def datasource_stop(request: web.Request):
    """Stop the server from retrieving data from the datasource with the given id."""
    datasource_id = request.match_info['id']
    if datasource_id not in request.app['datasources']:
        raise web.HTTPUnprocessableEntity(text=f'Running datasource with id {datasource_id} could not be found')
    request.app['datasources'].remove_source(datasource_id)
    raise web.HTTPOk()
