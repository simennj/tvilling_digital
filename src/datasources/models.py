import asyncio
import logging
import struct
from dataclasses import dataclass, field
from typing import Tuple, List, Optional

from kafka import KafkaProducer

logger = logging.getLogger(__name__)


@dataclass
class UdpDatasource:
    """Class for describing an udp datasource"""
    addr: Tuple[str, int]
    input_byte_format: str
    input_names: List[str]
    output_refs: List[int]
    time_index: int
    topic: str = None
    output_names: List[str] = field(init=False)
    byte_format: str = field(init=False)
    output_byte_count: int = field(init=False)
    input_byte_count: int = field(init=False)
    time_bytes_start: int = field(init=False)

    def __post_init__(self):
        self.time_index = self.time_index % len(self.input_byte_format[1:])
        self.input_byte_count = struct.calcsize(self.input_byte_format)
        byte_types = self.input_byte_format[1:]
        self.time_bytes_start = struct.calcsize(byte_types[:self.time_index])
        self.byte_format = self.input_byte_format[0] + byte_types[self.time_index]
        for ref in self.output_refs:
            self.byte_format += byte_types[ref]
        self.output_byte_count = struct.calcsize(self.byte_format)
        self.output_names = [self.input_names[ref] for ref in self.output_refs]


def generate_catman_outputs(output_names: List[str], output_refs, single: bool = False) -> Tuple[
    List[str], List[int], str]:
    """

    :param single: true if the data from Catman is single precision (4 bytes each)
    :param output_names: a list of the names of the input data
    """
    byte_format = '<HHI'
    measurement_type = 's' if single else 'd'
    byte_format += (measurement_type * len(output_names))
    output_refs = [ref + 3 for ref in output_refs]
    return ['id', 'channels', 'counter', *output_names], output_refs, byte_format


class UdpReceiver(asyncio.DatagramProtocol):

    def __init__(self, kafka_addr):
        self.producer = KafkaProducer(bootstrap_servers=kafka_addr)
        self._addr_to_source = {}
        self._sources = {}
        self.buffer = bytearray()

    def set_source(self,
                   source_id: str,
                   addr: Tuple[str, int],
                   topic: str,
                   input_byte_format: str,
                   input_names: List[str],
                   output_refs: List[int],
                   time_index: int
                   ) -> None:
        source = UdpDatasource(
            input_byte_format=input_byte_format,
            input_names=input_names,
            output_refs=output_refs,
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
        pass

    def connection_lost(self, exc: Optional[Exception]) -> None:
        pass

    def error_received(self, exc: Exception) -> None:
        logger.exception('error in datasource: %s', exc)

    def datagram_received(self, raw_data: bytes, addr: Tuple[str, int]) -> None:
        if addr in self._addr_to_source:
            source: UdpDatasource = self._addr_to_source[addr]
            data = bytearray(source.output_byte_count * (len(raw_data) // source.input_byte_count))
            for i, msg in enumerate(struct.iter_unpack(source.input_byte_format, raw_data)):
                data[i:i + source.output_byte_count] = struct.pack(source.byte_format, msg[source.time_index],
                                                                   *[msg[ref] for ref in source.output_refs])
            # time_bytes_start = source.time_bytes_start
            # data = bytearray(raw_data)
            # for i in range(0, len(data), source.msg_bytes):
            #     data[i:i + time_bytes_start + 8] = data[i + time_bytes_start:i + time_bytes_start + 8] + data[i:i + time_bytes_start]
            self.buffer += data
            if len(self.buffer) > len(source.output_names) * 100:
                self.producer.send(topic=source.topic, value=self.buffer)
                self.buffer = bytearray()
        else:
            logger.debug('%s attempted to send udp data but was not on the list of running datasources', addr)
