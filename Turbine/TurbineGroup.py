from openmdao.api import ExplicitComponent
from input_params import max_n_turbines, turbine_rated_power
import numpy as np


class Turbine(ExplicitComponent):

    def __init__(self, number, n_cases):
        super(Turbine, self).__init__()
        self.number = number
        self.n_cases = n_cases

    def setup(self):
        self.add_input('n_turbines', val=0)
        for n in range(max_n_turbines):
            if n < self.number:
                self.add_input('U{}'.format(n), shape=self.n_cases)
        self.add_input('prev_turbine_ct', shape=(self.n_cases, max_n_turbines - 1))
        self.add_input('prev_turbine_p', shape=(self.n_cases, max_n_turbines - 1))
        self.add_output('ct', shape=(self.n_cases, max_n_turbines - 1))
        self.add_output('power', shape=(self.n_cases, max_n_turbines - 1))

        # Finite difference all partials.

    def compute(self, inputs, outputs):
        # print "2 Turbine"
        # for n in range(max_n_turbines):
        #     if n != self.number:
                # print inputs['U{}'.format(n)], "Input U{}".format(n)
        c_t_ans = np.array([])
        power_ans = np.array([])
        for case in range(self.n_cases):
            prev_turbine_p = inputs['prev_turbine_p'][case]
            prev_turbine_ct = inputs['prev_turbine_ct'][case]
            n_turbines = int(inputs['n_turbines'])
            c_t = np.array([])
            power = np.array([])
            for n in range(n_turbines):
                if n < self.number < n_turbines:
                    if n == self.number - 1:
                        print "called turbine model"
                        ct, p = self.turbine_model(inputs['U{}'.format(n)][case])
                    else:
                        ct = prev_turbine_ct[n]
                        p = prev_turbine_p[n]
                    c_t = np.append(c_t, [ct])
                    power = np.append(power, [p])
            lendif = max_n_turbines - len(c_t) - 1
            # print c_t
            c_t = np.concatenate((c_t, [0 for _ in range(lendif)]))
            power = np.concatenate((power, [0 for _ in range(lendif)]))
            c_t_ans = np.append(c_t_ans, c_t)
            power_ans = np.append(power_ans, power)
        c_t_ans = c_t_ans.reshape(self.n_cases, max_n_turbines - 1)
        power_ans = power_ans.reshape(self.n_cases, max_n_turbines - 1)
        # print c_t_ans
        outputs['ct'] = c_t_ans
        outputs['power'] = power_ans

    def turbine_model(self, u):
    	if u < 4.0:
            ct = 0.1
        elif u <= 25.0:
            ct = 7.3139922126945e-7 * u ** 6.0 - 6.68905596915255e-5 * u ** 5.0 + 2.3937885e-3 * u ** 4.0 - 0.0420283143 * u ** 3.0 + 0.3716111285 * u ** 2.0 - 1.5686969749 * u + 3.2991094727
        else:
            ct = 0.1


        if u < 4.0:
            power = 0.0
        elif u <= 10.0:
            power = (3.234808e-4 * u ** 7.0 - 0.0331940121 * u ** 6.0 + 1.3883148012 * u ** 5.0 - 30.3162345004 * u ** 4.0 + 367.6835557011 * u ** 3.0 - 2441.6860655008 * u ** 2.0 + 8345.6777042343 * u - 11352.9366182805) * 1000.0
        elif u <= 25.0:
            power = turbine_rated_power
        else:
            power = 0.0

        return ct, power
