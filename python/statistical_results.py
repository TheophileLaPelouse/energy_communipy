import json, os, pickle
import os.path as pos
import matplotlib.pyplot as plt
from matplotlib import rcParams
import numpy as np
import pandas as pd
from tqdm import tqdm
from time import time
import datetime as dt
from bisect import insort

import sys
sys.path.append("/Users/theophilemounier/Desktop/git/energy_communipy/python")
sys.path.append("/home/theophile/Desktop/git/energy_communipy/python")
import pyomo.environ as pyo
from pyomo.util.infeasible import find_infeasible_constraints, find_infeasible_bounds
from pyomo.opt import SolverFactory

from commu_opti.plotting.plot_functions import plot_3d, plot_hexagon_objective

from commu_opti.plotting.plot_functions import plot_power_curves    

from commu_opti.generate_device_infos import compute_results
from commu_opti.community.utils import gini, compare_indices


try:
    rcParams['font.family'] = 'Times New Roman'
except ValueError:
    print("Warning: 'Times New Roman' not found. Falling back to 'Times'.")
    rcParams['font.family'] = 'Times'

rcParams['font.size'] = 25

save_folder = pos.join(pos.dirname(__file__), "results", "stat_results")
if not pos.exists(save_folder) :
    os.makedirs(save_folder)
    
plot_folder = pos.join(pos.dirname(__file__), "results", "plot_results")
if not pos.exists(plot_folder) :
    os.makedirs(plot_folder)

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
n_iter_eps = 10
eps = [1000, 100, 10, 5, 1, 0.5, 0.1, 0.05, 0.01]
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

file_name = pos.join(save_folder, f"admm_vs_centralized_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json")
res = {
    "eps" : eps,
    "diffs" : diffs,
    "values" : values,}
with open(file_name, "w") as f :
    json.dump(res, f, indent=4)
    
#%%
file_name = pos.join(save_folder, "admm_vs_centralized_2026-08-20_02-02-57.json")
with open(file_name, "r") as f : 
    results = json.load(f)
    
eps, diffs, values = results["eps"], results["diffs"], results["values"]

eps_to_plot = [f"{e:.0e}" for e in eps]
# plt.plot(eps_to_plot, diffs, '+')
fig = plt.figure()
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
    
file_name = pos.join(save_folder, "simulation_time_2026-08-18_19-10-01.json")
with open(file_name, "r") as f : 
    results = json.load(f)

n_ranges, time_results = results["n_ranges"], results["time_results"]
n_ranges = [n[0] for n in n_ranges]

centralized_mean = [np.mean(time_results[k]["centralized"]) for k in range(len(n_ranges))]
centralized_std  = [np.std(time_results[k]["centralized"]) for k in range(len(n_ranges))]

admm_mean = [np.mean(time_results[k]["admm"]) for k in range(len(n_ranges))]
admm_std  = [np.std(time_results[k]["admm"]) for k in range(len(n_ranges))]

fig1 = plt.figure()
plt.errorbar(
    n_ranges,
    centralized_mean,
    yerr=centralized_std,
    fmt='o',
    capsize=5,
    label="Centralized"
)
plt.xlabel("Number of members in the community")
plt.ylabel("Average Simulation Time (s)")
plt.legend()

fig2 = plt.figure()
plt.errorbar(
    n_ranges,
    admm_mean,
    yerr=admm_std,
    fmt='o',
    capsize=5,
    label="ADMM",
    color="orange"
    
)
plt.xlabel("Number of members in the community")
plt.ylabel("Average Simulation Time (s)")
plt.legend()

plt.show()

save_path1 = pos.join(plot_folder, "time_centralized.pdf")
save_path2 = pos.join(plot_folder, "time_admm.pdf")
#fig1.savefig(save_path1)
#fig2.savefig(save_path2)

#%% gain repartition

