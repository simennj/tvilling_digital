"""Butterworth filter
"""
from typing import List

import math
import numpy as np
import scipy.signal as si


class P:
    input_names = ('measurement',)
    output_names = ('filtered',)

    def __init__(self, sample_spacing=.01, buffer_size=500, cutoff_frequency=10, btype='hp', order=10):
        """
        :param sample_spacing: the time to be used between each sample
        :param buffer_size: the amount of samples to be used for each calculation
        :param cutoff_frequency: the frequency to filter on
        :param btype: the filter type "hp" for highpass, "lp" for lowpass
        :param order: the order to use for the butterworth filter
        """
        self.t = 0
        self.sample_spacing = float(sample_spacing)
        self.buffer_size = int(buffer_size)
        self.buffers = np.zeros((2, self.buffer_size))
        self.time_buffers = np.zeros((2, self.buffer_size))
        self.current_buffer = 0
        self.output_buffer = np.zeros(self.buffer_size)
        self.index = -1
        self.sos = si.butter(int(order), float(cutoff_frequency), btype, fs=1 / self.sample_spacing, output='sos')
        self.last_value = 0

    def start(self, start_time):
        self.t = start_time

    def set_inputs(self, input_refs: List[int], input_values: List[int]):
        if len(input_refs) == 1:
            self.last_value = input_values[0]

    def get_outputs(self, output_refs: List[int]):
        if len(output_refs) == 1:
            return [self.output_buffer[self.index]]

    def get_time(self):
        return self.time_buffers[(self.current_buffer + 1) % 2, self.index]

    def step(self, t):
        if self.t <= self.sample_spacing and t > 0:
            self.t = t
        while t >= self.t or math.isclose(t, self.t, rel_tol=1e-15):
            self.t += self.sample_spacing
            self.index += 1
            if self.index >= self.buffer_size:
                next_buffer = (self.current_buffer + 1) % 2
                self.output_buffer = si.sosfilt(
                    self.sos,
                    np.concatenate((
                        self.buffers[next_buffer],
                        self.buffers[self.current_buffer]
                    )))[self.buffer_size:]
                self.index = 0
                self.current_buffer = next_buffer
            self.buffers[self.current_buffer, self.index] = self.last_value
            self.time_buffers[self.current_buffer, self.index] = self.t
