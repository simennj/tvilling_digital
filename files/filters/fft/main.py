"""Fast Fourier Transform
"""
from typing import List

import numpy as np


class F:
    input_names = ('measurement',)
    output_names = ('frequencies', 'calculated')
    # TODO: maybe output_names return the data in 'frequencies' instead  and get_outputs returns only the data in 'calculated' (based on selected frequencies). Should be more compatible with the fmu output

    def __init__(self, start_time, target_sampling_frequency, n):
        self.t = start_time
        self.dt = target_sampling_frequency
        self.n = n
        self.measurements = np.zeros(self.n, dtype=float)
        self.inputs = [
            0,
            100
        ]
        self.outputs = [
            np.fft.rfftfreq(self.n, self.dt),
            np.zeros(self.n, dtype=float)
        ]

    def set_inputs(self, input_refs: List[int], input_values: List[int]):
        for i in range(len(input_refs)):
            self.inputs[input_refs[i]] = input_values[i]

    def get_outputs(self, output_refs: List[int]):
        self.outputs[1] = np.abs(np.fft.rfft(self.measurements)) ** 2
        return [self.outputs[output_ref].tobytes() for output_ref in output_refs]

    def step(self, t):
        while t >= self.t or np.isclose(t, self.t):
            self.t += self.dt
            self.measurements[0] = self.inputs[0]
            self.measurements = np.roll(self.measurements, -1)
