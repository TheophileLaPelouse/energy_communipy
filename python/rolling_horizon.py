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
from commu_opti.generate_device_infos import generate_member_data_random
from commu_opti.data.generate_data_V2 import list_locations, get_price_data

# First choose a location

# choose a timeframe

# choose penetration rate of PV, EV and battery

EV_rate = 0.2
PV_rate = 0.3
Battery_rate = 0.1

# generate agents data

possible_socio = []
for k in range(8) : 
    for j in range(8-k) : 
        for i in range(8-j-k) : 
            possible_socio.append([k, j, i, 8-k-j-i])
            

n = 10


day_number = np.random.randint(1, 365)
date = dt.datetime(2020, 1, 1) + dt.timedelta(days=day_number)
nb_of_days = 3
lat, lon = list_locations[np.random.randint(0, len(list_locations)-1)]

params = []
for k in range(n) : 
    rd_EV = np.random.rand()
    rd_PV = np.random.rand()
    rd_bat = np.random.rand()
    
    param, final_result = generate_member_data_random(nb_of_days=3, location=(lat, lon))
    if rd_EV < EV_rate : 
        # to do : define PV and EV, for PV needs irradiance
        
    if rd_PV < PV_rate : 
        # to do : define PV
        
    if rd_bat < Battery_rate : 
        # to do : define battery and PV
    
    param["parameters"]["socio"] = possible_socio[np.random.randint(0, len(possible_socio)-1)]
    param["parameters"]["calc_ref"] = False
    param["parameters"]["id_"] = k 
    param["parameters"]["method"] = "admm"
    params.append(param)
    
members = define_members(params)

param_commu = {
        "method" : "admm",
        "deltat" : 1,
        "total_time" : 24,
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
        "cost_grid_buy" : prices[:24], # €/wh
        "cost_grid_sell" : -prices[:24]/4,
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