from collections import defaultdict
from typing import Set

from aiohttp import web, WSCloseCode


class Client:
    """Handles connections to a clients websocket connections"""

    def __init__(self):
        """Initializes the client with no websocket connections and an empty buffer"""
        self._websocket_connections: Set[web.WebSocketResponse] = set()
        self.buffers = defaultdict(bytearray)

    async def receive(self, topic, bytes):
        """
        Asynchronously transmit data to the clients websocket connections

        Will add the data to the buffer and send it when the buffer becomes large enough

        :param topic: the topic the data received from
        :param bytes: the data received as bytes
        """
        self.buffers[topic] += bytes
        if len(self.buffers[topic]) > 500:
            for ws in self._websocket_connections:
                try:
                    await ws.send_bytes(topic.encode() + self.buffers[topic])
                except ConnectionResetError:
                    break
            else:
                self.buffers[topic] = bytearray()
                return
            self.buffers[topic] = bytearray()
            await self.remove_websocket_connection(ws)

    async def add_websocket_connection(self, ws: web.WebSocketResponse):
        self._websocket_connections.add(ws)

    async def remove_websocket_connection(self, ws: web.WebSocketResponse):
        self._websocket_connections.remove(ws)

    async def close(self):
        """Will close all the clients websocket connections"""
        for ws in self._websocket_connections:
            await ws.close(code=WSCloseCode.GOING_AWAY, message=b'Shutdown')

    def dict_repr(self) -> dict:
        """Returns a the number of connections the client has"""
        return {
            'connections': len(self._websocket_connections)
        }
