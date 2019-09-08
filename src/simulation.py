# TODO: No longer in use
import logging
import operator
import os
import re
import shutil
from collections import defaultdict
from typing import List, Dict, Tuple

from fmpy import read_model_description, extract
from fmpy.fmi2 import FMU2Slave
from fmpy.model_description import ModelDescription

logger = logging.getLogger(__name__)


class ModelVariables:
    def __init__(self, model_description: ModelDescription):
        self.input_variables = {
            variable.name: variable for variable in model_description.modelVariables
            if variable.causality == 'input'
        }
        cell_regex = re.compile(r'.+_m\d\d$')
        self.matrix_output_variables = defaultdict(list)
        for variable in model_description.modelVariables:
            if variable.causality == 'output' and cell_regex.match(variable.name):
                self.matrix_output_variables[variable.name[:-4]].append(variable)
        self.scalar_output_variables = {
            variable.name: variable for variable in model_description.modelVariables
            if variable.causality == 'output' and variable.name[:-4] not in self.matrix_output_variables
        }
        self.scalar_variable_references = [
            variable.valueReference for variable in model_description.modelVariables
            if variable.name[:-4] not in self.matrix_output_variables
        ]

    def get_scalar_input_variable_references(self, *args) -> List[int]:
        if len(args) > 0:
            return [
                variable.valueReference for name, variable in self.input_variables.items()
                if name in args
            ]
        else:
            return [
                variable.valueReference for variable in self.input_variables.values()
            ]

    def get_scalar_output_variable_references(self, *args) -> List[int]:
        if len(args) > 0:
            return [
                variable.valueReference for name, variable in self.scalar_output_variables.items()
                if name in args
            ]
        else:
            return [
                variable.valueReference for variable in self.scalar_output_variables.values()
            ]

    def get_matrix_output_variable_references(self, *args) -> List[int]:
        if len(args) > 0:
            return [
                variable.valueReference for variable in
                operator.itemgetter(*args)(self.matrix_output_variables)
            ]
        else:
            return [
                variable.valueReference
                for matrix in self.matrix_output_variables.values()
                for variable in matrix
            ]

    def transform_inputs(self, kwargs: Dict[str, float]) -> Tuple[List[int], List[float]]:
        inputs = sorted(kwargs.items())
        return [
                   self.input_variables[name].valueReference for name, _ in inputs
                   if name in self.input_variables
               ], [
                   value for name, value in inputs
                   if name in self.input_variables
               ]

    def dict_repr(self):
        return {
            'input_variables': {n: v.__dict__ for n, v in self.input_variables.items()},
            'scalar_output_variables': {n: v.__dict__ for n, v in self.scalar_output_variables.items()},
            'matrix_output_variables': {n: [v.__dict__ for v in l] for n, l in self.matrix_output_variables.items()},
        }


class Twin:
    def __init__(self, file: str):
        self.file = file
        logger.info('Opening twin %s in %s', self.file, os.getcwd())
        self.model_description = read_model_description(file)
        self.variables = ModelVariables(self.model_description)
        self.unzipped_directory = extract(file)
        self.fmu = FMU2Slave(
            guid=self.model_description.guid,
            unzipDirectory=self.unzipped_directory,
            modelIdentifier=self.model_description.coSimulation.modelIdentifier,
            instanceName='instance'
        )
        self.running = False
        self.time = 0

    def set_inputs(self, **kwargs):  # TODO: slutte [ bruke kwargs for [ st;tte flere variabelnavn
        self.fmu.setReal(*self.variables.transform_inputs(kwargs))

    def get_scalar_outputs(self, *variable_references):  # TODO pute testbar logikk i variables tilsvarende inputs over
        return self.fmu.getReal(variable_references)

    def start(self):
        self.running = True
        self.fmu.instantiate()
        self.fmu.setupExperiment(startTime=self.time)
        self.fmu.enterInitializationMode()
        self.fmu.exitInitializationMode()

    def stop(self):
        self.fmu.terminate()
        self.fmu.freeInstance()
        shutil.rmtree(self.unzipped_directory)
        self.running = False

    def update(self, dt):
        if self.running:
            self.fmu.doStep(currentCommunicationPoint=self.time, communicationStepSize=dt)
            self.time += dt

    def dict_repr(self):
        return {
            'file': self.file,
            'variables': self.variables.dict_repr(),
            'running': self.running
        }


# Test fmu step by step through manual input
def main():
    model = Twin('CraneShort_w_pos_z_Longitudalupperstrain.zip')
    model.start()
    while True:
        try:
            next_input = float(input('Next: '))
        except ValueError:
            break
        model.set_inputs(Input_Displacement__Excitation=next_input)
        print(model.get_scalar_outputs(*model.variables.get_scalar_input_variable_references()))
        print(model.get_scalar_outputs(*model.variables.get_scalar_output_variable_references()))


if __name__ == '__main__':
    main()
