import importlib

import matplotlib.pyplot as plt
import numpy as np
from scipy import signal as si


def generate_signal(frequencies, magnitudes):
    def s(t):
        return sum([
            magnitudes[i] * np.sin(frequencies[i] * (2 * np.pi * t))
            for i in range(len(frequencies))
        ])

    return s


def generate_noise(magnitude):
    def noise(t):
        return (np.random.random() - .5) * 2 * magnitude

    return noise


sample_spacing = 1 / 300
start_time = 0
end_time = 10
order = 10
buffer_size = 400
cutoff_frequency = 10
btype = 'hp'
if __name__ == '__main__':
    # plt.figure(dpi=1200)

    freq_outputs = 100
    max_freq = 100
    min_freq = 1
    p = importlib.import_module('files.blueprints.lombscargle.main').P(
        start_time, buffer_size, min_freq, max_freq, freq_outputs
    )
    signal = generate_signal([1, 2, 4, 8, 16, 32, 64, 128], [0, 0, .5, 0, 1, 2, 0, 0])
    noise = generate_noise(.0)
    t_range = np.arange(start_time, end_time, sample_spacing)
    plt.plot(t_range, [signal(t) + noise(t) for t in t_range])
    plt.show()
    normval = t_range.shape[0]
    w = np.linspace(min_freq * 2 * np.pi, max_freq * 2 * np.pi, freq_outputs)
    f = w / (2 * np.pi)
    pgram = si.lombscargle(t_range, [signal(t) + noise(t) for t in t_range], w)
    plt.plot(f, np.sqrt(4 * (pgram / normval)))
    plt.show()

    for i, t in enumerate(t_range):
        p.set_inputs([0], [signal(t) + noise(t)])
        p.step(t)
    output = p.get_outputs(list(range(freq_outputs)))
    plt.plot(f, output)
    plt.show()
