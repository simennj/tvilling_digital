import os
import re
from collections import defaultdict
from typing import List

import fmpy
from fmpy import fmi2


def prepare_outputs(output_refs):
    vr = (fmi2.fmi2ValueReference * len(output_refs))(*output_refs)
    outputs = (fmi2.fmi2Real * len(output_refs))()
    return outputs, vr


cell_regex = re.compile(r'.+_m\d\d$')


class P:

    def __init__(self, fmu="testrig.fmu"):
        file = os.path.realpath(os.path.join('../../fmus', fmu)) # TODO: validate file path
        self.model_description = fmpy.read_model_description(file)
        self.dt = 0
        self.t = 0
        self.inputs = []
        self.time_step_input_ref = -1
        for variable in self.model_description.modelVariables:
            if variable.causality == 'input':
                if not variable.name == "Input_time_step":
                    self.inputs.append(variable)
                else:
                    self.time_step_input_ref = variable.valueReference
        self.matrix_outputs = defaultdict(list)
        self.outputs = []
        for variable in self.model_description.modelVariables:
            if variable.causality == 'output':
                self.outputs.append(variable)
                if cell_regex.match(variable.name):
                    self.matrix_outputs[variable.name[:-4]].append(len(self.outputs) - 1)
        self.file = file
        self.fmu = None

    def set_inputs(self, input_refs, input_values):
        self.fmu.setReal(input_refs, input_values)

    def start(self, start_time):
        with open(os.devnull, 'w') as outfile:
            os.dup2(outfile.fileno(), 1)
        self.fmu = fmi2.FMU2Slave(
            guid=self.model_description.guid,
            unzipDirectory=fmpy.extract(self.file, os.path.realpath('./')),
            modelIdentifier=self.model_description.coSimulation.modelIdentifier,
            instanceName=os.path.basename(os.path.realpath(os.curdir))
        )
        self.fmu.instantiate()
        self.fmu.setupExperiment(startTime=self.t)
        self.fmu.enterInitializationMode()
        self.fmu.exitInitializationMode()

    # def set_inputs(self, input_refs: List[int], input_values: List[int]):
    #     if self.time_input_ref >= 0:
    #         self.fmu.setReal([self.time_input_ref, *input_refs], [dt, *input_values])
    #     else:
    #         self.fmu.setReal(input_refs, input_values)

    def get_outputs(self, output_refs: List[int]):
        outputs, vr = prepare_outputs(output_refs)
        self.fmu.fmi2GetReal(self.fmu.component, vr, len(output_refs), outputs)
        return outputs

    def step(self, t):
        self.dt = t - self.t
        if self.dt > 0:
            if self.time_step_input_ref >= 0:
                self.fmu.setReal([self.time_step_input_ref], [self.dt])
            self.fmu.doStep(currentCommunicationPoint=self.t, communicationStepSize=self.dt)
            self.t = t

    def stop(self):
        self.fmu.terminate()


    # fmu.freeInstance()
