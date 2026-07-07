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
from commu_opti.plotting.plot_functions import plot_power_curves

# First choose a location

# choose a timeframe

# choose penetration rate of PV, EV and battery

# EV_rate = 0.2
# PV_rate = 0.3
# Battery_rate = 0.1

EV_rate = 0
PV_rate = 0.2
Battery_rate = 0.2

# generate agents data

possible_socio = []
for k in range(8) : 
    for j in range(8-k) : 
        for i in range(8-j-k) : 
            # possible_socio.append([k/8, j/8, i/8, (8-k-j-i)/8])
            possible_socio.append([0, 1, 1, 1])
            

n = 5
nb_of_days = 2
method="centralized"
# method="admm"

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
n_PV = 0
for k in range(n) : 
    rd_EV = np.random.rand()
    rd_PV = np.random.rand()
    rd_bat = np.random.rand()   
    
    nb_people, deltat, equipments, build, weather = generate_devices_data(date=date, nb_of_days=nb_of_days, location=(lat, lon), deltat=deltat)
    
    param, final_result = generate_devices_profile(nb_people, deltat, equipments, build, weather, total_time=(horizon*nb_of_days)//deltat, one_empty_day=True)
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
        param["devices"]["EV"] = EV_profile(allocated, presence_profile, deltat, bypass=True)
        # for k in range(3) : 
        #     try : 
        #         param["devices"]["EV"] = EV_profile(allocated, presence_profile, deltat, bypass=True)
        #         break
        #     except : 
        #         continue
        # if k == 2 : 
        #     print("PAS D'EV")
        # flag_pv=True
        
    if rd_bat < Battery_rate : 
        E_max = bat_allocation["E_range"][0] + (bat_allocation["E_range"][1] - bat_allocation["E_range"][0]) * np.random.rand()
        C_max = bat_allocation["C_range"][0] + (bat_allocation["C_range"][1] - bat_allocation["C_range"][0]) * np.random.rand()
        P_max = C_max * E_max
        E_range = [0.1*E_max*1000, 0.9*E_max*1000]
        P_range = [-P_max*1000, P_max*1000]
        charge_eff = np.random.normal(bat_allocation["charge_eff"][0], bat_allocation["charge_eff"][1])
        dcharge_eff = np.random.normal(bat_allocation["dcharge_eff"][0], bat_allocation["dcharge_eff"][1])
        param["devices"]["battery"] = {
            "parameters" : {"E_range" : E_range, "p_range" : P_range, "charge_eff" : charge_eff, "dcharge_eff" : dcharge_eff, "name" : "battery"}, 
            "type" : "battery"
            }

        # flag_pv=True
        
    if rd_PV < PV_rate or flag_pv : 
        n_PV += 1
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
    param["parameters"]["method"] = method
    param["parameters"]["debug_ref"] = True
    param["parameters"]["building"] = building
    param["parameters"]["nb_people"] = final_result['args']['nb_people']
    param["parameters"]["presence_profile"] = presence_profile
    params.append(param)

print("Nombre de panneaux solaire", n_PV)

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
        # "debug_ref" : True,
        # "debug_admm" : True,
    }

prices = get_price_data(date, date + dt.timedelta(days=nb_of_days))[:-1]/10e6
prices[24:] = prices[:24]

price_options = {
    "eco" : {
        "cost_grid_buy" : prices[:], # €/wh
        "cost_grid_sell" : -prices[:]*((prices[:]>0)/4 + (prices[:]<=0)*4), # €/wh
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
    }, 
    "confort" : {
        "coef_p" : 10e-3, 
        "coef_t" : 1, 
        "coef_c" : 10e-3,
    },
}

# Iterate optimization of the community over several hours over time horizon.

#%%

socio = [1, 1, 1, 1]
bat_exchange = False

kwargs = {
    "total_time" : horizon*nb_of_days,
    "horizon" : horizon,
    "deltat" : 1,
    "date" : date,
    "debug" : True,
    "until" : 1,
    "irradiance_history" : irradiance_history[:24] + irradiance_history[:25], 
    "weather_history" : weather_history[:24] + weather_history[:25],
    # "irradiance_forecast" : irradiance_forecast,
    # "weather_forecast" : weather_forecast,
    "irradiance_forecast" : irradiance_history[:24] + irradiance_history[:25],
    "weather_forecast" : weather_history[:24] + weather_history[:25],
    # "skip_params" : True
    }

for param in params : 
    param['parameters']['method'] = 'centralized'
    param['parameters']['socio'] = socio
    param['parameters']['bat_exchange'] = bat_exchange
param_commu['method'] = 'centralized'

# param_commu["ref_lp"] = True
with_rolling, without_rolling, debug = rolling_horizon_optimization(params, param_commu, price_options, **kwargs)

co = debug['community']
d = co.members[0].devices[0]



#%% Plotting 

n_compare = horizon*(nb_of_days-1)

