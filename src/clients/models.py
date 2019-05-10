from typing import Set, List

import aiokafka
from aiohttp import web, WSCloseCode


class Client:

    def __init__(self):
        self._websocket_connections: Set[web.WebSocketResponse] = set()

    async def receive(self, bytes):
        for ws in self._websocket_connections:
            await ws.send_bytes(bytes)

    async def add_websocket_connection(self, ws: web.WebSocketResponse):
        self._websocket_connections.add(ws)

    async def remove_websocket_connection(self, ws: web.WebSocketResponse):
        self._websocket_connections.remove(ws)

    async def close(self):
        for ws in self._websocket_connections:
            await ws.close(code=WSCloseCode.GOING_AWAY, message=b'Shutdown')

    def dict_repr(self):
        return {
            'connections': len(self._websocket_connections)
        }
