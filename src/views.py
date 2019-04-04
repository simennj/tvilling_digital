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


@routes.post('/subscribe')
async def subscribe(request: web.Request):
    addr, _ = await get_or_create_retriever(request)
    session: Session = await get_session(request)
    if 'id' not in session or session['id'] not in request.app['clients']:
        raise web.HTTPForbidden()
    client: Client = request.app['clients'][session['id']]
    if not client.running:
        client.start([f'{addr[0]}_{addr[1]}'])
    else:
        await client.add_subscription(f'{addr[0]}_{addr[1]}')
    return web.json_response({'host': addr[0], 'port': addr[1]})


@routes.post('/unsubscribe')
async def unsubscribe(request: web.Request):  # TODO: not tested
    post = await request.post()
    addr = (post['address'], int(post['port']))
    datasource: dict = request.app['datasource']
    if addr in datasource:
        retriever: Datasource = datasource[addr]
        session = await get_session(request)
        return web.Response(text=f'Unsubscribed to {addr}')
    else:
        return web.Response(text=f'{addr} not found')


@routes.post('/stop')
async def stop(request: web.Request):  # TODO: not tested
    post = await request.post()
    addr = (post['address'], int(post['port']))
    datasource: dict = request.app['datasource']
    if addr in datasource:
        del datasource[addr]
        return web.Response(text=f'Stopped {addr}')
    else:
        return web.Response(text=f'{addr} not found')


@routes.post('/simulate')
async def simulate(request: web.Request):
    _, retriever = await get_or_create_retriever(request)
    session_id = (await get_session(request))['id']
    simulation: Simulation = Simulation(asyncio.get_event_loop(), 'testrig.fmu', retriever.byte_format)
    request.app['simulations'][session_id] = simulation
    client = request.app['clients'][session_id]
    retriever.subscribers[session_id] = simulation
    simulation.output_refs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    simulation.set_inputs(time_ref=14, bindings=[(0, 7)])
    return web.json_response(request.app['simulations'].__repr__())
