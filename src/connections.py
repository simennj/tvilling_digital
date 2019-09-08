# TODO: No longer in use
import asyncio
import datetime
import json
import logging
import struct
from abc import ABC, abstractmethod
from array import array
from asyncio import AbstractEventLoop
from typing import Tuple, List

import aiokafka

from src import simulation

logger = logging.getLogger(__name__)


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
        self.task = loop.run_in_executor(executor=None, func=self._flush_measurements)
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
                        logger.exception('Error while flushing to topic %s', self.topic)
                await asyncio.sleep(
                    (next_flush_time - datetime.datetime.now()).total_seconds()
                )
                next_flush_time += self.frequency
            except TypeError:
                logger.exception('Error while flushing to topic %s', self.topic)
                next_flush_time = datetime.datetime.now() + self.frequency  # TODO: remove this ugly hack
            except struct.error:
                logger.exception('Error while flushing to topic %s', self.topic)
            except:
                logger.exception('Error while flushing to topic %s', self.topic)

    def flush(self):
        buffercontent = self.buffer
        self.buffer = b''
        return buffercontent

    def stop(self, timeout=5):
        self.running = False
        try:
            asyncio.wait_for(self.task, timeout=timeout)
        except TimeoutError as e:
            logger.exception('Error when stopping producer to topic %s', self.topic)


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



