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
from pyomo.util.infeasible import find_infeasible_constraints, find_infeasible_bounds
from pyomo.opt import SolverFactory

from commu_opti.data.generate_data import generate_n_profile, create_random_agent
from commu_opti.commu_builder import define_members, define_community
from commu_opti.generate_device_infos import generate_member_data_random, generate_devices_data, generate_devices_profile, separate_horizon_futur
from commu_opti.data.generate_data_V2 import get_weather_data, list_locations, get_price_data
from commu_opti.data.ev_profile import EV_profile
from commu_opti.opti.rolling_horizon import rolling_horizon_optimization

# First choose a location

# choose a timeframe

# choose penetration rate of PV, EV and battery

# EV_rate = 0.2
# PV_rate = 0.3
# Battery_rate = 0.1

EV_rate = 1
PV_rate = 1
Battery_rate = 1

# generate agents data

possible_socio = []
for k in range(8) : 
    for j in range(8-k) : 
        for i in range(8-j-k) : 
            possible_socio.append([k, j, i, 8-k-j-i])
            

n = 5
nb_of_days = 2

day_number = np.random.randint(1, 365)
date = dt.datetime(2025, 1, 1) + dt.timedelta(days=day_number)

lat, lon = list_locations[np.random.randint(0, len(list_locations)-1)]
deltat = 1

weather_forecast, irradiance_forecast = get_weather_data(date, date + dt.timedelta(days=nb_of_days), lat=lat, lon=lon, forecast=True, deltat=deltat)
weather_history, irradiance_history = get_weather_data(date, date + dt.timedelta(days=nb_of_days), lat=lat, lon=lon, forecast=False, deltat=deltat)

weather_forecast, irradiance_forecast = list(weather_forecast), list(irradiance_forecast)
weather_history, irradiance_history = list(weather_history), list(irradiance_history)

horizon = 24

EV_allocation = {
    "E_range" : [10, 70], # kwh
    "P_max" : [3.6, 7.4, 11, 22], # kW
    "proba_minus" :0.5
}

PV_allocation = {
    "portion_surf" : 0.7, 
    "eff" : [0.2, 0.05] # average, variance
}

bat_allocation = {
    "E_range" : [5, 40], # kwh
    "C_range" : [0.25, 1], 
    "charge_eff" : [0.93, 0.02], # average, variance
    "dcharge_eff" : [0.93, 0.02], # average
}
params = []
for k in range(n) : 
    rd_EV = np.random.rand()
    rd_PV = np.random.rand()
    rd_bat = np.random.rand()   
    
    nb_people, deltat, equipments, build, weather = generate_devices_data(date=date, nb_of_days=nb_of_days, location=(lat, lon), deltat=deltat)
    
    param, final_result = generate_devices_profile(nb_people, deltat, equipments, build, weather, total_time=(horizon*nb_of_days)//deltat)
    param, devices_futur = separate_horizon_futur(param, horizon)
    presence_profile = final_result['args']['presence_profile']
    building = final_result['args']['building']
    weather = final_result['args']['weather']
    
    flag_pv = False
    if rd_EV < EV_rate : 
        allocated = {}
        E = EV_allocation["E_range"][0] + (EV_allocation["E_range"][1] - EV_allocation["E_range"][0]) * np.random.rand()
        P_max = EV_allocation["P_max"][np.random.randint(0, len(EV_allocation["P_max"]))]
        P_min = -P_max*(np.random.rand()>EV_allocation["proba_minus"])
        allocated = {"E": E, "power_pos": P_max, "power_neg": P_min, "name" : "EV"}
        for k in range(3) : 
            try : 
                param["devices"]["EV"] = EV_profile(allocated, presence_profile, deltat, bypass=True)
                break
            except : 
                continue
        # flag_pv=True
        
    if rd_bat < Battery_rate : 
        E_max = bat_allocation["E_range"][0] + (bat_allocation["E_range"][1] - bat_allocation["E_range"][0]) * np.random.rand()
        C_max = bat_allocation["C_range"][0] + (bat_allocation["C_range"][1] - bat_allocation["C_range"][0]) * np.random.rand()
        P_max = C_max * E_max
        E_range = [0.1*E_max, 0.9*E_max]
        P_range = [-P_max, P_max]
        charge_eff = np.random.normal(bat_allocation["charge_eff"][0], bat_allocation["charge_eff"][1])
        dcharge_eff = np.random.normal(bat_allocation["dcharge_eff"][0], bat_allocation["dcharge_eff"][1])
        param["devices"]["battery"] = {
            "parameters" : {"E_range" : E_range, "p_range" : P_range, "charge_eff" : charge_eff, "dcharge_eff" : dcharge_eff, "name" : "battery"}, 
            "type" : "battery"
            }

        flag_pv=True
        
    if rd_PV < PV_rate or flag_pv : 
        irradiance = weather["forecast"]["irradiance"][:horizon]
        eff = np.random.normal(PV_allocation["eff"][0], PV_allocation["eff"][1])
        surface = PV_allocation["portion_surf"] * building["surface"] if PV_allocation["portion_surf"] is not None else None
        param['devices']['PV'] = {
            "parameters" : {"irradiance_profile":irradiance, "surface":surface, 'eff' : eff, "name" : "PV"}, 
            "type" : "PV"
            }
    
    param['parameters'] = {}
    param["parameters"]["socio"] = possible_socio[np.random.randint(0, len(possible_socio)-1)]
    param["parameters"]["calc_ref"] = False
    param["parameters"]["id_"] = k 
    param["parameters"]["method"] = "admm"
    param["parameters"]["debug_ref"] = True
    param["parameters"]["building"] = building
    param["parameters"]["nb_people"] = final_result['args']['nb_people']
    params.append(param)


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
        # "debug_ref" : True,
    }

prices = get_price_data(date, date + dt.timedelta(days=nb_of_days))

price_options = {
    "eco" : {
        "cost_grid_buy" : prices[:horizon], # €/wh
        "cost_grid_sell" : -prices[:horizon]/4,
        "cost_ex" : 0, 
        "cost_PV" : 800, # € per m2
        # "cost_PV" : 0, # per m2
        "PV_min" : 0,
        "cost_bat" : 0.5, # € per wh
        # "cost_bat" : 0, # per kwh
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

# Iterate optimization of the community over several hours over time horizon.



kwargs = {
    "total_time" : horizon*nb_of_days,
    "horizon" : horizon,
    "deltat" : 1,
    "date" : date,
    "debug" : True,
    "until" : 10
    }

with_rolling, without_rolling, debug = rolling_horizon_optimization(params, param_commu, price_options, **kwargs)

co = debug['community']
d = co.members[0].devices[0]
#%%

co.debug_model()

# find_infeasible_constraints(co.mod)

#%% Plotting 

# Plot comparaison between weather and irradiance forecast and history
# plt.figure()
# plt.subplot(2, 1, 1)
# plt.plot(weather_forecast[:n_total_time], label="forecast")
# plt.plot(weather_history[:n_total_time], label="history")
# plt.title("Temperature forecast vs history")
# plt.xlabel("Time (h)")
# plt.ylabel("Temperature (°C)")
# plt.legend()
# plt.subplot(2, 1, 2)
# plt.plot(irradiance_forecast[:n_total_time], label="forecast")
# plt.plot(irradiance_history[:n_total_time], label="history")
# plt.title("Irradiance forecast vs history")
# plt.xlabel("Time (h)")
# plt.ylabel("Irradiance (W/m2)") 
# plt.legend()

# Plot power of the community over time with comparison between forecast and rolling horizon optimization


        