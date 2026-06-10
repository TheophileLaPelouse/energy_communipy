import json, os
import matplotlib.pyplot as plt
from matplotlib import rcParams
import numpy as np
import pandas as pd
from tqdm import tqdm
from time import time

import sys
sys.path.append("/Users/theophilemounier/Desktop/git/projet_g3/python")
sys.path.append("/home/theophile/Desktop/git/projet_g3/python")
import pyomo.environ as pyo
from pyomo.opt import SolverFactory

from commu_opti.data.generate_data import generate_n_profile, create_random_agent
from commu_opti.commu_builder import define_members, define_community


def test_complexity(n, method, test_calc_ref=False, calc_ref=True, calc_ref_commu=True, max_iter=100) :
    
    t0 = time()
    
    print("generating data...")
    profile = [[0, 8, 1], [8, 16, 0], [16, 24, 1], [24, 32, 1], [32, 40, 0], [40, 48, 1], [48, 56, 1], [56, 64, 0], [64, 72, 1]]
    total_time = 72
    # profile = [[0, 8, 1], [8, 16, 0]]
    # total_time = 16
    profiles = generate_n_profile(n, profile, offset=2, lengths_rate=1.3, lengths_breaks_rate=0.3)
    t1 = time()
    print(f"data generated in {t1 - t0} seconds \n")

    agents = []
    for profile in profiles :
        agent = create_random_agent(profile)
        agents.append(agent)
    
    t2 = time()
    print(f"agent created in {t2 - t1} seconds \n")

    members_params = []
    for i, agent in enumerate(agents) :
        param = {"devices" : agent, "device_options" : {"total_time" : total_time, "deltat" : 1}, 
                "parameters" : {
                    "socio" : [1, 1, 0, 1],
                    "method" : method,
                    "id_" : i+1, 
                    "bat_exchange" : False, 
                    "total_time" : total_time,
                }}
        members_params.append(param)
    members = define_members(members_params, calc_ref=False)
    if test_calc_ref : 
        for m in members : 
            if not m.calc_ref_values(**m.kwargs) : 
                print("Mauvaise ref")
                return m
    
    t3 = time()
    print(f"members defined in {t3 - t2} seconds \n")
    
    param_commu = {
        "method" : method,
        "deltat" : 1,
        "total_time" : total_time,
        "calc_ref" : calc_ref, 
        "ref_values" : [1, 1, 1, 1],
        "max_iter" : max_iter,
        "rho" : 0.001/n, 
        "power_max_random" : 0,
        "parallel" : True,
    }

    price_options = {
        "eco" : {
            "cost_grid_buy" : 0.0003, # €/wh
            "cost_grid_sell" : -0.00003,
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

    print("defining community...")
    t4 = time()
    
    community = define_community(members, **param_commu, **price_options)
    t5 = time()
    print(f"community defined in {t5 - t4} seconds \n")
    print("optimizing community...")
    print(community.members)
    t6 = time()
    if method == 'admm' : 
        state = community.optimize_admm("gurobi", **community.kwargs)
    else : 
        state = community.optimize("gurobi")
    t7 = time()
    print(f"community optimized in {t7 - t6} seconds \n")
    print(f"total time for {n} members : {t7 - t0} seconds \n")
    community.aggregate_distributed_information()
    return (t7 - t6, t7-t0, community, members_params, state)


retur = test_complexity(4, "admm", calc_ref=False, calc_ref_commu = False)
co = retur[2]