# Plot comparaison between weather and irradiance forecast and history
# plt.figure()
# plt.subplot(2, 1, 1)
# plt.plot(weather_forecast[:n_compare], label="forecast")
# plt.plot(weather_history[:n_compare], label="history")
# plt.title("Temperature forecast vs history")
# plt.xlabel("Time (h)")
# plt.ylabel("Temperature (°C)")
# plt.legend()
# plt.subplot(2, 1, 2)
# plt.plot(irradiance_forecast[:n_compare], label="forecast")
# plt.plot(irradiance_history[:n_compare], label="history")
# plt.title("Irradiance forecast vs history")
# plt.xlabel("Time (h)")
# plt.ylabel("Irradiance (W/m2)") 
# plt.legend()

# Plot power of the community over time with comparison between forecast and rolling horizon optimization

to_plot_rolling = {
    "powers" : {
        "P_cons" : with_rolling['aggregated_powers']["P_cons"],
        "P_bat" : with_rolling['aggregated_powers']["P_bat"],
        "P_prod" : with_rolling['aggregated_powers']["P_prod"],
        "P_exchange" : with_rolling['aggregated_powers']["P_exchange"],
        "P_grid" : with_rolling['aggregated_powers']["P_grid"], 
        "Price" : prices[:horizon]*100*1000,
        "irradiance" : irradiance_history[:horizon]
    },
    "title" : "Community power profile with rolling horizon optimization"
}

to_plot_without_rolling = {
    "powers" : {
        "P_cons" : without_rolling['aggregated_powers']["P_cons"],
        "P_bat" : without_rolling['aggregated_powers']["P_bat"],
        "P_prod" : without_rolling['aggregated_powers']["P_prod"],
        "P_exchange" : without_rolling['aggregated_powers']["P_exchange"],
        "P_grid" : without_rolling['aggregated_powers']["P_grid"], 
        "Price" : prices[:horizon]*100*1000,
        "irradiance" : [val*10 for val in irradiance_history[:horizon]]
    },
    "title" : "Community power profile without rolling horizon optimization"
}


# plot_power_curves(**to_plot_rolling)
plot_power_curves(**to_plot_without_rolling)

# print("Objectif with rolling horizon : ", with_rolling['aggregated_objs']['Objective'], "price", with_rolling['aggregated_objs']['price'], "enviro", with_rolling['aggregated_objs']['enviro'], "auto", with_rolling['aggregated_objs']['auto'], "comfort", with_rolling['aggregated_objs']['comfort'])
print("Objectif WITHOUT rolling horizon : ", without_rolling['aggregated_objs']['Objective'], "price", without_rolling['aggregated_objs']['price'], "enviro", without_rolling['aggregated_objs']['enviro'], "auto", without_rolling['aggregated_objs']['auto'], "comfort", without_rolling['aggregated_objs']['comfort'])

#%% plot first 2 members 

to_plot1 = {
    "powers" : {
        "P_cons" : without_rolling['members_0']["P_cons"],
        "P_bat" : without_rolling['members_0']["P_bat"],
        "P_prod" : without_rolling['members_0']["P_prod"],
        "P_exchange" : without_rolling['members_0']["P_exchange"],
        "P_grid" : without_rolling['members_0']["P_grid"], 
        "P_surplus" : without_rolling['members_0']["P_surplus"],
        "irradiance" : irradiance_history[:horizon]
    },
    "title" : "Member 0 power profile without rolling horizon optimization"
}

to_plot2 = {
    "powers" : {
        "P_cons" : without_rolling['members_1']["P_cons"],
        "P_bat" : without_rolling['members_1']["P_bat"],
        "P_prod" : without_rolling['members_1']["P_prod"],
        "P_exchange" : without_rolling['members_1']["P_exchange"],
        "P_grid" : without_rolling['members_1']["P_grid"], 
        "P_surplus" : without_rolling['members_1']["P_surplus"],
        "irradiance" : irradiance_history[:horizon]
    },
    "title" : "Member 1 power profile without rolling horizon optimization"
}

plot_power_curves(**to_plot1)
plot_power_curves(**to_plot2)

#%% ADMM Version

kwargs = {
    "total_time" : horizon*nb_of_days,
    "horizon" : horizon,
    "deltat" : 1,
    "date" : date,
    "debug" : True,
    "until" : 2,
    "irradiance_history" : irradiance_history[:24] + irradiance_history[:25], 
    "weather_history" : weather_history[:24] + weather_history[:25],
    # "irradiance_forecast" : irradiance_forecast,
    # "weather_forecast" : weather_forecast,
    "irradiance_forecast" : irradiance_history[:24] + irradiance_history[:25],
    "weather_forecast" : weather_history[:24] + weather_history[:25],
    # "skip_params" : True
    }

help_admm = False
help_admm2 = False
for param in params : 
    param['parameters']['method'] = 'admm'
    param['parameters']['socio'] = socio
    param['parameters']['bat_exchange'] = bat_exchange
    param['parameters']['help_surplus_admm'] = help_admm
    param['parameters']['help_surplus_admm2'] = help_admm2
