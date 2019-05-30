import asyncio
import logging
import os

import aiokafka
from aiohttp import web, WSMessage
from aiohttp_session import get_session

from src.clients.models import Client
from src.utils import RouteTableDefDocs, try_get, get_client

routes = RouteTableDefDocs()

logger = logging.getLogger(__name__)


@routes.get('/session')
async def session_endpoint(request: web.Request):
    """Only returns a session cookie

    Generates and returns a session cookie.
    """
    session = await get_session(request)
    session['id'] = request.remote  # TODO: better id
    return web.HTTPOk()


@routes.get('/')
async def index(request: web.Request):
    """The API index

    A standard HTTP request will return a sample page with a simple example of api use.
    A WebSocket request will initiate a websocket connection making it possible to retrieve measurement and simulation data.

    Available endpoints are
    - /datasources/ for measurement data sources
    - /processors/ for running processors on the data
    - /blueprints/ for the blueprints used to create processors
    - /fmus/ for available FMUs (for the fmu blueprint)
    - /fmus/ for available models (for the fedem blueprint)
    - /topics/ for all available data sources (datasources and processors)
    """

    session = await get_session(request)
    ws = web.WebSocketResponse()  # TODO: fix heartbeat clientside?
    session['id'] = client_id = request.remote  # TODO: better id
    if ws.can_prepare(request):
        await ws.prepare(request)
        if client_id not in request.app['clients']:
            logger.info('New connection from %s', request.remote)
            request.app['clients'][client_id] = Client()
        else:
            logger.info('Reconnection from %s', request.remote)
        client = request.app['clients'][client_id]
        await client.add_websocket_connection(ws)
        try:
            async for message in ws:  # type: WSMessage
                try:
                    if message.data == '__ping__':
                        await ws.send_bytes(b'')
                    # else:
                    #     print(message.json())
                except AttributeError as e:
                    logger.exception('Error receiving message from %s', client_id)
            return ws
        finally:
            logger.info('Closing %s', request.remote)
            await client.remove_websocket_connection(ws)
            await ws.close()
    else:
        with open('html/index.html', 'r') as file:
            body = file.read()
        return web.Response(body=body, content_type='text/html')


@routes.get('/topics/', name='topics')
async def topics(request: web.Request):
    """Lists the available data sources for plotting or processors

    Append the id of a topic to get details about only that topic
    Append the id of a topic and /subscribe to subscribe to a topic
    Append the id of a topic and /unsubscribe to unsubscribe to a topic
    """
    return web.json_response(request.app['topics'])


@routes.get('/topics/{id}', name='topics_detail')
async def topics_detail(request: web.Request):
    """Show a single topic

    Append /subscribe to subscribe to the topic
    Append /unsubscribe to unsubscribe to the topic
    """
    topic = request.match_info['id']
    if topic not in request.app['topics']:
        raise web.HTTPNotFound()
    return web.json_response(request.app['topics'][topic])


@routes.get('/topics/{id}/subscribe', name='subscribe')
async def subscribe(request: web.Request):
    """Subscribe to the given topic"""
    topic = request.match_info['id']
    client = await get_client(request)
    if topic not in request.app['topics']:
        raise web.HTTPNotFound()
    request.app['subscribers'][topic].add(client)
    raise web.HTTPAccepted()
