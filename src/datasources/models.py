import asyncio
import logging
from dataclasses import dataclass
from typing import Tuple, List, Optional

import aiokafka

logger = logging.getLogger(__name__)


@dataclass
class UdpDatasource:
    """Class for describing an udp datasource"""
    addr: Tuple[str, int]
    byte_format: str
    data_names: List[str]
    topic: str


def generate_catman_byte_formats(data_names: List[str], single: bool = False) -> str:
    """

    :param single: true if the data from Catman is single precision (4 bytes each)
    :param data_names: a list of the names of the input data
    """
    byte_format = '<HHI'
    measurement_type = 's' if single else 'd'
    byte_format + (measurement_type * len(data_names))
    return byte_format


class UdpReceiver(asyncio.DatagramProtocol):

    def __init__(self, loop: asyncio.AbstractEventLoop, kafka_addr):
        self.loop = loop
        self.producer = aiokafka.AIOKafkaProducer(
            loop=self.loop, bootstrap_servers=kafka_addr
        )
        self._addr_to_topic = {}
        self._sources = {}

    def set_source(self,
                   source_id: str,
                   addr: Tuple[str, int],
                   topic: str,
                   byte_format: str,
                   data_names: List[str]) -> None:
        self._addr_to_topic[addr] = topic
        self._sources[source_id] = UdpDatasource(
            byte_format=byte_format,
            data_names=data_names,
            addr=addr,
            topic=topic
        )

    def remove_source(self, source_id) -> None:
        try:
            source: UdpDatasource = self._sources.pop(source_id)
            self._addr_to_topic.pop(source.addr)
        except KeyError:
            logger.warning('%s could not be removed since it was not there', source_id)

    def __contains__(self, source_id):
        return source_id in self._sources

    def get_source(self, source_id):
        return self._sources.get(source_id)

    def get_sources(self):
        return self._sources.copy()

    def connection_made(self, transport: asyncio.transports.BaseTransport) -> None:
        self.loop.create_task(self.producer.start())

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.loop.run_until_complete(self.producer.stop())

    def error_received(self, exc: Exception) -> None:
        logger.exception('error in datasource: %s', exc)

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        if addr in self._addr_to_topic:
            self.loop.create_task(self.producer.send(topic=self._addr_to_topic[addr], value=data))
        else:
            logger.debug('%s attempted to send udp data but was not on the list of running datasources', addr)
