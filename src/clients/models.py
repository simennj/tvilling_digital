from collections import defaultdict
from typing import Set

from aiohttp import web, WSCloseCode


class Client:

    def __init__(self):
        self._websocket_connections: Set[web.WebSocketResponse] = set()
        self.buffers = defaultdict(bytearray)

    async def receive(self, topic, bytes):
        self.buffers[topic] += bytes
        if len(self.buffers[topic]) > 500:
            for ws in self._websocket_connections:
                await ws.send_bytes(topic.encode() + self.buffers[topic])
            self.buffers[topic] = bytearray()

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
