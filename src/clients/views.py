from aiohttp import web
from aiohttp_session import get_session, Session

from src.clients.models import Client
from src.utils import RouteTableDefDocs

routes = RouteTableDefDocs()


@routes.get('/client/', name='client')
async def client(request: web.Request):
    """clients"""
    session: Session = await get_session(request)
    return web.json_response(request.app['clients'][session['id']].dict_repr())


@routes.get('/client/start', name='client_start')
async def client_start(request: web.Request):
    """start a client?"""
    session: Session = await get_session(request)
    client: Client = request.app['clients'][session['id']]
    client.start()
    return web.HTTPTemporaryRedirect('client')
