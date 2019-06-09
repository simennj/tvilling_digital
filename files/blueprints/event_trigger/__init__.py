"""
A blueprint for event triggering
"""
from collections import namedtuple
from typing import List

Variable = namedtuple(
    'Variable',
    ('name', 'valueReference', 'value'),
    defaults=(None, None, 0)
)


class P:
    """The interface for the event trigger functionality"""

    def __init__(self, number_of_inputs, trigger_input, trigger_value, trigger_reason='gt'):
        """"""
        self.inputs = [
            Variable(
                name=str(i),
                valueReference=i,
                value=0
            )
            for i in range(number_of_inputs)
        ]
        self.outputs = [
            Variable(
                name=str(i),
                valueReference=i,
                value=0
            )
            for i in range(number_of_inputs)
        ]
        self.trigger_input = int(trigger_input)
        self.trigger_value = float(trigger_value)
        self.trigger_reason = trigger_reason
        self.triggered = False

    def set_inputs(self, input_refs, input_values):
        for i, ref in enumerate(input_refs):
            self.inputs[ref].value = input_values[i]
        if self.triggered:
            return
        if self.trigger_reason == 'gt' and input_values[self.trigger_input] > self.trigger_value:
            self.triggered = True
        elif self.trigger_reason == 'lt' and input_values[self.trigger_input] < self.trigger_value:
            self.triggered = True

    def get_outputs(self, output_refs: List[int]):
        if not self.triggered:
            return None
        return [self.inputs[ref].value for ref in output_refs]

    def step(self, t):
        pass
