import asyncio
import logging
from collections import defaultdict
from typing import Dict

import aiohttp_cors
import aiohttp_session
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from src import views
from src.clients import views as client_views
from src.connections import Client, Datasource, Simulation
from src.datasources import views as datasource_views
from src.fmus import views as fmu_views
from src.kafka import consume_from_kafka
from src.simulations import views as simulation_views

logger = logging.getLogger(__name__)


async def start_background_tasks(app):
    app['kafka'] = asyncio.get_event_loop().create_task(consume_from_kafka(app))


async def cleanup_background_tasks(app):
    for client in app['clients'].values():
        await client.close()
    for datasource in app['datasources'].values():
        await datasource.close()
    for simulation in app['simulations'].values():
        await simulation.close()
    app['kafka'].cancel()
    await app['kafka']


@web.middleware
async def error_middleware(request, handler):
    try:
        response = await handler(request)
        if response.status != 404:
            return response
        message = response.message
    except web.HTTPException as ex:
        if ex.status != 404:
            raise
        message = ex.reason
    return web.json_response({'error': message})


def init_app(settings) -> web.Application:
    app = web.Application(middlewares=[error_middleware])
    app['settings'] = settings
    aiohttp_session.setup(app, EncryptedCookieStorage(settings.SECRET_KEY))
    app.router.add_routes(views.routes)
    app.router.add_routes(simulation_views.routes)
    app.router.add_routes(datasource_views.routes)
    app.router.add_routes(client_views.routes)
    app.router.add_routes(fmu_views.routes)

    cors = aiohttp_cors.setup(app, defaults={
        '*': aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers='*',
            allow_headers='*',
            allow_methods='*'
        )
    })

    for route in list(app.router.routes()):
        cors.add(route)

    app['clients']: Dict[str, Client] = {}
    app['datasources']: Dict[str, Datasource] = {}
    app['simulations']: Dict[str, Simulation] = {}
    app['subscribers'] = defaultdict(set)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app
