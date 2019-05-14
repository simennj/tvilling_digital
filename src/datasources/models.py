import asyncio
import logging
import struct
from dataclasses import dataclass, field
from typing import Tuple, List, Optional

import aiokafka

logger = logging.getLogger(__name__)


@dataclass
class UdpDatasource:
    """Class for describing an udp datasource"""
    addr: Tuple[str, int]
    byte_format: str
    data_names: List[str]
    time_index: int
    topic: str
    msg_bytes: int = field(init=False)
    time_bytes_start: int = field(init=False)

    def __post_init__(self):
        self.msg_bytes = struct.calcsize(self.byte_format)
        self.time_bytes_start = struct.calcsize(self.byte_format[1:][:self.time_index])


def generate_catman_outputs(output_names: List[str], single: bool = False) -> Tuple[List[str], str]:
    """

    :param single: true if the data from Catman is single precision (4 bytes each)
    :param output_names: a list of the names of the input data
    """
    byte_format = '<HHI'
    measurement_type = 's' if single else 'd'
    byte_format += (measurement_type * len(output_names))
    return ['id', 'channels', 'counter', *output_names], byte_format


class UdpReceiver(asyncio.DatagramProtocol):

    def __init__(self, loop: asyncio.AbstractEventLoop, kafka_addr):
        self.loop = loop
        self.producer = aiokafka.AIOKafkaProducer(
            loop=self.loop, bootstrap_servers=kafka_addr
        )
        self._addr_to_source = {}
        self._sources = {}

    def set_source(self,
                   source_id: str,
                   addr: Tuple[str, int],
                   topic: str,
                   byte_format: str,
                   data_names: List[str],
                   time_index: int
                   ) -> None:
        source = UdpDatasource(
            byte_format=byte_format,
            data_names=data_names,
            time_index=time_index,
            addr=addr,
            topic=topic,
        )
        self._addr_to_source[addr] = source
        self._sources[source_id] = source

    def remove_source(self, source_id) -> None:
        try:
            source: UdpDatasource = self._sources.pop(source_id)
            self._addr_to_source.pop(source.addr)
        except KeyError:
            logger.warning('%s could not be removed since it was not there', source_id)

    def __contains__(self, source_id):
        return source_id in self._sources

    def get_source(self, source_id):
        return self._sources[source_id]

    def get_sources(self):
        return self._sources.copy()

    def connection_made(self, transport: asyncio.transports.BaseTransport) -> None:
        self.loop.create_task(self.producer.start())

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.loop.create_task(self.producer.stop())

    def error_received(self, exc: Exception) -> None:
        logger.exception('error in datasource: %s', exc)

    def datagram_received(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        if addr in self._addr_to_source:
            source: UdpDatasource = self._addr_to_source[addr]
            time_bytes_start = source.time_bytes_start
            data = bytearray(raw_data)
            for i in range(0, len(data), source.msg_bytes):
                data[i:i+time_bytes_start+8] = data[i+time_bytes_start:i+time_bytes_start+8] + data[i:i+time_bytes_start]
            # for measurement in struct.iter_unpack(source.byte_format, raw_data):
            #     data += struct.pack(asdf, measurement[time_position], measurement
            self.loop.create_task(self.producer.send(topic=source.topic, value=data))
        else:
            logger.debug('%s attempted to send udp data but was not on the list of running datasources', addr)
