"""
A blueprint for ramp functions
"""
from typing import List


class P:
    """
    The interface for the ramp function
    """
    input_names = ('not_used',)
    output_names = ('amplitude',)

    def __init__(self, ramp_delay=1, start_amplitude=0, end_amplitude=1):
        """
        Sets ramp attributes

        :param ramp_delay: the number of seconds to wait before ramp start
        :param start_amplitude: the amplitude before ramp
        :param end_amplitude: the amplitude to ramp to
        """
        self.amplitude = start_amplitude
        self.end_amplitude = end_amplitude
        self.ramp_delay = ramp_delay

    def set_inputs(self, input_refs: List[int], input_values: List[int]):
        pass

    def get_outputs(self, output_refs: List[int]):
        if len(output_refs) == 1:
            return [self.amplitude]
        return []

    def step(self, t):
        if self.amplitude != self.end_amplitude and t > self.ramp_delay:
            self.amplitude = self.end_amplitude
