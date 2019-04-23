import multiprocessing
import os
import shutil
from time import sleep

from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave


def a(model, unzipdir, datasource: str, byte_format: str, id: str):
    print(model)
    print(datasource)
    print(byte_format)
    print(id)
    print('module name:', __name__)
    print('parent process:', os.getppid())
    print('process id:', os.getpid())

    t = 0
    dt = .1

    model_description = read_model_description(model)
    dir = os.path.join('simulation_files', id)
    try:
        os.mkdir(dir)
        fmu = FMU2Slave(
            guid=model_description.guid,
            unzipDirectory=extract(model, os.path.abspath(dir)),
            modelIdentifier=model_description.coSimulation.modelIdentifier,
            instanceName=id
        )
        fmu.instantiate()
        fmu.setupExperiment(startTime=t)
        fmu.enterInitializationMode()
        fmu.exitInitializationMode()

        while t < 10:
            fmu.doStep(currentCommunicationPoint=t, communicationStepSize=dt)
            t += dt

        fmu.terminate()
        fmu.freeInstance()
    finally:
        shutil.rmtree(dir)


if __name__ == '__main__':
    p = multiprocessing.Process(target=a, kwargs=dict(
        model=os.path.abspath('fmu_files/testrig.fmu'),
        unzipdir=os.path.abspath('simulation_files'),
        datasource='127.0.0.1_7331',
        byte_format='',
        id='asdf'
    ))
    p.start()
    print('module name:', __name__)
    print('parent process:', os.getppid())
    print('process id:', os.getpid())
    try:
        while p.is_alive():
            print('Still running')
            sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        p.join(5)
