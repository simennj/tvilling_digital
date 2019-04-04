#!/usr/bin/env python3
from typing import Dict

from aiohttp import web

import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from src import settings
from src import views
from src.connections import Simulation
from src.clients import views as client_views
from src.simulations import views as simulation_views
from src.datasources import views as datasource_views


@web.middleware
async def allow_cors(request: web.Request, handler):
    response: web.Response = await handler(request)
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


def init_app() -> web.Application:
    app = web.Application(middlewares=[allow_cors])
    aiohttp_session.setup(app, EncryptedCookieStorage(settings.SECRET_KEY))
    app.router.add_routes(views.routes)
    app.router.add_routes(simulation_views.routes)
    app.router.add_routes(datasource_views.routes)
    app.router.add_routes(client_views.routes)
    app['clients'] = {}
    app['datasources'] = {}
    app['simulations']: Dict[str, Simulation] = {}
    return app


if __name__ == '__main__':
    web.run_app(app=init_app(), host=settings.HOST, port=settings.PORT)
