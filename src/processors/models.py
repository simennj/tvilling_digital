import asyncio
import logging
import multiprocessing
import os
import shutil
import struct
from dataclasses import dataclass
from importlib.machinery import SourceFileLoader
from multiprocessing.connection import Connection

import kafka
import math
from kafka import TopicPartition

logger = logging.getLogger(__name__)


def processor_process(
        connection: Connection,
        blueprint_path: str,
        init_params: dict,
        processor_dir: str,
        topic: str,
        source_topic: str,
        source_format: str,
        kafka_server: str,
        min_input_spacing: float,
        min_step_spacing: float,
        min_output_spacing: float,
):
    """
    Runs the given blueprint as a processor

    Is meant to be run in a separate process

    :param connection: a connection object to communicate with the main process
    :param blueprint_path: the path to the blueprint folder
    :param init_params: the initialization parameters to the processor as a dictionary
    :param processor_dir: the directory the created process will run in
    :param topic: the topic the process will send results to
    :param source_topic: the topic the process will receive data from
    :param source_format: the byte format of the data the process will receive
    :param kafka_server: the address of the kafka bootstrap server the process will use
    :param min_input_spacing: the minimum time between each input to the processor
    :param min_step_spacing: the minimum time between each step function call on the processor
    :param min_output_spacing: the minimum time between each results retrieval from the processor
    :return:
    """
    blueprint_path = os.path.realpath(blueprint_path)

    # Creates and sets, deleting if it already exists, the directory the process will use
    try:
        if os.path.exists(processor_dir):
            shutil.rmtree(processor_dir)
        os.makedirs(processor_dir)
        os.chdir(processor_dir)
    except PermissionError as e:
        connection.send({'type': 'error', 'value': e})
        return

    start_time = -1
    next_input_time = 0
    next_step_time = 0
    next_output_time = 0

    # Imports the blueprints and initializes the processor from it
    try:
        processor_instance = SourceFileLoader(
            os.path.basename(blueprint_path), os.path.join(blueprint_path, '__init__.py')
        ).load_module().P(
            **init_params
        )
    except TypeError as e:
        connection.send({'type': 'error', 'value': e})
        return
    except ValueError as e:
        connection.send({'type': 'error', 'value': e})
        return

    # Retrieves the inputs and outputs from the initialized processor
    if hasattr(processor_instance, 'outputs'):
        # Uses the outputs attribute from the processor if it exists
        outputs = [Variable(v.valueReference, v.name) for v in processor_instance.outputs]
    else:
        # Otherwise it has to create outputs from output_names
        outputs = [Variable(i, name) for i, name in enumerate(processor_instance.output_names)]
    if hasattr(processor_instance, 'inputs'):
        # Uses the inputs attribute from the processor if it exists
        inputs = [Variable(v.valueReference, v.name) for v in processor_instance.inputs]
    else:
        # Otherwise it has to create inputs from input_names
        inputs = [Variable(i, name) for i, name in enumerate(processor_instance.input_names)]

    # Add a helper attribute that lists outputs that are part of a matrix
    matrix_outputs = (
        processor_instance.matrix_outputs
        if hasattr(processor_instance, 'matrix_outputs')
        else []
    )

    initialized = True
    started = False
    byte_format = '<d'
    output_refs = []
    input_refs = []
    measurement_refs = []
    measurement_proportions = []

    topic_partition = TopicPartition(topic=source_topic, partition=0)
    output_buffer = bytearray()

    # Waits for the start signal from the main process
    start_params = None
    while start_params is None:
        msg = connection.recv()
        if msg['type'] == 'start':
            value = msg['value']
            start_params = value['start_params']
            output_refs = value['output_refs']
            input_refs = value['input_refs']
            measurement_refs = value['measurement_refs']
            measurement_proportions = value['measurement_proportions']
            byte_format = '<' + 'd' * (len(output_refs) + 1)
        elif msg['type'] == 'status':
            connection.send({'type': 'status', 'value': {
                'outputs': outputs,
                'inputs': inputs,
                # Add a helper attribute that lists outputs that are part of a matrix
                'matrix_outputs': matrix_outputs,
                'initialized': initialized,
                'started': started,
            }})
        elif msg['type'] == 'stop':
            try:
                processor_instance.stop()
            finally:
                return

    try:
        # Calls the processors start function if present
        if hasattr(processor_instance, 'start'):
            processor_instance.start(
                start_time=next_output_time,
                **start_params
            )
    except TypeError as e:
        connection.send({'type': 'error', 'value': e})
        return
    except ValueError as e:
        connection.send({'type': 'error', 'value': e})
        return

    # Use a custom time for results if the processor defines it
    if hasattr(processor_instance, "get_time"):
        processor_custom_time = True
    else:
        processor_custom_time = False

    try:
        # Initializes kafka
        consumer = kafka.KafkaConsumer(
            source_topic,
            bootstrap_servers=kafka_server
        )
        producer = kafka.KafkaProducer(
            value_serializer=bytes,
            bootstrap_servers=kafka_server
        )
    except:
        connection.send({'type': 'error', 'value': 'Kafka error'})
        return

    started = True

    while True:
        try:
            while connection.poll():
                # Handles new data from main process
                conn_msg = connection.recv()
                if conn_msg['type'] == 'outputs':
                    output_refs = conn_msg['value']
                    byte_format = '<' + 'd' * (len(output_refs) + 1)
                elif conn_msg['type'] == 'inputs':
                    input_refs, measurement_refs, measurement_proportions = conn_msg['value']
                elif conn_msg['type'] == 'stop':
                    try:
                        processor_instance.stop()
                    finally:
                        return
                elif conn_msg['type'] == 'status':
                    connection.send({'type': 'status', 'value': {
                        'outputs': outputs,
                        'inputs': inputs,
                        # Add a helper attribute that lists outputs that are part of a matrix
                        'matrix_outputs': matrix_outputs,
                        'initialized': initialized,
                        'started': started,
                    }})

            messages = consumer.poll(10)
            for msg in messages.get(topic_partition, []):
                # Handles new data from kafka
                for data in struct.iter_unpack(source_format, msg.value):
                    current_time = data[0]
                    if start_time < 0:
                        start_time = current_time
                    if next_input_time <= current_time or math.isclose(next_input_time, current_time, rel_tol=1e-15):
                        # Retrieve measurements from data where ref is positive and use a constant where ref is negative
                        measurements = [
                            (data[ref + 1] if ref >= 0 else 1) * measurement_proportions[i]
                            for i, ref in enumerate(measurement_refs)
                        ]
                        processor_instance.set_inputs(input_refs, measurements)
                        next_input_time = current_time + min_input_spacing
                    if next_step_time <= current_time or math.isclose(next_step_time, current_time, rel_tol=1e-15):
                        processor_instance.step(current_time - start_time)
                        next_step_time = current_time + min_step_spacing
                    if next_output_time <= current_time or math.isclose(next_output_time, current_time, rel_tol=1e-15):
                        outputs = processor_instance.get_outputs(output_refs)
                        if outputs is None:
                            continue
                        if processor_custom_time:
                            current_time = processor_instance.get_time() + start_time
                        output_buffer += struct.pack(byte_format, current_time, *outputs)
                        if len(output_buffer) > 100 * len(output_refs):
                            producer.send(topic=topic, value=output_buffer)
                            output_buffer = bytearray()
                        next_output_time = current_time + min_output_spacing
        except Exception as e:
            logger.exception(f'Exception in processor {processor_dir}')
            connection.send({'type': 'error', 'value': e})
            return


