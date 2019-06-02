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

    blueprint_path = os.path.realpath(blueprint_path)

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

    if hasattr(processor_instance, 'outputs'):
        outputs = processor_instance.outputs
    else:
        outputs = [Variable(i, name) for i, name in enumerate(processor_instance.output_names)]
    if hasattr(processor_instance, 'inputs'):
        inputs = processor_instance.inputs
    else:
        inputs = [Variable(i, name) for i, name in enumerate(processor_instance.input_names)]
    connection.send({'type': 'initialized', 'value': {
        'outputs': [Variable(v.valueReference, v.name) for v in outputs],
        'inputs': [Variable(v.valueReference, v.name) for v in inputs],
        # Add a helper attribute that lists outputs that are part of a matrix
        'matrix_outputs':
            processor_instance.matrix_outputs
            if hasattr(processor_instance, 'matrix_outputs')
            else []
    }})

    byte_format = '<d'
    output_refs = []
    input_refs = []
    measurement_refs = []
    measurement_proportions = []

    topic_partition = TopicPartition(topic=source_topic, partition=0)
    output_buffer = bytearray()

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

    processor_instance.start(
        start_time=next_output_time,
        **start_params
    )
    if hasattr(processor_instance, "get_time"):
        processor_custom_time = True
    else:
        processor_custom_time = False

    consumer = kafka.KafkaConsumer(
        source_topic,
        bootstrap_servers=kafka_server
    )
    producer = kafka.KafkaProducer(
        value_serializer=bytes,
        bootstrap_servers=kafka_server
    )

    while True:
        try:
            while connection.poll():
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
                        connection.send({'type': 'stop'})
                        return
                # if conn_msg['type'] == 'reload': importlib.reload

            messages = consumer.poll()

            for msg in messages.get(topic_partition, []):
                for data in struct.iter_unpack(source_format, msg.value):
                    current_time = data[0]
                    if start_time < 0:
                        start_time = current_time
                    if next_input_time <= current_time or math.isclose(next_input_time, current_time, rel_tol=1e-15):
                        measurements = [data[ref + 1] * measurement_proportions[i] for i, ref in
                                        enumerate(measurement_refs)]
                        processor_instance.set_inputs(input_refs, measurements)
                        next_input_time = current_time + min_input_spacing
                    if next_step_time <= current_time or math.isclose(next_step_time, current_time, rel_tol=1e-15):
                        processor_instance.step(current_time - start_time)
                        next_input_time = current_time + min_step_spacing
                    if next_output_time <= current_time or math.isclose(next_output_time, current_time, rel_tol=1e-15):
                        outputs = processor_instance.get_outputs(output_refs)
                        if processor_custom_time:
                            current_time = processor_instance.get_time() + start_time
                        output_buffer += struct.pack(byte_format, current_time, *outputs)
                        if len(output_buffer) > 80 * len(output_refs):
                            producer.send(topic=topic, value=output_buffer)
                            output_buffer = bytearray()
                        next_output_time = current_time + min_output_spacing
        except Exception as e:
            logger.exception(f'Exception in processor {processor_dir}')
            connection.send({'type': 'error', 'value': e})

        time.sleep(.001)

@dataclass
class Variable:
    """A simple container class for variable attributes"""

    valueReference: int
    name: str


class Processor:

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

        # self.init_var_names = processor_class.__init__.__code__.co_varnames[1:]

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

    def retrieve_init_results(self):
        """Waits for and returns the results from the process initalization

        Can only be called once after initialization
        :return: the processors status as a dict
        """
        try:
            result = self.connection.recv()
        except EOFError:
            result = {'type': 'error', 'value': 'The processor crashed on initialization'}
        except Exception as e:
            result = {'type': 'error', 'value': 'Unable to process initialization data from processor'}
        if result['type'] == 'error':
            return {
                'url': '/processors/' + self.processor_id,
                'error': str(result['value'])
            }
        elif result['type'] == 'initialized':
            self.outputs = result['value']['outputs']
            self.matrix_outputs = result['value']['matrix_outputs']
            self.inputs = result['value']['inputs']
            self.initialized = True
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

    def start(self, input_refs, measurement_refs, measurement_proportions, output_refs, start_params):
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
        self.started = True
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
        self._set_inputs(input_refs, measurement_proportions, measurement_refs)
        self.connection.send(
            {'type': 'inputs', 'value': (self.actual_input_refs, measurement_refs, measurement_proportions)})
        return [i.name for i in self.inputs]

    def _set_inputs(self, input_refs, measurement_proportions, measurement_refs):
        self.input_refs = input_refs
        self.measurement_refs = measurement_refs
        self.measurement_proportions = measurement_proportions
        self.actual_input_refs = [self.inputs[ref].valueReference for ref in input_refs]

    def set_outputs(self, output_refs):
        self._set_outputs(output_refs)
        self.connection.send({'type': 'outputs', 'value': self.actual_output_refs})
        return [o.name for o in self.outputs]

    def _set_outputs(self, output_refs):
        if output_refs == 'all':
            self.output_refs = list(range(len(self.outputs)))
            self.actual_output_refs = [o.valueReference for o in self.outputs]
        else:
            self.output_refs = output_refs
            self.actual_output_refs = [self.outputs[ref].valueReference for ref in output_refs]
        self.byte_format = '<' + 'd' * (len(self.output_refs) + 1)

    def stop(self):
        try:
            self.connection.send({'type': 'stop', 'value': ''})
        except BrokenPipeError:
            pass
        except EOFError:
            pass
        finally:
            self.process.join(5)
            self.process.kill()
