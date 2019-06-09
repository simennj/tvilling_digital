""""""
from typing import List

import numpy as np


def generate_signal(frequencies, magnitudes):
    def s(t):
        return sum([
            magnitudes[i] * np.sin(frequencies[i] * (2 * np.pi * t))
            for i in range(len(frequencies))
        ])

    return s


class P:
    input_names = ('not_used',)
    output_names = ('amplitude',)

    def __init__(self, signals=(
            [1, 2,  4, 8, 16, 32, 64, 128],
            [0, 0, 1.0, 0, 0, 0, 0, 0]
    )):
        self.signal = generate_signal(*signals)
        self.t = 0

    def start(self, start_time):
        self.t = start_time

    def set_inputs(self, input_refs: List[int], input_values: List[int]):
        pass

    def get_outputs(self, output_refs: List[int]):
        if len(output_refs) == 1:
            return [self.signal(self.t)]
        return []

    def step(self, t):
        self.t = t
