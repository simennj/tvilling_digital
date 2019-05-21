""""""
from typing import List


class P:
    input_names = ('measurement',)
    output_names = ('frequencies',)

    def __init__(self, start_time):
        pass

    def set_inputs(self, input_refs: List[int], input_values: List[int]):
        pass

    def get_outputs(self, output_refs: List[int]):
        return output_refs

    def step(self, t):
        pass
