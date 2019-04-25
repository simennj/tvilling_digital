import asyncio
import datetime
import json
import struct
import traceback
from abc import ABC, abstractmethod
from array import array
from asyncio import AbstractEventLoop, transports
from typing import Tuple, List, Optional, Set

import aiokafka
from aiohttp import web, WSCloseCode

from src import simulation


class Consumer(ABC):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    @abstractmethod
    async def _receive(self, messages: List[aiokafka.ConsumerRecord]):
        pass


def run(producer, topic, frequency_ms=1000 / 60):
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop=loop)
        return loop.run_until_complete(producer(loop, topic, frequency_ms))
    finally:
        loop.close()


class Producer:

    def __init__(self, loop: AbstractEventLoop, topic, bootstrap_servers, frequency_ms=1000 / 60):
        self.loop = loop
        self.producer = aiokafka.AIOKafkaProducer(
            loop=self.loop, bootstrap_servers=bootstrap_servers
        )
        self.topic = topic
        self.running = True
        # executor = ProcessPoolExecutor()
        self.task = loop.run_in_executor(executor=None, func=self.run)
        self.frequency = datetime.timedelta(milliseconds=frequency_ms)
        self.buffer = b''

    async def _flush_measurements(self):
        next_flush_time = datetime.datetime.now() + self.frequency
        while self.running:
            try:
                data = self.flush()
                if len(data) > 0:
                    try:
                        await self.producer.send(topic=self.topic, value=data)
                    except:
                        print(traceback.format_exc())
                await asyncio.sleep(
                    (next_flush_time - datetime.datetime.now()).total_seconds()
                )
                next_flush_time += self.frequency
            except TypeError:
                print(traceback.format_exc())
                next_flush_time = datetime.datetime.now() + self.frequency  # TODO: remove this ugly hack
            except struct.error:
                print(traceback.format_exc())  # TODO: replace when logging is set up
            except:
                print(traceback.format_exc())  # TODO: replace when logging is set up

    def flush(self):
        buffercontent = self.buffer
        self.buffer = b''
        return buffercontent

    def stop(self, timeout=5):
        self.running = False
        try:
            asyncio.wait_for(self.task, timeout=timeout)
        except TimeoutError as e:
            print(e)  # TODO: Logging


class Datasource(asyncio.DatagramProtocol, Producer):

    def __init__(self, loop: AbstractEventLoop, data_structure, topic, bootstrap_servers, frequency_ms=1000 / 60):
        super().__init__(loop=loop, topic=topic, bootstrap_servers=bootstrap_servers, frequency_ms=frequency_ms)
        self.byte_format = '<'
        self.data_names = []
        for name, data_type in data_structure:
            self.data_names.append(name)
            self.byte_format += data_type
        assert (len(self.byte_format) == len(self.data_names) + 1)

    def connection_made(self, transport: transports.BaseTransport) -> None:
        self.loop.create_task(self.producer.start())

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self.loop.run_until_complete(self.producer.stop())

    def error_received(self, exc: Exception) -> None:
        print('error in datasource: %s', exc)

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        self.buffer += data

    def dict_repr(self):
        return {
            'frequency': self.frequency.total_seconds(),
            'byte_format': self.byte_format,
            'data_names': self.data_names,
        }


class Simulation(Consumer, Producer):

    def __init__(self, loop: AbstractEventLoop, path: str, byte_format: str, frequency_ms=1000 / 10):
        self.byte_format = byte_format
        self.twin = simulation.Twin(path)
        self.twin.start()
        self.output_refs: Tuple[int] = ()
        self._input_refs: Tuple[int] = ()
        self._measurement_refs: Tuple[int] = ()
        # self._measurement_time_ref: int = None
        self.current_input_values: List[float] = []
        # self.current_input_timestamp: float = None
        # self.last_input_timestamp: float = None
        super().__init__(loop, frequency_ms)

    def set_inputs(self, input_refs: List[int], measurement_refs: List[int]):
        # self._measurement_time_ref = time_ref
        self._input_refs = input_refs
        self._measurement_refs = measurement_refs
        self.current_input_values = [None] * len(input_refs)

    def flush(self):
        # if self.last_input_timestamp is None:
        #     if self.current_input_timestamp is None:
        #         return b'' #TODO: log?
        #     self.last_input_timestamp = self.current_input_timestamp
        # self.twin.fmu.doStep(self.last_input_timestamp, self.current_input_timestamp-self.last_input_timestamp)
        self.twin.fmu.doStep(0, 0)
        # self.last_input_timestamp = self.current_input_timestamp
        data_list = self.twin.fmu.getReal(self.output_refs)
        data_bytes = array('d', data_list).tostring()
        return data_bytes

    async def _receive(self, data):
        unpacked_data = list(struct.iter_unpack(self.byte_format, data))
        # self.current_input_timestamp = unpacked_data[0][self._measurement_time_ref] * 1000  # TODO: not hardcode scaling
        for input_index, measurement_ref in enumerate(self._measurement_refs):
            self.current_input_values[input_index] = 0.001 * unpacked_data[0][measurement_ref]
        self.twin.fmu.setReal(self._input_refs, self.current_input_values)

    def __repr__(self):
        return json.dumps(self.dict_repr())

    def dict_repr(self):
        return {
            'frequency': self.frequency.total_seconds(),
            'byte_format': self.byte_format,
            'outputs': self.output_refs,
            'inputs': self._input_refs,
            'datasources': self._measurement_refs,
            'twin': self.twin.dict_repr()
        }

    def stop(self, timeout=5):
        super().stop(timeout)
        self.twin.stop()


class Client(Consumer):

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self._websocket_connections: Set[web.WebSocketResponse] = set()
        super().__init__(loop)

    async def _receive(self, messages: List[aiokafka.ConsumerRecord]):
        for ws in self._websocket_connections:
            await ws.send_bytes(b''.join(message.value for message in messages))

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


async def setup_measurement_retriever(loop: AbstractEventLoop, addr, data_structure, bootstrap_servers):
    return await loop.create_datagram_endpoint(
        protocol_factory=lambda: Datasource(
            loop=loop,
            data_structure=data_structure,
            topic=f'{addr[0]}_{addr[1]}',
            bootstrap_servers=bootstrap_servers
        ),
        local_addr=addr
    )


async def get_or_create_retriever(request: web.Request):
    post = await request.post()
    addr = (
        post['address'], int(post['port'])
    )  # TODO: use same address for all retrievers, possibly with different ports?
    names = post.getall('name', [])
    types = post.getall('type', [])
    if addr not in request.app['datasources']:
        request.app['datasources'][addr] = await setup_measurement_retriever(
            loop=asyncio.get_event_loop(),
            addr=addr,
            data_structure=((names[i], types[i]) for i in range(len(names))),
            bootstrap_servers=request.app['settings'].KAFKA_SERVER
        )
    datasource: Datasource = request.app['datasources'][addr][1]
    return addr, datasource
