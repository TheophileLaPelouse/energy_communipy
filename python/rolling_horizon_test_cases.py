import json, os
import matplotlib.pyplot as plt
from matplotlib import rcParams
import numpy as np
import pandas as pd
from tqdm import tqdm
from time import time
import datetime as dt

import sys
sys.path.append("/Users/theophilemounier/Desktop/git/projet_g3/python")
sys.path.append("/home/theophile/Desktop/git/projet_g3/python")
import pyomo.environ as pyo
from pyomo.opt import SolverFactory

from commu_opti.data.generate_data import generate_n_profile, create_random_agent
from commu_opti.commu_builder import define_members, define_community
from commu_opti.generate_device_infos import generate_member_data_random, generate_devices_data, generate_devices_profile, separate_horizon_futur
from commu_opti.data.generate_data_V2 import get_weather_data, list_locations, get_price_data
from commu_opti.data.ev_profile import EV_profile
from commu_opti.community.utils import calc_eco


#%% Test rolling horizon for white goods

n = 1
nb_of_days = 3
horizon = 24
total_time = nb_of_days * horizon
method = "admm"
# method = "centralized"

param = {"devices" : {}, "parameters" : {}}

date = dt.datetime(2025, 1, 1)

wash_mach = {
    "parameters": {
    "cycle_length": [4, 4],
    "power_needed": [20.0, 20],
    "start_pref": [10, 35],
    "time_range": [[-5, 5], [-5, 5]],
    }, 
    "type": "white_good",
    "name": "washing_machine"
}
param['devices']['washing_machine'] = wash_mach
param["device_options"] = {"total_time" : total_time, "deltat" : 1}

irradiance_profile = [20 if 5 <=k < 10 else 0 for k in range(total_time)]
# irradiance_profile = [0 for k in range(total_time)]

param['devices']['PV'] = {
            "parameters" : {"irradiance_profile":irradiance_profile, "surface":1, 'eff' : 1, "name" : "PV"}, 
            "type" : "PV"
            }

param, devices_futur = separate_horizon_futur(param, horizon)


param["parameters"]["socio"] = [1, 0, 0, 1]
param["parameters"]["calc_ref"] = False
param["parameters"]["id_"] = 0
param["parameters"]["profile_method"] = None
param["parameters"]["method"] = method
param["parameters"]["time_window"] = [date, date + dt.timedelta(days=nb_of_days)]
param["parameters"]["horizon"] = horizon
param["parameters"]["devices_futur"] = devices_futur

members = define_members([param])

param_commu = {
        "method" : method,
        "deltat" : 1,
        "total_time" : horizon,
        "calc_ref" : True, 
        "max_iter" : 50,
        "rho" : 0.001/n, 
        "power_max_random" : 0,
        "parallel" : False,
        "eps_r" : 1e-2, 
        "eps_s" : 1e-2,
    }

# prices = get_price_data(date, date + dt.timedelta(days=nb_of_days))
prices = np.array([10 for k in range(total_time - horizon)])

price_options = {
    "eco" : {
        "cost_grid_buy" : prices[:horizon], # €/wh
        "cost_grid_sell" : -prices[:horizon]/4,
        "cost_ex" : 0, 
        "cost_PV" : 0, # per m2
        "PV_min" : 0,
        "cost_bat" : 0, # per kwh
        "bat_min" : 0,
    },
    "enviro" : {
        "carbone_grid" : 0.5,
        "carbone_commu" : 0.1
    },
    "auto" : {
        "coef_auto" : 1
    },
    "pena" : {
        "coef_pena" : 1
    }
}
new_weather = [20 for k in range(horizon)]

community = define_community(members, **param_commu, **price_options)

i_horizon = horizon
for t in range(total_time - horizon) :
# for t in range(6) :
    if community.kwargs["method"] == "admm" : 
        community.optimize_admm("gurobi", **community.kwargs)
    else : 
        community.optimize("gurobi")
    if t == 0 : 
        community.aggregate_distributed_information()
        without_rolling = community.results.copy()
    print("Optimization finished !", t)
    
    i = 0
    d = community.members[0].devices[0]
    pv = community.members[0].devices[1]
    while i < 24 and pyo.value(d.mod.bin_t0[0, i])*d.mod.available_time_set[0, i].value != 1:
        i += 1
        
    
    
    print("bin_t0", i, [pyo.value(d.mod.bin_t0[0, i]) for i in range(24)])
    print("P_cons", [pyo.value(d.mod.Pcons[k]) for k in range(24)])
    print("irradiance", [pyo.value(pv.mod.Pcons[k]) for k in range(24)])
    print("price", pyo.value(community.members[0].price), pyo.value(community.members[0].mod_member.obj_expr))
    # print("available_time", [d.mod.available_time_set[0, t].value for t in range(24)])
    # print("used_tim", d.mod.used_time.extract_values())
    irradiance_t = irradiance_profile[t]
    new_irradiance = [irradiance_t] + irradiance_profile[t+1:t+horizon]
    for i in community.current_members_id : 
        m = community.members[i]
        m.keep_in_memory()
        m.rolling_horizon_update(new_weather, new_irradiance)

for i in community.current_members_id : 
    m = community.members[i]
    m.objectif_from_memory()
community.aggregate_distributed_information(from_memory=True)
with_rolling = community.results.copy()
#%% plots
to_plot_rolling = {
    "powers" : {
        "with_rolling P_cons" : with_rolling['aggregated_powers']["P_cons"],
        "Irradiance" : irradiance_profile[:total_time-horizon]
    },
    "total_time" : 48, 
}

to_plot = {
    "powers" :  {
        "standard P_cons" : without_rolling['aggregated_powers']["P_cons"],
        "Irradiance" : irradiance_profile[:horizon]
        }
    }

community.plot_power_curves(**to_plot)
community.plot_power_curves(**to_plot_rolling)

#%% Autre 

Pconsbis = []
for t in range(24) : 
    s = 0
    for t_set in d.mod.max_set : 
        for t2 in d.mod.time_total_set : 
            new_val =  pyo.value(d.mod.bin_t0[t_set, t2])*d.mod.p_range_wg[t_set, (t-t2)%48].value#%*d.mod.available_time_set[t_set, t2].value
            if new_val > 0 :
                print(f"t_set {t_set}, t2 {t2}, bin_t0 {pyo.value(d.mod.bin_t0[t_set, t2])}, p_range_wg {d.mod.p_range_wg[t_set, max(0, t-t2)].value}, available_time_set {d.mod.available_time_set[t_set, t].value}, new_val {new_val}")
            s += new_val
    Pconsbis.append(s)
