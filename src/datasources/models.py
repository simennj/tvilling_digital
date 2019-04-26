import asyncio

import aiokafka
import typing
import logging

logger = logging.getLogger(__name__)

class Datasource(asyncio.DatagramProtocol):

    def __init__(self, loop: asyncio.AbstractEventLoop, kafka_addr):
        self.loop = loop
        self.producer = aiokafka.AIOKafkaProducer(
            loop=self.loop, bootstrap_servers=kafka_addr
        )
        self.sources = {}

    def
        self.byte_format = '<'
        self.data_names = []
        for name, data_type in data_structure:
            self.data_names.append(name)
            self.byte_format += data_type
        assert (len(self.byte_format) == len(self.data_names) + 1)

    def connection_made(self, transport: asyncio.transports.BaseTransport) -> None:
        self.loop.create_task(self.producer.start())

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        self.loop.run_until_complete(self.producer.stop())

    def error_received(self, exc: Exception) -> None:
        logger.exception('error in datasource: %s', exc)

    def datagram_received(self, data: bytes, addr: typing.Tuple[str, int]) -> None:
        if addr in self.sources:
            self.loop.create_task(self.producer.send(topic=self.sources[addr], value=data))


def init(udp_addr, kafka_addr):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_init(loop, udp_addr, kafka_addr))
    finally:
        loop.close()


async def _init(loop, addr, kafka_addr):
    return await loop.create_datagram_endpoint(
        protocol_factory=lambda: Datasource(loop, kafka_addr),
        local_addr=addr
    )
