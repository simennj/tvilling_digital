from aiohttp import web
from aiohttp_session import get_session, Session

from src.utils import RouteTableDefDocs, dumps

routes = RouteTableDefDocs()


@routes.get('/client', name='client')
async def client(request: web.Request):
    """Show info about the client sending the request"""
    session: Session = await get_session(request)
    if 'id' not in session or session['id'] not in request.app['clients']:
        raise web.HTTPUnauthorized()
    return web.json_response(request.app['clients'][session['id']], dumps=dumps)

