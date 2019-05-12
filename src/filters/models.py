import multiprocessing
import os
import struct
from importlib.machinery import SourceFileLoader
from multiprocessing.connection import Connection

import kafka


def filter_process(
        connection: Connection,
        filter_class,
        filter_vars: dict,
        instance_dir: str,
        topic: str,
        source_topic: str,
        source_format: str,
        kafka_server: str,
        time_source_ref: int,
        min_transmit_interval: int,
):
    consumer = kafka.KafkaConsumer(
        source_topic,
        bootstrap_servers=kafka_server
    )
    producer = kafka.KafkaProducer(
        value_serializer=bytes,
        bootstrap_servers=kafka_server
    )

    os.makedirs(instance_dir)

    output_refs = []
    inputs_refs = []
    measurement_refs = []

    filter_instance = filter_class(**filter_vars)

    last_time = 0
    # Use consumer.poll() instead of iterator?
    for msg in consumer:
        while connection.poll():
            conn_msg = connection.recv()
            if conn_msg['type'] == 'output_refs':
                output_refs = conn_msg['value']
            if conn_msg['type'] == 'inputs':
                inputs_refs, measurement_refs, measurement_proportions = conn_msg['value']
            # if conn_msg['type'] == 'reload': importlib.reload

        # TODO: will only use the first measurement if there are multiple measurements in the message
        data = struct.unpack(source_format, msg.value)
        current_time = data[time_source_ref]
        measurements = [data[ref] for ref in measurement_refs]

        filter_instance.set_inputs(inputs_refs, measurements)
        filter_instance.step(current_time)

        if last_time + min_transmit_interval > current_time:
            outputs = filter_instance.get_outputs(output_refs)
            producer.send(topic, outputs)
            last_time = current_time


class Filter:

    def __init__(
            self,
            instance_id: str,
            filter_id: str,
            filter_vars: dict,
            source_topic: str,
            source_format: str,
            time_source_ref: int,
            min_transmit_interval: float,
            filter_root_dir: str,
            kafka_server: str
    ) -> None:
        self.instance_id = instance_id
        self.filter_id = filter_id
        self.filter_vars = filter_vars
        self.topic = f'FIL_{instance_id}'
        self.source_topic = source_topic
        self.source_format = source_format
        self.time_source_ref = time_source_ref
        self.min_transmit_interval = min_transmit_interval
        self.connection, connection = multiprocessing.Pipe()
        self.input_refs = []
        self.measurement_refs = []
        self.filter_dir = os.path.join(filter_root_dir, filter_id)

        filter_class = SourceFileLoader(
            'filter_id', os.path.join(self.filter_dir, 'main.py')
        ).load_module().filter_class
        self.init_var_names = filter_class.__init__.__code__.co_varnames[1:]

        self.instance_dir = os.path.join(self.filter_dir, 'instances', instance_id)

        kwargs = dict(
            connection=connection,
            filter_class=filter_class,
            filter_vars=self.filter_vars,
            instance_dir=self.instance_dir,
            topic=self.topic,
            source_topic=self.source_topic,
            source_format=self.source_format,
            kafka_server=kafka_server,
            time_source_ref=self.time_source_ref,
            min_transmit_interval=self.min_transmit_interval,
        )
        self.process = multiprocessing.Process(target=filter_process, kwargs=kwargs)

    def start(self):
        self.process.start()

    def set_inputs(self, input_refs, measurement_refs, measurement_proportions):
        self.input_refs = input_refs
        self.measurement_refs = measurement_refs
        self.connection.send({'type': 'inputs', 'value': (input_refs, measurement_refs, measurement_proportions)})

    def stop(self):
        # TODO: gracefully stop
        self.process.join(5)
