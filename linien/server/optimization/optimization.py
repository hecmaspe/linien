import math
import pickle
import random
import numpy as np
from time import sleep, time
from scipy.signal import resample

from linien.communication.client import BaseClient
from linien.common import determine_shift_by_correlation, MHz, Vpp, get_lock_point
from linien.server.autolock import Approacher

from .cma_es import CMAES


# after the line was centered, its width will be 1/FINAL_ZOOM_FACTOR of the
# view.
FINAL_ZOOM_FACTOR = 10


def convert_params(params, xmin, xmax):
    converted = []

    for v, min_, max_ in zip(params, xmin, xmax):
        converted.append(
            min_ + v * (max_ - min_)
        )

    return converted


class OptimizeSpectroscopy:
    def __init__(self, control, parameters):
        self.control = control
        self.parameters = parameters

        self.initial_spectrum = None
        self.iteration = 0

        self.approacher = None

        self.recenter_after = 2
        self.next_recentering_iteration = self.recenter_after
        self.allow_increase_of_recentering_interval = True

    def run(self, x0, x1, spectrum):
        self.parameters.optimization_approaching.value = True

        spectrum = pickle.loads(spectrum)
        cropped = spectrum[x0:x1]
        min_idx = np.argmin(cropped)
        max_idx = np.argmax(cropped)
        self.x0, self.x1 = x0 + min_idx, x0 + max_idx

        self.record_first_error_signal(spectrum)

        params = self.parameters

        freqs = list(sorted([
            params.optimization_mod_freq_min.value * MHz,
            params.optimization_mod_freq_max.value * MHz
        ]))
        ampls = list(sorted([
            params.optimization_mod_amp_min.value * Vpp,
            params.optimization_mod_amp_max.value * Vpp
        ]))

        self.xmin = [freqs[0], ampls[0], 0]
        self.xmax = [freqs[1], ampls[1], 360]

        self.opt = CMAES()
        self.opt.lamb = 10
        self.opt.sigma = .6

        self.opt.x0 = [0.5, 0.5, 0.5]
        self.opt._upper_limits = [1, 1, 1]
        self.opt._lower_limits = [0, 0, 0]

        self.fitness_arr = []

        params.to_plot.change(self.react_to_new_spectrum)
        params.optimization_running.value = True
        params.optimization_improvement.value = 0

    def record_first_error_signal(self, error_signal):
        _, _2, target_zoom, rolled_error_signal = get_lock_point(
            error_signal, *list(sorted([self.x0, self.x1])),
            final_zoom_factor=FINAL_ZOOM_FACTOR
        )

        self.target_zoom = target_zoom
        self.first_error_signal = rolled_error_signal

        self.approacher = Approacher(
            self.control, self.parameters, self.first_error_signal,
            self.target_zoom
        )

        params = self.parameters
        self.initial_params = (
            params.modulation_frequency.value, params.modulation_amplitude.value,
            params.demodulation_phase_a.value
        )

    def request_new_parameters(self, use_initial_parameters=False):
        new_params = convert_params(self.opt.request_parameter_set(), self.xmin, self.xmax) \
            if not use_initial_parameters \
            else self.initial_params
        self.set_parameters(new_params)

    def react_to_new_spectrum(self, spectrum):
        # FIXME: try exept wie in autolock
        params = self.parameters

        # FIXME: hardcoded error_signal_1
        spectrum = pickle.loads(spectrum)['error_signal_1']

        if self.parameters.optimization_approaching.value:
            approaching_finished = self.approacher.approach_line(spectrum)
            if approaching_finished:
                self.parameters.optimization_approaching.value = False
        else:
            print(self.get_max_slope(spectrum))
            return
            self.iteration += 1

            if self.initial_spectrum is None:
                params = self.parameters
                self.initial_spectrum = spectrum
                self.last_parameters = self.initial_params
                self.initial_diff = self.get_max_slope(spectrum)

            center_line = self.iteration == self.next_recentering_iteration
            center_line_next_time = self.iteration + 1 == self.next_recentering_iteration

            if self.iteration > 1:
                if center_line:
                    # center the line again
                    shift, _, _2 = determine_shift_by_correlation(
                        1, self.initial_spectrum, spectrum
                    )
                    params.center.value -= shift * params.ramp_amplitude.value
                    self.control.exposed_write_data()

                    if self.allow_increase_of_recentering_interval and \
                            abs(shift) < 2 / FINAL_ZOOM_FACTOR:
                        self.recenter_after *= 2
                    else:
                        self.allow_increase_of_recentering_interval = False

                    self.next_recentering_iteration += self.recenter_after
                else:
                    max_diff = self.get_max_slope(spectrum)
                    improvement = (max_diff - self.initial_diff) / self.initial_diff
                    if improvement > 0 and improvement > params.optimization_improvement.value:
                        params.optimization_improvement.value = improvement

                    print('improvement %d' % (improvement * 100))

                    fitness = math.log(1 / max_diff)
                    #print('fitness', fitness)

                    self.fitness_arr.append(fitness)
                    self.opt.insert_fitness_value(fitness, self.last_parameters)

            self.request_new_parameters(use_initial_parameters=center_line_next_time)

    def exposed_stop(self, use_new_parameters):
        if use_new_parameters:
            optimized_parameters = convert_params(
                self.opt.request_results()[0], self.xmin, self.xmax
            )
            self.set_parameters(optimized_parameters)
        else:
            self.request_new_parameters(use_initial_parameters=True)

        self.parameters.optimization_running.value = False
        self.parameters.to_plot.remove_listener(self.react_to_new_spectrum)

    def set_parameters(self, new_params):
        params = self.parameters
        frequency, amplitude, phase = new_params
        #print('%.2f MHz, %.2f Vpp, %d deg' % (frequency / MHz, amplitude / Vpp, phase))
        self.control.pause_acquisition()
        params.modulation_frequency.value = frequency
        params.modulation_amplitude.value = amplitude
        params.demodulation_phase_a.value = phase
        self.control.exposed_write_data()
        self.control.continue_acquisition()
        self.last_parameters = new_params

    def get_max_slope(self, array):
        line_width = len(array) / FINAL_ZOOM_FACTOR

        min_line_width_factor = self.parameters.optimization_min_line_width.value / 100
        interesting_size = int(line_width * min_line_width_factor)

        slopes = []

        for shift in (0, -.1, -.2, -.3, -.4, -.5, .1, .2, .3, .4):
            shifted = np.roll(array, int(shift * interesting_size))

            # resampling assumes periodicity
            # --> if the ends don't match (e.g. doppler background) we have very
            # steep edges. Therefore, we connect the edges smoothly, then
            # we resample and crop again what we're interested in.
            to_add_before = int(abs(shifted[0]) / interesting_size) * interesting_size
            to_add_after = int(abs(shifted[-1]) / interesting_size) * interesting_size

            shifted = (
                list(np.linspace(0, shifted[0], to_add_before))
                + list(shifted)
                + list(np.linspace(shifted[-1], 0, to_add_after))
            )

            filtered = resample(shifted, int(len(shifted) / interesting_size))

            # now we remove again the fake data that was added before
            filtered = filtered[int(to_add_before / interesting_size):]
            if to_add_after > 0:
                filtered = filtered[:-int(to_add_after / interesting_size)]

            # and now we look only at the center
            line_center_r = int(len(filtered) / 2)
            range_around_center = int(2 * 1 / min_line_width_factor)
            filtered = filtered[
                line_center_r-range_around_center:line_center_r+range_around_center
            ]

            slopes.append(np.max(np.abs(np.gradient(filtered))))

        return np.max(slopes)
