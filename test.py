import multiprocessing
import os
import shutil
import struct
from multiprocessing.connection import Connection
from time import sleep
from typing import List

import sys
from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave, fmi2Real, fmi2ValueReference
from kafka import KafkaConsumer, KafkaProducer

import settings
from src.datasources.models import generate_catman_byte_formats


def simulate(
        connection: Connection,
        model: str,
        datasource: str,
        byte_format: str,
        sim_id: str,
        measurement_refs: List[int],
        measurement_proportions: List[float],
        inputs_refs: List[int],
        time_measurement_ref: int,
        time_input_ref: int,
        output_refs: List[int]
):
    sim_dir = os.path.abspath(os.path.join(settings.SIMULATION_DIR, sim_id))
    if os.path.exists(sim_dir):
        shutil.rmtree(sim_dir)
    os.mkdir(sim_dir)

    with open(os.path.join(sim_dir, 'stdout'), 'w') as outfile:
        os.dup2(outfile.fileno(), 1)
    consumer = KafkaConsumer(
        datasource,
        bootstrap_servers=settings.KAFKA_SERVER
    )
    producer = KafkaProducer(
        value_serializer=bytes,
        bootstrap_servers=settings.KAFKA_SERVER,
    )
    topic = f'FMU_{sim_id}'

    model_description = read_model_description(model)
    fmu = FMU2Slave(
        guid=model_description.guid,
        unzipDirectory=extract(model, sim_dir),
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
    start_time = last_time = struct.unpack(byte_format, msg.value)[time_measurement_ref]
    # consumer.poll()
    for msg in consumer:

        if connection.poll():
            conn_msg = connection.recv()
            if conn_msg['type'] == 'output_refs':
                output_refs = conn_msg['value']

        data = struct.unpack(byte_format, msg.value)
        current_time = data[time_measurement_ref]
        dt = current_time - last_time
        if dt < min_dt:
            continue
        measurements = [measurement_proportions[i] * data[ref] for i, ref in enumerate(measurement_refs)]
        fmu.setReal([time_input_ref, *inputs_refs], [dt, *measurements])
        fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
        vr = (fmi2ValueReference * len(output_refs))(*output_refs)
        outputs = (fmi2Real * len(output_refs))()
        fmu.fmi2GetReal(fmu.component, vr, len(output_refs), outputs)
        producer.send(topic, outputs)
        t = current_time - start_time
        last_time = current_time

    fmu.terminate()
    # fmu.freeInstance()


if __name__ == '__main__':
    a, b = multiprocessing.Pipe()
    kwargs = dict(
        connection=b,
        model=os.path.abspath(os.path.join(settings.FMU_DIR, 'testrig.fmu')),
        datasource='UDP_129.241.90.108_7331',
        sim_id='asdf',
        measurement_refs=[7],
        measurement_proportions=[.001],
        inputs_refs=[0],
        time_measurement_ref=-1,
        time_input_ref=1,
        byte_format=generate_catman_byte_formats([
            'Time',
            'Garbage',
            'Garbage',
            'Load N',
            'Displacement mm',
            'AccelerometerX',
            '0 Degrees Transvers on Axle',
            'Rosett +45 Degrees Along Axle',
            'Rosett  90 Degrees Along Axle',
            'Rosett  -45 Degrees Along Axle',
            'Radius +45 Degrees Along Axle',
            'MX840A_0 hardware time default sample rate',
        ]),
        output_refs=[2, 3],
    )
    # simulate(**kwargs)
    p = multiprocessing.Process(target=simulate, kwargs=kwargs)
    p.start()
    print('module name:', __name__)
    print('parent process:', os.getppid())
    print('process id:', os.getpid())
    sleep(5)
    try:
        while p.is_alive():
            msg_type = input('type: ')
            msg_value = []
            while True:
                v = input('value: ')
                if not v: break
                msg_value.append(int(v))
            a.send({'type': msg_type, 'value': msg_value})
    except KeyboardInterrupt:
        pass
    finally:
        p.join(5)