param_commu['method'] = 'admm'
param_commu['help_surplus_admm'] = help_admm
param_commu['help_surplus_admm2'] = help_admm2

param_commu["rho"]=  1e-8
param_commu["power_max_random"] =  10000
param_commu["eps_r"] = 1e-2
param_commu["eps_s"] = 1e-2
param_commu["max_iter"] = 500

with_rolling_admm, without_rolling_admm, debug_admm = rolling_horizon_optimization(params, param_commu, price_options, **kwargs)

co_admm = debug['community']

#%% Plot admm

to_plot_rolling_admm = {
    "powers" : {
        "P_cons" : with_rolling_admm['aggregated_powers']["P_cons"],
        "P_bat" : with_rolling_admm['aggregated_powers']["P_bat"],
        "P_prod" : with_rolling_admm['aggregated_powers']["P_prod"],
        "P_exchange" : with_rolling_admm['aggregated_powers']["P_exchange"],
        "P_grid" : with_rolling_admm['aggregated_powers']["P_grid"], 
        "Price" : prices[:horizon]*1e8,
        "irradiance" : irradiance_history[:horizon]
    },
    "title" : "Community power profile with rolling horizon optimization ADMM"
}

to_plot_without_rolling_admm = {
    "powers" : {
        "P_cons" : without_rolling_admm['aggregated_powers']["P_cons"],
        "P_bat" : without_rolling_admm['aggregated_powers']["P_bat"],
        "P_prod" : without_rolling_admm['aggregated_powers']["P_prod"],
        "P_exchange" : without_rolling_admm['aggregated_powers']["P_exchange"],
        "P_grid" : without_rolling_admm['aggregated_powers']["P_grid"], 
        "Price" : prices[:horizon]*1e8,
        "irradiance" : [val*10 for val in irradiance_history[:horizon]]
    },
    "title" : "Community power profile without rolling horizon optimization ADMM"
}


# plot_power_curves(**to_plot_rolling_admm)
plot_power_curves(**to_plot_without_rolling_admm)

# print("Objectif with rolling horizon : ", with_rolling_admm['aggregated_objs']['Objective'], "price", with_rolling_admm['aggregated_objs']['price'], "enviro", with_rolling_admm['aggregated_objs']['enviro'], "auto", with_rolling_admm['aggregated_objs']['auto'], "comfort", with_rolling_admm['aggregated_objs']['comfort'])
print("Objectif WITHOUT rolling horizon : ", without_rolling_admm['aggregated_objs']['Objective'], "price", without_rolling_admm['aggregated_objs']['price'], "enviro", without_rolling_admm['aggregated_objs']['enviro'], "auto", without_rolling_admm['aggregated_objs']['auto'], "comfort", without_rolling_admm['aggregated_objs']['comfort'])


#%% Plot first 2 members 

to_plot1 = {
    "powers" : {
        "P_cons" : without_rolling_admm['members_0']["P_cons"],
        "P_bat" : without_rolling_admm['members_0']["P_bat"],
        "P_prod" : without_rolling_admm['members_0']["P_prod"],
        "P_exchange" : without_rolling_admm['members_0']["P_exchange"],
        "P_grid" : without_rolling_admm['members_0']["P_grid"], 
        "P_surplus" : without_rolling_admm['members_0']["P_surplus"],
        "irradiance" : irradiance_history[:horizon]
    },
    "title" : "Member 0 power profile without rolling horizon optimization"
}

to_plot2 = {
    "powers" : {
        "P_cons" : without_rolling_admm['members_1']["P_cons"],
        "P_bat" : without_rolling_admm['members_1']["P_bat"],
        "P_prod" : without_rolling_admm['members_1']["P_prod"],
        "P_exchange" : without_rolling_admm['members_1']["P_exchange"],
        "P_grid" : without_rolling_admm['members_1']["P_grid"], 
        "P_surplus" : without_rolling_admm['members_1']["P_surplus"],
        "irradiance" : irradiance_history[:horizon]
    },
    "title" : "Member 1 power profile without rolling horizon optimization"
}

plot_power_curves(**to_plot1)
plot_power_curves(**to_plot2)

#%% Plot P cons for each device of the first member of the community

devices_name = []
for k in range(len(co.members[0].devices_name)) : 
    # if co.members[0].devices[k].__class__.__name__ == "white_good" : 
    #     devices_name.append(co.members[0].devices_name[k])
    devices_name.append(co.members[0].devices_name[k])

to_plot_rolling = {
    "powers" : {
        device : [(with_rolling['aggregated_powers']["devices"][device][k]) for k in range(horizon)] for device in devices_name
    },
    "title" : "With rolling horizon"
}

to_plot_without_rolling = {
    "powers" : {
        device : [(without_rolling['aggregated_powers']["devices"][device][k]) for k in range(horizon)] for device in devices_name
    },
    "title" : "Without rolling horizon"
}

plot_power_curves(**to_plot_rolling)

plot_power_curves(**to_plot_without_rolling)