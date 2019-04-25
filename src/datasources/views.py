from aiohttp import web
from aiohttp_session import get_session, Session

from src.connections import get_or_create_retriever, Datasource
from src.utils import RouteTableDefDocs

routes = RouteTableDefDocs()


@routes.get('/datasources/', name='datasource_list')
async def datasource_list(request: web.Request):
    """
    List all datasources.
    Append an id to get more information about a listed datasource.
    Append /create to create a new datasource
    """
    return web.json_response({
        str(addr): datasource.dict_repr() for addr, (_, datasource)
        in request.app['datasources'].items()
    })


@routes.post('/datasources/create', name='datasource_create')
async def datasource_start(request: web.Request):
    """
    Create a new datasource from post request.
    Post parameters:
    - address: the address to receive data on
    - port: the port to receive data on
    - name: the names of the outputs
      Must be all the outputs and in the same order as in the byte stream.
    - type: the types of the outputs.
      Must be in the same order as name.
    returns redirect to created simulation page
    """
    addr, datasource = await get_or_create_retriever(request)
    session: Session = await get_session(request)
    if 'id' not in session or session['id'] not in request.app['clients']:
        raise web.HTTPForbidden()
    client = request.app['client'][session['id']]
    # request.app['subscribers'][f'{addr[0]}_{addr[1]}'].add(client)
    return web.HTTPTemporaryRedirect(
        request.app.router['datasource'].url_for(id=addr)
    )


@routes.get('/datasources/{id}', name='datasource_detail')
async def datasource_detail(request: web.Request):
    """
    Information about the datasource with the given id.
    To subscribe to the simulation append /subscribe
    To stop the simulation append /stop
    """
    return web.json_response(request.app['datasources'][request.match_info['id']].dict_repr())


@routes.get('/datasources/{id}/subscribe', name='datasource_subscribe')
async def datasource_subscribe(request: web.Request):
    """Subscribe to the datasource with the given id"""
    session: Session = await get_session(request)
    if 'id' not in session or session['id'] not in request.app['clients']:
        raise web.HTTPForbidden()
    client = request.app['client'][session['id']]
    datasource_id = request.app['datasources'][request.match_info['id']]
    if datasource_id not in request.app['datasources']:
        return web.json_response({
            'status': 'failed',
            'message': f'There is no running datasource with id {datasource_id}'
        })
    request.app['subscribers'][datasource_id].add(client)
    return web.json_response(datasource_id)


@routes.post('/datasources/{id}/stop', name='datasource_stop')
async def datasource_stop(request: web.Request):
    """
    Stop the server from retrieving data from the datasource with the given id.
    """
    datasource_id = request.match_info['id']
    if datasource_id not in request.app['datasources']:
        return web.json_response({
            'status': 'failed',
            'message': f'There is no running datasource with id {datasource_id}'
        })
    datasource: Datasource = request.app['datasources'][datasource_id]
    datasource.stop()
