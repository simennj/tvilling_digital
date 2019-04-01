#!/usr/bin/env python3
import asyncio
import logging

from aiohttp import web

import aiohttp_session
from aiohttp.web_runner import GracefulExit
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from watchdog.events import FileSystemEventHandler

import src.settings, src.views

import importlib

from watchdog.observers import Observer

log = logging.getLogger(__name__)

HOST = src.settings.HOST
PORT = src.settings.PORT


def init_app() -> web.Application:
    app = web.Application()
    aiohttp_session.setup(app, EncryptedCookieStorage(src.settings.SECRET_KEY))
    app.router.add_routes(src.views.routes)
    app['ws'] = []
    return app


class ReloadHandler(FileSystemEventHandler):
    def __init__(self, loop):
        self.runner = None
        self.loop = loop
        self.reloading = asyncio.Lock()

    async def start_server(self):
        async with self.reloading:
            importlib.reload(src)
            if self.runner is not None:
                await self.runner.cleanup()
                await self.runner.shutdown()
                self.runner = None
                print('reloading')
            else:
                print("starting for the first time")
            self.runner = web.AppRunner(init_app())
            await self.runner.setup()
            site = web.TCPSite(runner=self.runner, host=HOST, port=PORT)
            await site.start()

    def on_any_event(self, event):
        loop.create_task(self.start_server())


async def start_with_reload(observer, handler):
    await handler.start_server()
    observer.schedule(handler, 'src', )
    observer.start()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    observer = Observer()
    handler = ReloadHandler(loop)
    loop.create_task(start_with_reload(observer, handler))
    try:
        loop.run_forever()
    except(GracefulExit, KeyboardInterrupt):
        pass
    finally:
        loop.close()
