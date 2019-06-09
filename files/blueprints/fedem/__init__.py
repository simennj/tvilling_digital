import os
from collections import namedtuple
from typing import List

# from files.blueprints.fedem.fedemdll.vpmSolverRun import VpmSolverRun
import numpy as np

Variable = namedtuple('Variable',
                      ('name', 'valueReference', 'value'),
                      defaults=(None, None, 0)
                      )


def extract_inputs(file):
    functions = {}
    inputs = []
    with open(file, 'r') as f:
        for line in f:
            if line == 'ENGINE\n':
                for l in f:
                    if l == '{\n':
                        continue
                    if l == '}\n':
                        break
                    k, v = l.split("=")
                    if k.strip() == "ID":
                        func_id = int(v.split(';')[0])
                    elif k.strip() == 'DESCR':
                        func_name = v.split('"')[1]
                functions[func_id] = func_name
            if line == 'FUNC_EXTERNAL_FUNCTION\n':
                f.__next__()
                ref = int(f.__next__().split('=')[1].split(';')[0])
                f.__next__()
                func_id = int(f.__next__().split('=')[1].split(';')[0])
                inputs.append(Variable(name=functions[func_id], valueReference=ref)) #TODO: channel_id or id????
                del functions[func_id]
        # TODO: outputs = [asdf for functions]
    return inputs


class P:

    def __init__(self, model='CraneShort', time_step=.1):
        # Initiate VpmSolverRun object
        file_path = os.path.abspath(os.path.join('../../models', model, model + '.fmm'))
        self.inputs = extract_inputs(file_path)
        self.outputs = [

        ]
        # self.twin = VpmSolverRun(file_path) #TODO: mangler response_ folder eller noe sånt
        self.time_step = time_step
        self.last_twin_time = 0
        self.initial_values = {}
        self.initial_values_interpolated = True
        self.start_duration = None
        self.t = 0

    def start(self, start_time, initial_values=None, start_duration=5,):
        self.start_duration = start_duration
        if initial_values:
            self.initial_values_interpolated = False

        # Initialization of solver (Needed for fedem functions)
        # for n in range(2):
        #     self.twin.solveNext()
        # self.calculate_compliance_matrix()
        # self.last_twin_time = self.twin.getCurrentTime()

    def set_inputs(self, input_refs, input_values):
        if not self.initial_values_interpolated:
            self.interpolate_initial_values(input_refs, input_values)
        for i, ref in enumerate(input_refs):
            self.twin.setExtFunc(ref, self.last_twin_time, input_values[i])

    def get_outputs(self, output_refs):
        pass
        #TODO: self.twin.getFunction(ref) for ref in output_refs

    def interpolate_initial_values(self, input_refs: List[int], input_values):
        # Timing
        numberOfSteps = round((self.start_duration / self.time_step))
        initial_values = {
            k: {
                'model': v,
                'init': input_values[input_refs.index(k)],
                'interpolated': 0,
                'stepsize': (input_values[input_refs.index(k)]-v)/numberOfSteps
            } for k, v in self.initial_values
        }
        # Go to initial
        for i in range(0, numberOfSteps, 1):
            time = self.twin.getCurrentTime()
            for k, v in initial_values.items():
                self.twin.setExtFunc(k, time, v['interpolated'])
                v['interpolated'] += v['stepsize']
            self.twin.solveNext()
        # One Second of Idle time
        for i in range(0, 100, 1):
            time = self.twin.getCurrentTime()
            for k, v in initial_values.items():
                self.twin.setExtFunc(k, time, v['interpolated'])
            self.twin.solveNext()
        self.initial_values_interpolated = True

    def step(self, t):
        twin_time = self.twin.getCurrentTime()

        # CALCULATE FORCES
        # F = self.S @ np.array([filtered_UT[i], filtered_UR[i], filtered_REF[i]])

        # # SET FORCE
        # self.twin.setExtFunc(6, time, F[0])
        # self.twin.setExtFunc(7, time, F[1])
        # self.twin.setExtFunc(8, time, F[2])

        # # Calculate Movement
        # actuatorLower = (float(temp[5]) / 100) - 0.10099981     # Prismatic Joint 1
        # actuatorUpper = (float(temp[6]) / 100) - 0.040999981    # Prismatic Joint 3
        # base = float(temp[10]) * (3.14 / 180) * (10 / 16500)    # Radians

        # # Actuator movement
        # self.twin.setExtFunc(1, time, actuatorLower)
        # self.twin.setExtFunc(2, time, actuatorUpper)

        # # Base Rotation
        # self.twin.setExtFunc(5, time, base)

        while t >= self.t:
            self.twin.solveNext()
            self.last_twin_time = twin_time
            self.t += self.time_step

    def calculate_compliance_matrix(self):
        # This part is only needed once, unless there is made structural changes to the Fedem model
        # Variable declarations
        out_def = [19, 20, 21]  # UT UR UL
        Sinv = np.zeros((3, 3))
        inp = 1  # Input Force [N]
        inp_def = [6, 7, 8]  # Fx Fy Fz
        for j in range(3):

            # Variable declarations
            out = [np.inf, np.inf, np.inf]  # Strain Output (From virtual strain gauges)

            # Apply Force
            time = self.twin.getCurrentTime()
            self.twin.setExtFunc(inp_def[j], time, inp)

            # Let Structure settle after applying force
            for k in range(600):
                self.twin.solveNext()

            # Get values from virtual strain gauges
            out[0] = self.twin.getFunction(out_def[0])  # UT
            out[1] = self.twin.getFunction(out_def[1])  # UR
            # out[2] = twin.getFunction(out_def[2]) # Inverse method using "UL"
            out[2] = self.twin.getFunction(35)  # REF

            time = self.twin.getCurrentTime()
            Sinv[:, j] = np.array(out)

            # Cancel Force
            self.twin.setExtFunc(inp_def[j], time, 0)
            self.twin.solveNext()

            # Half second of idle time
            for k in range(50):
                self.twin.solveNext()
        # Calculate compliance matrix S
        self.S = np.linalg.inv(Sinv)
        print("S")
        print(self.S)
