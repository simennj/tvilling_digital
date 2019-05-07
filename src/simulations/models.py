import multiprocessing
import os
import shutil
import struct
from multiprocessing.connection import Connection
from typing import List

import kafka
import fmpy
from fmpy import fmi2

from src.datasources.models import UdpDatasource


def simulate(
        connection: Connection,
        model: str,
        source_topic: str,
        source_format: str,
        sim_id: str,
        sim_root_dir: str,
        kafka_server: str,
        measurement_refs: List[int],
        measurement_proportions: List[float],
        inputs_refs: List[int],
        time_measurement_ref: int,
        time_input_ref: int,
        output_refs: List[int]
):
    sim_dir = os.path.abspath(os.path.join(sim_root_dir, sim_id))
    if os.path.exists(sim_dir):
        shutil.rmtree(sim_dir)
    os.mkdir(sim_dir)

    with open(os.path.join(sim_dir, 'stdout'), 'w') as outfile:
        os.dup2(outfile.fileno(), 1)
    consumer = kafka.KafkaConsumer(
        source_topic,
        bootstrap_servers=kafka_server
    )
    producer = kafka.KafkaProducer(
        value_serializer=bytes,
        bootstrap_servers=kafka_server
    )
    topic = f'FMU_{sim_id}'

    outputs, vr = prepare_outputs(output_refs)
    model_description = fmpy.read_model_description(model)
    fmu = fmi2.FMU2Slave(
        guid=model_description.guid,
        unzipDirectory=fmpy.extract(model, sim_dir),
        modelIdentifier=model_description.coSimulation.modelIdentifier,
        instanceName=sim_id
    )
    fmu.instantiate()
    t = 0
    fmu.setupExperiment(startTime=t)
    fmu.enterInitializationMode()
    fmu.exitInitializationMode()

    min_dt = 0.001
    msg = consumer.__next__()  # Will skip the other values of the first message
    start_time = last_time = struct.unpack(source_format, msg.value)[time_measurement_ref]

    # Use consumer.poll() instead of iterator?
    for msg in consumer:

        while connection.poll():
            conn_msg = connection.recv()
            if conn_msg['type'] == 'output_refs':
                output_refs = conn_msg['value']
                outputs, vr = prepare_outputs(output_refs)
            if conn_msg['type'] == 'inputs':
                inputs_refs, measurement_refs, measurement_proportions = conn_msg['value']

        data = struct.unpack(source_format, msg.value)
        current_time = data[time_measurement_ref]
        dt = current_time - last_time
        if dt < min_dt:
            continue
        measurements = [measurement_proportions[i] * data[ref] for i, ref in enumerate(measurement_refs)]

        # Input time to simulation input if time_input_ref is valid
        if time_input_ref >= 0:
            fmu.setReal([time_input_ref, *inputs_refs], [dt, *measurements])
        else:
            fmu.setReal(inputs_refs, measurements)
        fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
        fmu.fmi2GetReal(fmu.component, vr, len(output_refs), outputs)
        producer.send(topic, outputs)
        t = current_time - start_time
        last_time = current_time

    fmu.terminate()
    # fmu.freeInstance()


def prepare_outputs(output_refs):
    vr = (fmi2.fmi2ValueReference * len(output_refs))(*output_refs)
    outputs = (fmi2.fmi2Real * len(output_refs))()
    return outputs, vr


class Simulation:

    def __init__(self, sim_id: str, fmu: str, fmu_dir: str, datasource: UdpDatasource,
                 time_input_ref: int, time_measurement_ref: int, sim_root_dir, kafka_server) -> None:
        self.sim_id = sim_id
        self.fmu = fmu
        self.datasource = datasource
        self.connection, connection = multiprocessing.Pipe()
        self.output_refs = []
        self.input_refs = []
        self.measurement_refs = []
        self.time_input_ref = time_input_ref
        self.time_measurement_ref = time_measurement_ref
        self.measurement_proportions = []
        kwargs = dict(
            connection=connection,
            model=os.path.abspath(os.path.join(fmu_dir, fmu)),
            source_topic=datasource.topic,
            source_format=datasource.byte_format,
            sim_id=sim_id,
            sim_root_dir=sim_root_dir,
            kafka_server=kafka_server,
            measurement_refs=[],
            measurement_proportions=[],
            inputs_refs=[],
            time_measurement_ref=time_measurement_ref,
            time_input_ref=time_input_ref,
            output_refs=[],
        )
        self.process = multiprocessing.Process(target=simulate, kwargs=kwargs)

    def start(self):
        self.process.start()

    def set_outputs(self, output_refs: List[int]):
        self.output_refs = output_refs
        self.connection.send({'type': 'output_refs', 'value': output_refs})

    def set_inputs(self, input_refs, measurement_refs, measurement_proportions):
        self.input_refs = input_refs
        self.measurement_refs = measurement_refs
        self.connection.send({'type': 'inputs', 'value': (input_refs, measurement_refs, measurement_proportions)})

    def stop(self):
        # TODO: gracefully stop the simulation
        self.process.join(5)

