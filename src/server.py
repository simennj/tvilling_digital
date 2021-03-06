import asyncio
import logging
from collections import defaultdict
from typing import Dict

import aiohttp_cors
import aiohttp_session
from aiohttp import web
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from src import views
from src.blueprints import views as blueprints_views
from src.clients import views as client_views
from src.clients.models import Client
from src.datasources import views as datasource_views
from src.datasources.models import UdpReceiver
from src.fmus import views as fmu_views
from src.kafka import consume_from_kafka
from src.processors import views as processor_views
from src.processors.models import Processor

logger = logging.getLogger(__name__)


async def start_background_tasks(app):
    """A method to be called on startup, initiates the Kafka and UDP connections"""
    loop = asyncio.get_event_loop()
    app['kafka'] = loop.create_task(consume_from_kafka(app))
    app['udp_transport'], app['datasources'] = await loop.create_datagram_endpoint(
        protocol_factory=lambda: UdpReceiver(app['settings'].KAFKA_SERVER),
        local_addr=app['settings'].UDP_ADDR
    )


async def cleanup_background_tasks(app):
    """A method to be called on shutdown, closes the WebSocket, Kafka, and UDP connections"""
    for client in app['clients'].values():
        await client.close()
    for simulation in app['simulations'].values():
        await simulation.close()
    app['udp_transport'].close()
    app['kafka'].cancel()
    await app['kafka']


def init_app(settings) -> web.Application:
    """Initializes and starts the server"""
    app = web.Application()
    app['settings'] = settings
    aiohttp_session.setup(app, EncryptedCookieStorage(settings.SECRET_KEY))
    app.router.add_routes(views.routes)
    app.router.add_routes(datasource_views.routes)
    app.router.add_routes(client_views.routes)
    app.router.add_routes(fmu_views.routes)
    app.router.add_routes(processor_views.routes)
    app.router.add_routes(blueprints_views.routes)

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

    # TODO: these should be switched out with something that is not instance exclusive to enable horizontal scaling
    # Redis could for example be a viable alternative
    app['clients']: Dict[str, Client] = {}
    app['processors']: Dict[str, Processor] = {}
    app['subscribers'] = defaultdict(set)
    app['topics']: Dict[str, Dict] = {}
    app['topic_counter'] = 0

    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app
