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
from commu_opti.opti.rolling_horizon import rolling_horizon_optimization
from commu_opti.plotting.plot_functions import plot_power_curves


#%% Test rolling horizon for white goods

n = 1
nb_of_days = 3
horizon = 24
total_time = nb_of_days * horizon
# method = "admm"
method = "centralized"

member_params = {"socio" : [1, 0, 0, 0.5], "calc_ref" : False, "id_" : 0, "profile_method" : None}


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
param["parameters"]["socio"] = member_params["socio"]
param["parameters"]["calc_ref"] = member_params["calc_ref"]
param["parameters"]["id_"] = member_params["id_"]
param["parameters"]["profile_method"] = member_params["profile_method"]
param["parameters"]["method"] = method


params = [param]

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
        "cost_grid_sell" : -prices[:horizon]/4*0,
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
#%%
kwargs = {
    "total_time" : total_time,
    "horizon" : horizon,
    "deltat" : 1,
    "date" : date,
    "irradiance_forecast" : irradiance_profile,
    "irradiance_history" : irradiance_profile,
    # "until" : 10,
    }

with_rolling, without_rolling = rolling_horizon_optimization(params, param_commu, price_options, **kwargs)

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

plot_power_curves(**to_plot)
plot_power_curves(**to_plot_rolling)


#%% Test rolling horizon for heating
wake_set = set(range(0, 8)) | set(range(20, 24))
away_set = set(range(8, 20))
presence_profile = [{"awake" : 1, "asleep" : 0, "away" : 0} if k in wake_set else {"awake" : 0, "asleep" : 0, "away" : 1} for k in range(horizon)]*nb_of_days

heating_params = {
    "T_wanted" : {"awake" : 20, "asleep" : 15, "away" : 15},
    "T_min" : {"awake" : 16, "asleep" : 14, "away" : 10},
    "R1" : 1, "R2" : 1, "C" : 10000000, "efficiency" : 1, "type" : "resistor"
}

heat_device = {
    "parameters" : {"heating_params" : heating_params,
        "power_range" : [[0, 0] for k in range(horizon)],
        "name" : "heating_system"},
    "type" : "flex"
}
param = {"devices" : {"heating_system" : heat_device}, "parameters" : {}}

param["parameters"]["socio"] = [0, 0, 0, 1]
param["parameters"]["calc_ref"] = member_params["calc_ref"]
param["parameters"]["id_"] = member_params["id_"]
param["parameters"]["profile_method"] = member_params["profile_method"]
param["parameters"]["presence_profile"] = presence_profile

params = [param]

weather_forecast = [0 for k in range(total_time)]
weather_history = [0 for k in range(total_time)]

kwargs = {
    "total_time" : total_time,
    "horizon" : horizon,
    "deltat" : 1,
    "date" : date,
    "weather_forecast" : weather_forecast,
    "weather_history" : weather_history,
    # "until" : 2
    }

with_rolling, without_rolling = {}, {}
with_rolling, without_rolling = rolling_horizon_optimization(params, param_commu, price_options, **kwargs)

#%% plots
T_wanted = [(heating_params["T_wanted"]["awake"]*presence_profile[k]["awake"] + heating_params["T_wanted"]["away"]*presence_profile[k]["away"]) for k in range(48)]
to_plot_rolling = {
    "powers" : {
        "with_rolling P_cons" : with_rolling['aggregated_powers']["P_cons"],
        "Temperature_wanted" : T_wanted
    },
    "total_time" : 48, 
}

plot_power_curves(**to_plot_rolling)

#%% Case EV

EV_device = {
    "parameters" : {
        "p_range" : [-10, 10], 
        "E_range" : [5, 45], 
        # "time_home" : [[15, 23], [40, 48]],
        # "E0s" : [25, -15], 
        # "E_min" :[22, 25], 
        "time_home" : [[0, 10], [15, 23], [40, 48]],
        "E0s" : [25, -30, -15], 
        "E_min" :[37, 22, 25], 
        "E_end" : 25,
        "name" : "EV"},
    "type" : "EV"
}

param = {"devices" : {"EV" : EV_device}, "parameters" : {}}

param["parameters"]["socio"] = [1, 0, 0, 0]
param["parameters"]["calc_ref"] = member_params["calc_ref"]
param["parameters"]["id_"] = member_params["id_"]
param["parameters"]["profile_method"] = member_params["profile_method"]
# param["parameters"]["presence_profile"] = presence_profile

params = [param]

kwargs = {
    "total_time" : total_time,
    "horizon" : horizon,
    "deltat" : 1,
    "date" : date,
    # "until" : 20
    }

with_rolling, without_rolling = {}, {}
with_rolling, without_rolling = rolling_horizon_optimization(params, param_commu, price_options, **kwargs)

#%% Plots
home_set = set(range(0, 10)) | set(range(15, 34)) | set(range(40, 48))
home = [1 if k in home_set else 0 for k in range(48)]

to_plot = {
    "powers" : {
        "with_rolling P_cons" : with_rolling['aggregated_powers']["P_bat"],
        "Home" : home
    },
    "total_time" : 48,
}
plot_power_curves(**to_plot)

to_plot = {
    "powers" :  {
        "standard P_cons" : without_rolling['aggregated_powers']["P_bat"],
        "Home" : home[:24]
        }
    }
plot_power_curves(**to_plot)


#%% Case AoN

AoN_device = {
    "parameters" : {
        "power_needed" : 10,
        "energy_needed" : 20, 
        "name" : "water_heater"
        },
    "type" : "AoN"
}

param = {"devices" : {"AoN" : AoN_device}, "parameters" : {}}

param["parameters"]["socio"] = [1, 0, 0, 0]
param["parameters"]["calc_ref"] = member_params["calc_ref"]
param["parameters"]["id_"] = member_params["id_"]
param["parameters"]["profile_method"] = member_params["profile_method"]

params = [param]

kwargs = {
    "total_time" : total_time,
    "horizon" : horizon,
    "deltat" : 1,
    "date" : date,
    "until" : 3, 
    "debug" : True,
    }

with_rolling, without_rolling = {}, {}
with_rolling, without_rolling, debug = rolling_horizon_optimization(params, param_commu, price_options, **kwargs)
co = debug['community']
co.debug_model()
d = co.members[0].devices[0]