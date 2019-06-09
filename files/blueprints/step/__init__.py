"""
A blueprint for step functions
"""
from typing import List


class P:
    """
    The interface for the step function
    """
    input_names = ('not_used',)
    output_names = ('value',)

    def __init__(self, step_delay=1, start_value=0, end_value=1):
        """
        Sets step attributes

        :param step_delay: the number of seconds to wait before step start
        :param start_value: the value before step
        :param end_value: the value to step to
        """
        self.value = start_value
        self.end_value = end_value
        self.step_delay = step_delay

    def set_inputs(self, input_refs: List[int], input_values: List[int]):
        pass

    def get_outputs(self, output_refs: List[int]):
        if len(output_refs) == 1:
            return [self.value]
        return []

    def step(self, t):
        if self.value != self.end_value and t > self.step_delay:
            self.value = self.end_value
