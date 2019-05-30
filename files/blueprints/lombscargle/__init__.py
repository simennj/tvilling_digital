"""Lombscargle processor
"""
from typing import List

import numpy as np
import scipy.signal as si


class P:
    input_names = ('measurement',)
    output_names = ('frequencies',)

    def __init__(self, buffer_size=100, min_freq=.5, max_freq=50, freq_outputs=1000):
        """

        :param sample_spacing: the time to be used between each sample
        :param window: the amount of samples to be used for each calculation
        """
        self.buffer_size = buffer_size
        self.buffer = np.zeros((2, self.buffer_size))
        self.index = -1
        self.last_value = 0
        self.normval = self.buffer_size
        self.w = np.linspace(min_freq * 2 * np.pi, max_freq * 2 * np.pi, freq_outputs)
        self.frequencies = self.w / (2 * np.pi)
        self.output_names = tuple(str(f) for f in self.frequencies)

    def start(self, start_time):
        pass

    def set_inputs(self, input_refs: List[int], input_values: List[int]):
        if len(input_refs) == 1:
            self.last_value = input_values[0]

    def get_outputs(self, output_refs: List[int]):
        try:
            pgram = si.lombscargle(
                np.roll(self.buffer[0], self.index),
                np.roll(self.buffer[1], self.index),
                self.w
            )
        except ZeroDivisionError:
            return [0 for _ in output_refs]
        outputs = np.sqrt(4 * (pgram / self.normval))
        return [outputs[output_ref] for output_ref in output_refs]

    def step(self, t):
        self.index += 1
        if self.index >= self.buffer_size:
            self.index = 0
        self.buffer[0, self.index] = t
        self.buffer[1, self.index] = self.last_value