method = ["centralized"]
n_iteration = 30
# gains_method = ["proportional", "equal"]
gains_method = ["proportional", "equal", "shapley", "nucleolus"]
compute_gains = True
n_range = [5, 10]
# n_range = [4, 5]
kwargs = {
    "n_range" : n_range,
    "n_iterations" : n_iteration,
    "list_method" : method,
    "compute_gains" : compute_gains,
    "gains_method" : gains_method, 
    # "return_commus" : True
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
file_name=pos.join(save_folder, "gain_repartition_2026-08-20_13-27-47.pickle")
with open(file_name, "rb") as f : 
    res = pickle.load(f)
    
results, gains_method = res["results"], res['gains_method']

# for meritocratic correlation
correlation_list = []
excess = {method : [] for method in gains_method}
nucleolus_compare = {method : 0 for method in gains_method}

Gini = {method : 0 for method in gains_method}

for name in results : 
    conso_tot = sum(results[name]['aggregated_powers']['P_cons'])
    exchange_tot = sum(results[name]['aggregated_powers']['P_exchange'])
    if exchange_tot == 0 : exchange_tot= 1
    comfort_tot = results[name]['aggregated_objs']['comfort']
    if comfort_tot ==0 : comfort_tot = 1
    invest_tot = results[name]['aggregated_objs']['price_invest']
    for key in results[name] :
        if key.startswith("members_") : 
            k = int(key.split("_")[-1])
            dico = {}
            dico['conso'] = sum(results[name][key]["P_cons"])/conso_tot
            dico['comfort'] = results[name][key]["comfort"]/comfort_tot
            dico["invest"] = results[name][key]["price_invest"]/invest_tot
            dico["exchange"] = sum(results[name][key]["P_exchange"])/exchange_tot
            for method in gains_method : 
                dico[method] = results[name]["gains"][method][k]
            correlation_list.append(dico)
            
    # n_coal = len(results[name]["coalitions"])
    ex = {method :[] for method in gains_method}
    for coal, val in results[name]["coalitions"].items() :
        for method in gains_method:
            sum_x = sum(results[name]["gains"][method][k] for k in coal)*results[name]["total_gains"]
            # print(method, sum_x, coal, val)
            insort(ex[method], (val- sum_x)) # Change to smart way if too slow, could be done in nlogn here n2
    for method in gains_method:
        excess[method].append(np.mean(ex[method][-5:-1]))
        
    for method in gains_method : 
        gains = list(results[name]["gains"][method].values())
        Gini[method] += gini(gains)
        
    for method in gains_method : 
        n_member = len(results[name]["gains"][method])
        x = [0 for k in range(n_member)]
        y = [0 for k in range(n_member)]
        for k, val in results[name]["gains"][method].items() :
            x[k] = val
            y[k] = results[name]["gains"]["nucleolus"][k]
        
        # print(name, method, compare_indices(x, y))
        nucleolus_compare[method] += compare_indices(x, y)
        
    
    
        
for method in gains_method :
    excess[method] = [np.mean(excess[method]), np.std(excess[method])]
    nucleolus_compare[method] /= len(results)
    Gini[method] /= len(results)
    

# correlation
indices_method = {}
correlation_array = np.zeros((len(correlation_list), len(gains_method)+4))
for i, dico in enumerate(correlation_list) :
    correlation_array[i, 0] = dico['conso']
    correlation_array[i, 1] = dico['comfort']
    correlation_array[i, 2] = dico['invest']
    correlation_array[i, 3] = dico["exchange"]
    for j, method in enumerate(gains_method) :
        indices_method[method] = j+4
        correlation_array[i, j+4] = dico[method]
        
# Meritocratic correlation = positive gain / comfort, positive gain / invest
comfort_correlation = {}
invest_correlation = {}
for method in gains_method :
    idx = indices_method[method]
    comfort_correlation[method] = np.corrcoef(correlation_array[:, 1], correlation_array[:, idx])[0, 1]
    invest_correlation[method] = np.corrcoef(correlation_array[:, 2], correlation_array[:, idx])[0, 1]
    meritocratic_correlation = (
        np.corrcoef(correlation_array[:, 1], correlation_array[:, idx])[0, 1] + 
        np.corrcoef(correlation_array[:, 2], correlation_array[:, idx])[0, 1] 
    ) / 2
    print(f"Meritocratic correlation for {method}: {meritocratic_correlation:.4f}")

#%% PLot

to_plot = {
    "values" : {"Excess score" : excess},
    "labels" : ['Proportional', "Equal", "Shapley", "Nucleolus"],
    "dimension" : 0,
    "title" : "",
    "colors" : ['lightblue']
    # "save_path" : os.path.join(folder_path, "gains_allocation_proportional.pdf")
}
save_path1 = pos.join(plot_folder, "excess_score.pdf")
fig1, ax1 = plot_hexagon_objective(**to_plot)
#fig1.savefig(save_path1)

to_plot = {
    "values" : {"Comfort correlation" : comfort_correlation},
    "labels" : ['Proportional', "Equal", "Shapley", "Nucleolus"],
    "dimension" : 0,
    "title" : "",
    "colors" : ["orange"]
    # "save_path" : os.path.join(folder_path, "gains_allocation_proportional.pdf")
}
save_path2 = pos.join(plot_folder, "comfort_correlation.pdf")
fig2, ax2 = plot_hexagon_objective(**to_plot)
#fig2.savefig(save_path2)

to_plot = {
    "values" : {"Investment correlation" : invest_correlation},
    "labels" : ['Proportional', "Equal", "Shapley", "Nucleolus"],
    "dimension" : 0,
    "title" : "",
    "colors" : ["green"]
    # "save_path" : os.path.join(folder_path, "gains_allocation_proportional.pdf")
}
save_path3 = pos.join(plot_folder, "invest_correlation.pdf")
fig3, ax3 = plot_hexagon_objective(**to_plot)
#fig3.savefig(save_path3)

to_plot = {
    "values" : {"Gini coefficient" : Gini},
    "labels" : ['Proportional', "Equal", "Shapley", "Nucleolus"],
    "dimension" : 0,
    "title" : "",
    # "colors" : ["green"]
    # "save_path" : os.path.join(folder_path, "gains_allocation_proportional.pdf")
}
save_path4 = pos.join(plot_folder, "gini.pdf")
fig4, ax4 = plot_hexagon_objective(**to_plot)
#fig4.savefig(save_path4)

#%% ADMM vs centralized correlation 

methods = ["centralized", "admm"]
n_iter = 40
n_range=[5, 20]

kwargs = {
    "n_range" : n_range,
    "n_iterations" : n_iter,
    "list_mehtod" : methods,
}

t0 = time()
results = compute_results(**kwargs)
delta = time() - t0
#%%
admm_vs_centr = {"admm" : {"members_objs" : [], "members_socio" : []}, "centralized" : {"members_objs" : [], "members_socio" : []}}
for name in results :
    to_change = "admm" if "admm" in results[name] else "centralized" 
    for key, val in results[name].items() : 
        if key.startswith('members') : 
            if val['Objective'] == 0 : continue
            objs = [val['price']/val['Objective'], val["enviro"]/val['Objective'], val["auto"]/val['Objective'], val['comfort']/val['Objective']]
            socio = val['socio'][:]
            admm_vs_centr[to_change]["members_objs"].append(objs)
            admm_vs_centr[to_change]["members_socio"].append(socio)
            

admm_vs_centr["admm"]["members_objs"] = np.array(admm_vs_centr["admm"]["members_objs"])
admm_vs_centr["centralized"]["members_objs"] = np.array(admm_vs_centr["centralized"]["members_objs"])
admm_vs_centr["admm"]["members_socio"] = np.array(admm_vs_centr["admm"]["members_socio"])
admm_vs_centr["centralized"]["members_socio"] = np.array(admm_vs_centr["centralized"]["members_socio"])
#%%
file_name = pos.join(save_folder, f"ADMM_centralized_correlation_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pickle")
with open(file_name, "wb") as f :
    pickle.dump({"n_range" : kwargs.get("n_range"), 
                 "n_iterations" : kwargs.get("n_iterations"),
                 "list_method" : kwargs.get("list_method"),
                 "results" : results,
                 "admm_vs_centr" : admm_vs_centr}, 
                f)
    
#%% Analysis of ADMM vs centralized correlation
file_name = pos.join(save_folder, "ADMM_centralized_correlation_2026-08-21_21-39-35.pickle")
with open(file_name, "rb") as f :
    results = pickle.load(f)
    
admm_vs_centr = results["admm_vs_centr"]
#%%

corr_admm = {k : np.corrcoef(admm_vs_centr["admm"]["members_objs"][:, k], admm_vs_centr["admm"]["members_socio"][:, k])[0, 1] for k in range(4)}
corr_centr = {k:np.corrcoef(admm_vs_centr["centralized"]["members_objs"][:, k], admm_vs_centr["centralized"]["members_socio"][:, k])[0, 1] for k in range(4)}
# print(f"Correlation between members' objectives and sociological profiles for ADMM: {corr_admm}")
# print(f"Correlation between members' objectives and sociological profiles for CENTRALIZED: {corr_centr}")

to_plot = {
    "values" : {"ADMM" : corr_admm, 
                "Centralized" : corr_centr},
    "labels" : ['Economy', "Environment", "Self-consumption", "Comfort penalties"],
    "dimension" : 0,
    "title" : "",
    "colors" : ["green"]
    # "save_path" : os.path.join(folder_path, "gains_allocation_proportional.pdf")
}
save_path3 = pos.join(plot_folder, "invest_correlation.pdf")
fig3, ax3 = plot_hexagon_objective(**to_plot)

#%% Plot one community

method = ["centralized"]
n_iteration = 1
compute_gains = True
n_range = [20, 21]
kwargs = {
    "n_range" : n_range,
    "n_iterations" : n_iteration,
    "list_method" : method,
}

results = compute_results(**kwargs)
#%%

powers = results["community_centralized_0"]['aggregated_powers']
to_plot = {
    "powers" : {
        "Puissance échangé avec le réseau" : powers['P_grid'],
        "Puissance des batteries" : powers['P_bat'],
        "Puissance consommée" : powers['P_cons'], 
        "Puissance échangée dans la communauté" : powers['P_exchange'],
        "Puissance produite" : powers['P_prod'],
    },
    "title" : "", 
    "xlabel" : "Temps (h)", 
    "ylabel" : "Puissance (W)"
}

fig, ax = plot_power_curves(**to_plot)
#fig.savefig(pos.join(plot_folder, "illustration_centralized.pdf"))

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