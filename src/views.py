import asyncio
import traceback

from aiohttp import web, WSMessage
from aiohttp_session import get_session, Session

from src.connections import Client, Datasource, Simulation, \
    get_or_create_retriever

routes = web.RouteTableDef()


@routes.get('/')
async def test(request: web.Request):
    session = await get_session(request)
    ws = web.WebSocketResponse()  # TODO: fix heartbeat clientside?
    session['id'] = client_id = request.remote  # TODO: better id
    if ws.can_prepare(request):
        await ws.prepare(request)
        if client_id not in request.app['clients']:
            print(f'New connection from {request.remote}')
            request.app['clients'][client_id] = Client(asyncio.get_event_loop())
        else:
            print(f'Reconnection from {request.remote}')
        client = request.app['clients'][client_id]
        await client.add_websocket_connection(ws)
        try:
            async for message in ws:  # type: WSMessage
                try:
                    if message.data == '__ping__':
                        await ws.send_bytes(b'')
                    else:
                        print(message.json())
                except AttributeError as e:
                    traceback.print_exc()
                    print(e)
            return ws
        finally:
            print(f'Closing {request.remote}')
            await client.remove_websocket_connection(ws)
            await ws.close()
    else:
        with open('html/wsprint.html', 'r') as file:
            body = file.read()
        return web.Response(body=body, content_type='text/html')
