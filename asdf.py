import importlib

import matplotlib.pyplot as plt
import numpy as np


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


dt = 1 / 300
n = 300
start_time = 0
end_time = 1
if __name__ == '__main__':
    # plt.figure(dpi=1200)

    filter = importlib.import_module('files.filters.fft.main').F(start_time, dt)
    signal = generate_signal([1, 2, 4, 8, 16, 32, 64, 128], [0, 1, 0, 0, 0, .5, 0, 0])
    noise = generate_noise(1)
    freqs, vals, idx = None, None, None
    filter.set_inputs([1], 100)

    i = 0
    t_range = np.arange(start_time, end_time, dt)
    plt.plot(t_range, [signal(t) + noise(t) for t in t_range])
    plt.show()
    for t in t_range:
        filter.set_inputs([0], [signal(t) + noise(t)])
        filter.step(t)

        if i % n == n - 1:
            freqs, vals = filter.get_outputs([0, 1])
            # idx = np.argsort(freqs)
            # plt.plot(freqs[idx], vals[idx])
            plt.plot(freqs, vals)
            plt.show()
        i += 1
