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


#%% Test rolling horizon for white goods

n = 1
nb_of_days = 3
horizon = 24
total_time = nb_of_days * horizon

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

irradiance_profile = [20 if 5 <=k < 10 or 25 <= k < 30 else 0 for k in range(total_time)]
param['devices']['PV'] = {
            "parameters" : {"irradiance_profile":irradiance_profile, "surface":1, 'eff' : 1, "name" : "PV"}, 
            "type" : "PV"
            }

param, devices_futur = separate_horizon_futur(param, horizon)


param["parameters"]["socio"] = [1, 1, 1, 1]
param["parameters"]["calc_ref"] = False
param["parameters"]["id_"] = 0
param["parameters"]["profile_method"] = None
param["parameters"]["method"] = "admm"
param["parameters"]["time_window"] = [date, date + dt.timedelta(days=nb_of_days)]
param["parameters"]["horizon"] = horizon
param["parameters"]["devices_futur"] = devices_futur

members = define_members([param])

param_commu = {
        "method" : "admm",
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

prices = get_price_data(date, date + dt.timedelta(days=nb_of_days))

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
# for t in range(1) :
    community.optimize_admm("gurobi", **community.kwargs)
    if t == 0 : 
        community.aggregate_distributed_information()
        without_rolling = community.results.copy()
    print("Optimization finished !", t)
    
    i = 0
    d = community.members[0].devices[0]
    while i < 24 and pyo.value(d.mod.bin_t0[0, i]) != 1:
        i += 1
    print("bin_t0", i, [pyo.value(d.mod.bin_t0[0, i]) for i in range(24)])
    print(pyo.value(d.mod.Pcons[0]))
    print(pyo.value(d.mod.starting_time_plus[0]), pyo.value(d.mod.starting_time_minus[0]))
    print(d.mod.used_time.extract_values())
    
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
