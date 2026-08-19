import json, os, pickle
import os.path as pos
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


save_folder = pos.join(pos.dirname(__file__), "results", "stat_results")
if not pos.exists(save_folder) :
    os.makedirs(save_folder)

#%% test d'erreur

method = ["centralized"]

n_iteration = 100
kwargs = {
    "n_range" : [5, 10],
    "n_iterations" : n_iteration,
    "list_method" : method,
}

t0 = time()
results = compute_results(**kwargs)
delta = time() - t0


#%% ADMM vs centralized

method = ["centralized", "admm"]
n_iter_eps = 5
eps = [1000, 100, 10, 5, 1, 0.5, 0.1, 0.05, 0.01, 0.005, 0.001]
# eps = [1, 0.5, 0.1, 0.05, 0.01, 0.005, 0.001, 0.0001, 0.00001]
# eps = eps[:1]
param_commus = [
    {
        # "solving_method" : method,
        "deltat" : 1,
        "total_time" : 24,
        "calc_ref" : True, 
        "rho" : 1e-9,
        # "power_max_random" : 10000,
        "eps_r" : e,
        "eps_s" : e,
        "max_iter" : 300, 
        # "mu" : 10, 
        # "tau_incr" : 1.5, 
        # "tau_decr" : 1.5, 
        # "wait_iter" : 0,
        "name" : f"{e}_{k}"
    }
    for e in eps for k in range(n_iter_eps)
]

n_iteration = len(param_commus)
kwargs = {
    "n_range" : [5, 20],
    # "n_range" : [1, 2],
    "n_iterations" : n_iteration,
    "list_param_commu" : param_commus
}

t0 = time()
results = compute_results(**kwargs)
delta = time() - t0

file_name = pos.join(save_folder, f"admm_vs_centralized_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json")
res = {
    "eps" : eps,
    "diffs" : diffs,
    "values" : values,}
with open(file_name, "w") as f :
    json.dump(res, f, indent=4)
#%% plot results ADMM vs centralized

# Plot difference in obective function values between ADMM and centralized methods for different epsilon values.

diffs = [0 for k in range(len(eps))]
values = {e : {"centralized" : [None for k in range(n_iter_eps)], "admm" : [None for k in range(n_iter_eps)]} for e in eps}
for name in results : 
    e, k, method = name.split("_")
    e = float(e)
    if results[name].get('solving_status', "optimal") == "optimal" : 
        values[e][method][int(k)] = results[name]['aggregated_objs']['Objective']
        
for k in range(len(eps)) :
    e = eps[k]
    vals = values[e]
    diffs[k] = sum(
        [abs(vals['admm'][i] - vals['centralized'][i])/abs(vals['centralized'][i]) for i in range(n_iter_eps) 
        if vals['admm'][i] is not None and vals['centralized'][i] is not None]
        ) / n_iter_eps



eps_to_plot = [f"{e:.0e}" for e in eps]
# plt.plot(eps_to_plot, diffs, '+')
plt.semilogy(eps_to_plot, diffs, '+')
plt.xlabel("Epsilon")
plt.ylabel("Average difference in objective function values (ADMM - Centralized)")



#%% Simulation time

method = ["centralized", "admm"]
n_ranges = [[1,2], [3, 4], [5, 6], [7, 8], [9, 10], [11, 12], [13, 14], [15, 16], [17, 18], [19, 20]]
# n_ranges = n_ranges[:1]
n_iterations = 10
time_results = []
for k in range(len(n_ranges)) :
    kwargs = {
        "n_range" : n_ranges[k],
        "n_iterations" : n_iterations,
        "list_method" : method,
    }
    results = compute_results(**kwargs)
    times = {"centralized" : [], "admm" : []}
    for name in results : 
        if results[name].get("centralized") : 
            times["centralized"].append(results[name]["centralized"]["Times"]['self_optimize'])
        if results[name].get("admm") :
            times["admm"].append(results[name]["admm"]["Times"]['total'])
    time_results.append(times)
    print(f"Simulation time for n_range {n_ranges[k]}: {delta:.2f} seconds")
    
file_name = pos.join(save_folder, f"simulation_time_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json")
res = {
    "n_ranges" : n_ranges,
    "time_results" : time_results,}
with open(file_name, "w") as f :
    json.dump(res, f, indent=4)

#%% plot results time
    
plt.plot([np.mean(time_results[k]["centralized"]) for k in range(len(n_ranges))], label="Centralized")
plt.plot([np.mean(time_results[k]["admm"]) for k in range(len(n_ranges))], label="ADMM")
plt.xlabel("Number of members in the community")
plt.ylabel("Average Simulation Time (s)")
plt.legend()

#%% gain repartition

method = ["centralized"]
n_iteration = 20
gains_method = ["proportional", "equal", "shapley", "nucleolus"]
compute_gains = True
n_range = [5, 10]
# n_range = [1, 2]
kwargs = {
    "n_range" : n_range,
    "n_iterations" : n_iteration,
    "list_method" : method,
    "compute_gains" : compute_gains,
    "gains_method" : gains_method
}
t0 =time()
results = compute_results(**kwargs)
print(time()-t0)
#%%
file_name = pos.join(save_folder, f"gain_repartition_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pickle")
res = {
    "n_range" : n_range,
    "n_iterations" : n_iteration,
    "list_method" : method,
    "compute_gains" : compute_gains,
    "gains_method" : gains_method,
    "results" : results}
with open(file_name, "wb") as f :
    pickle.dump(res, f)
    
#%% Analysis



# for meritocratic correlation
correlation_list = []
excess = {method : [] for method in gains_method}

for name in results : 
    for key in results[name] :
        if key.startswith("members_") : 
            k = int(key.split("_")[-1])
            dico = {}
            dico['conso'] = sum(results[name][key]["P_cons"])
            dico['comfort'] = results[name][key]["comfort"]
            dico["invest"] = results[name][key]["price_invest"]
            for method in gains_method : 
                dico[method] = results[name]["gains"][method][k]
            correlation_list.append(dico)
            
    
    ex = {method : 0 for method in gains_method}
    for coal, val in results[name]["coalitions"].items() :
        for method in gains_method:
            ex[method] += val - sum(results[name]["gains"][method][k] for k in coal)
    for method in gains_method:
        excess[method].append(ex[method])
        
for method in gains_method :
    excess[method] = [np.mean(excess[method]), np.std(excess[method])]
    

# correlation

# correlation_array = np.array([correlation_list[]])

#%% test autre

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