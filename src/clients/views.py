from aiohttp import web
from aiohttp_session import get_session, Session

from src.connections import get_or_create_retriever, Client

routes = web.RouteTableDef()


@routes.get('/client/', name='client')
async def client(request: web.Request):
    session: Session = await get_session(request)
    return web.json_response(request.app['clients'][session['id']].dict_repr())


@routes.get('/client/start', name='client_start')
async def client_start(request: web.Request):
    session: Session = await get_session(request)
    client: Client = request.app['clients'][session['id']]
    client.start()
    return web.HTTPTemporaryRedirect('client')
