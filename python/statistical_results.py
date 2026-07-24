import json, os
import matplotlib.pyplot as plt
from matplotlib import rcParams
import numpy as np
import pandas as pd
from tqdm import tqdm
from time import time
import datetime as dt

import sys
sys.path.append("/Users/theophilemounier/Desktop/git/energy_communipy/python")
sys.path.append("/home/theophile/Desktop/git/energy_communipy/python")
import pyomo.environ as pyo
from pyomo.util.infeasible import find_infeasible_constraints, find_infeasible_bounds
from pyomo.opt import SolverFactory


from commu_opti.plotting.plot_functions import plot_power_curves    

from commu_opti.generate_device_infos import compute_results

#%% test d'erreur

method = ["centralized"]

n_iteration = 100
kwargs = {
    "n_range" : [5, 20],
    "n_iterations" : n_iteration,
    "list_method" : method,
}

t0 = time()
results = compute_results(**kwargs)
delta = time() - t0


#%% ADMM vs centralized

method = ["centralized", "admm"]
eps = [1, 0.5, 0.1, 0.05, 0.01, 0.005, 0.001, 0.0001, 0.00001]
eps = eps[:2]
param_commus = [
    {
        # "solving_method" : method,
        "deltat" : 1,
        "total_time" : 24,
        "calc_ref" : True, 
        "rho" : 1e-9,
        "power_max_random" : 10000,
        "eps_r" : e,
        "eps_s" : e,
        "max_iter" : 300, 
        "mu" : 10, 
        "tau_incr" : 1.5, 
        "tau_decr" : 1.5, 
        "wait_iter" : 0,
    }
    for e in eps for k in range(5)
]

n_iteration = len(param_commus)
kwargs = {
    "n_range" : [10, 11],
    "n_iterations" : n_iteration,
    "list_param_commu" : param_commus
}

t0 = time()
results = compute_results(**kwargs)
delta = time() - t0


#%% 

method = ["centralized", "admm"]
eps = [1, 0.5, 0.1, 0.05, 0.01, 0.005, 0.001, 0.0001, 0.00001]
eps = eps[:2]
param_commus = [
    {
        # "solving_method" : method,
        "deltat" : 1,
        "total_time" : 24,
        "calc_ref" : True, 
        "rho" : 1e-9,
        "power_max_random" : 10000,
        "eps_r" : e,
        "eps_s" : e,
        "max_iter" : 500, 
        # "mu" : 10, 
        # "tau_incr" : 1.5, 
        # "tau_decr" : 1.5, 
        # "wait_iter" : 0,
    }
    for e in eps for k in range(5)
]

n_iteration = len(param_commus)
kwargs = {
    "n_range" : [10, 11],
    "n_iterations" : n_iteration,
    "list_param_commu" : param_commus
}

t0 = time()
results = compute_results(**kwargs)
delta2 = time() - t0