@dataclass
class Variable:
    """A simple container class for variable attributes"""

    valueReference: int
    name: str


class Processor:
    """The main process endpoint for processor processes"""

    def __init__(
            self,
            processor_id: str,
            blueprint_id: str,
            blueprint_path: str,
            init_params: dict,
            topic: str,
            source_topic: str,
            source_format: str,
            min_input_spacing: float,
            min_step_spacing: float,
            min_output_spacing: float,
            processor_root_dir: str,
            kafka_server: str
    ) -> None:
        """
        Initializes the processor process

        :param processor_id: the id to use for the processor
        :param blueprint_id: the id of the blueprint used to create the processor
        :param blueprint_path: the path to the blueprint used to create the processor
        :param init_params: the processors initialization parameters as a dict
        :param topic: the topic the processor will output results to
        :param source_topic: the topic the processor will receive data from
        :param source_format: the byte format of the data the processor will receive
        :param min_input_spacing: the minimum time between each input to the processor
        :param min_step_spacing: the minimum time between each step function call on the processor
        :param min_output_spacing: the minimum time between each results retrieval from the processor
        :param processor_root_dir: the directory the created process will run in
        :param kafka_server: the address of the kafka bootstrap server the process will use
        """

        self.processor_id = processor_id
        self.blueprint_id = blueprint_id
        self.init_params = init_params
        self.start_params = []
        self.topic = topic
        self.source_topic = source_topic
        self.source_format = source_format
        self.min_input_spacing = min_input_spacing
        self.min_step_spacing = min_step_spacing
        self.min_output_spacing = min_output_spacing
        self.connection, connection = multiprocessing.Pipe()
        self.input_refs = []
        self.output_refs = []
        self.actual_input_refs = []
        self.actual_output_refs = []
        self.measurement_refs = []
        self.measurement_proportions = []
        self.outputs = []
        self.matrix_outputs = []
        self.inputs = []
        self.byte_format = '<' + 'd' * (len(self.output_refs) + 1)
        self.processor_dir = os.path.join(processor_root_dir, processor_id)
        self.initialized = False
        self.started = False

        kwargs = dict(
            connection=connection,
            blueprint_path=blueprint_path,
            init_params=self.init_params,
            topic=self.topic,
            source_topic=self.source_topic,
            source_format=self.source_format,
            kafka_server=kafka_server,
            processor_dir=self.processor_dir,
            min_input_spacing=self.min_input_spacing,
            min_step_spacing=self.min_step_spacing,
            min_output_spacing=self.min_output_spacing,
        )
        self.process = multiprocessing.Process(target=processor_process, kwargs=kwargs)
        self.process.start()

    def start(self, input_refs, measurement_refs, measurement_proportions, output_refs, start_params):
        """
        Starts the process, must not be called before init_results

        :param input_refs: the indices of the inputs that will be used
        :param measurement_refs: the indices of the input data values that will be used.
                                 Must be in the same order as input_ref.
        :param measurement_proportions: list of scales to be used on values before inputting them.
                                        Must be in the same order as input_ref.
        :param output_refs: the indices of the inputs that will be used
        :param start_params: the processors start parameters as a dict
        :return: the processors status as a dict
        """
        self._set_inputs(
            input_refs=input_refs,
            measurement_refs=measurement_refs,
            measurement_proportions=measurement_proportions
        )
        self._set_outputs(output_refs)
        self.start_params = start_params
        self.connection.send({
            'type': 'start',
            'value': {
                'start_params': start_params,
                'output_refs': self.actual_output_refs,
                'input_refs': self.actual_input_refs,
                'measurement_refs': self.measurement_refs,
                'measurement_proportions': self.measurement_proportions,
            }
        })

    def retrieve_status(self):
        """
        Retrieves the status of the processor process

        Can only be called after initialization.
        Should be run in a separate thread to prevent the connection from blocking the main thread
        :return: the processors status as a dict
        """
        try:
            try:
                self.connection.send({'type': 'status'})
            finally:
                # Blocks the current thread until results are received
                result = self.connection.recv()
        except EOFError:
            result = {'type': 'error', 'value': 'The processor has crashed'}
        except Exception as e:
            result = {'type': 'error', 'value': 'Unable to get processor data (has probably crashed)'}
        if result['type'] == 'error':
            return {
                'url': '/processors/' + self.processor_id,
                'error': str(result['value'])
            }
        elif result['type'] == 'status':
            self.outputs = result['value']['outputs']
            self.matrix_outputs = result['value']['matrix_outputs']
            self.inputs = result['value']['inputs']
            self.initialized = result['value']['initialized']
            self.started = result['value']['started']
            return {
                'url': '/processors/' + self.processor_id,
                'input_names': [i.name for i in self.inputs],
                'output_names': [self.outputs[ref].name for ref in self.output_refs],
                'matrix_outputs': self.matrix_outputs,
                'available_output_names': [o.name for o in self.outputs],
                'byte_format': self.byte_format,
                'started': self.started,
                'initialized': self.initialized,
            }

    def set_inputs(self, input_refs, measurement_refs, measurement_proportions):
        """
        Sets the input values, must not be called before start

        :param output_refs: the indices of the inputs that will be used
        """
        self._set_inputs(input_refs, measurement_proportions, measurement_refs)
        self.connection.send(
            {'type': 'inputs', 'value': (self.actual_input_refs, measurement_refs, measurement_proportions)})
        return [i.name for i in self.inputs]

    def _set_inputs(self, input_refs, measurement_proportions, measurement_refs):
        """
        Sets what input values will be shown

        Should only be called by internal functions.
        Does not change the actual input values in the process.
        """
        self.input_refs = input_refs
        self.measurement_refs = measurement_refs
        self.measurement_proportions = measurement_proportions
        self.actual_input_refs = [self.inputs[ref].valueReference for ref in input_refs]

    def set_outputs(self, output_refs):
        """
        Sets the output values, must not be called before start

        :param input_refs: the indices of the inputs that will be used
        :param measurement_refs: the indices of the input data values that will be used.
                                 Must be in the same order as input_ref.
        :param measurement_proportions: list of scales to be used on values before inputting them.
                                        Must be in the same order as input_ref.
        """
        self._set_outputs(output_refs)
        self.connection.send({'type': 'outputs', 'value': self.actual_output_refs})
        return [o.name for o in self.outputs]

    def _set_outputs(self, output_refs):
        """
        Sets what output values will be shown

        Should only be called by internal functions.
        Does not change the actual output values in the process.
        """
        if output_refs == 'all':
            self.output_refs = list(range(len(self.outputs)))
            self.actual_output_refs = [o.valueReference for o in self.outputs]
        else:
            self.output_refs = output_refs
            self.actual_output_refs = [self.outputs[ref].valueReference for ref in output_refs]
        self.byte_format = '<' + 'd' * (len(self.output_refs) + 1)

    async def stop(self):
        """Attempts to stop the process nicely, killing it otherwise"""
        try:
            self.connection.send({'type': 'stop', 'value': ''})
        except BrokenPipeError:
            pass
        except EOFError:
            pass
        finally:
            i = 0
            while self.process.is_alive() and i < 50:
                await asyncio.sleep(.1)
                i += 1
            if self.process.is_alive():
                self.process.kill()
