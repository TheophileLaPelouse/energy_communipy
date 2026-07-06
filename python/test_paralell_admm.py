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


def generate_test_data(n) : 
    print("generating data...")
    t0 = time()
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
    return agents

def test_complexity(agents, method, test_calc_ref=False, calc_ref=True, max_iter=100, parallel=True, eps_r=0.001, eps_s=0.001) :
    
    n = len(agents)
    
    t2 = time()
    total_time = 24
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
            "calc_ref" : True, 
            "max_iter" : 50,
            "rho" : 0.001/n, 
            "power_max_random" : 0,
            "parallel" : parallel,
            "eps_r" : 1e-2, 
            "eps_s" : 1e-2,
            # "debug_ref" : True,
            # "debug_admm" : True,
        }

    price_options = {
        "eco" : {
            "cost_grid_buy" : [0.0003 for k in range(total_time)], # €/wh
            "cost_grid_sell" : [-0.0003 for k in range(total_time)],
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
        time_centralized = community.results["admm"]["Times"]["global_optimizer"]
        time_decentralized = community.results["admm"]["Times"]["local_optimizer"]
        print(f"community optimized using admm with the global optimizer in {time_centralized} seconds and local optimizers in {time_decentralized} seconds \n")
    else : 
        state = community.optimize("gurobi")
    t7 = time()
    print(f"community optimized in {t7 - t6} seconds \n")
    print(f"total time for {n} members : {t7 - t2} seconds \n")
    community.aggregate_distributed_information()
    return (t7 - t6, t7-t2, community, members_params, state)

def compare_admm_centralized(admm_param, centralized_param, n) : 
    
    flag = True
    c = 0
    while flag : 
        try : 
            agents = generate_test_data(n)
            flag =False
        except :
            c+=1
            if c> 5 : 
                return(None, None, None, None, None, None)
        
    
    results_admm = test_complexity(agents, "admm", **admm_param)
    results_centralized = test_complexity(agents, "centralized", **centralized_param)
    
    co_admm = results_admm[2]
    co_admm.aggregate_distributed_information()
    co_centralized = results_centralized[2]
    co_centralized.aggregate_distributed_information()
    obj_admm = co_admm.results["aggregated_objs"]["price"] + co_admm.results["aggregated_objs"]["enviro"] + co_admm.results["aggregated_objs"]["auto"] + co_admm.results["aggregated_objs"]["confort"]
    obj_centralized = co_centralized.results["aggregated_objs"]["price"] + co_centralized.results["aggregated_objs"]["enviro"] + co_centralized.results["aggregated_objs"]["auto"] + co_centralized.results["aggregated_objs"]["confort"]
    obj_diff = obj_admm - obj_centralized
    print(co_centralized.results.keys())
    time_centralized = co_centralized.results["centralized"]["Times"]["self_optimize"]
    time_admm_global = co_admm.results["admm"]["Times"]["global_optimizer"]
    time_admm_local = co_admm.results["admm"]["Times"]["local_optimizer"]
    return (obj_diff, time_centralized, time_admm_global, time_admm_local, co_admm, co_centralized)

def plot_comparaison(parallel=False) : 
    n = range(1, 40, 1)
    obj_diffs = []
    time_centralizeds = []
    time_admm_globals = []
    time_admm_locals = []
    for k in n : 
        print(f"\nComparing ADMM and centralized for {k} members...\n")
        admm_param = {"parallel" : parallel}
        centralized_param = {}
        res = compare_admm_centralized(admm_param, centralized_param, k)
        obj_diffs.append(res[0])
        time_centralizeds.append(res[1])
        time_admm_globals.append(res[2])
        time_admm_locals.append(res[3])
    
    plt.figure()
    plt.plot(n, obj_diffs, "+", label="Objective difference")
    plt.xlabel("Number of members")
    plt.ylabel("Objective difference")
    plt.title("Comparison of ADMM and Centralized approaches")
    plt.legend()
    plt.show()
    
    plt.figure()
    plt.plot(n, time_centralizeds, "+", label="Centralized time")
    plt.plot(n, time_admm_globals, "+", label="ADMM global time")
    plt.plot(n, time_admm_locals, "+", label="ADMM local time")
    plt.xlabel("Number of members")
    plt.ylabel("Time (s)")
    plt.title("Comparison of ADMM and Centralized approaches")
    plt.legend()
    plt.show()




if __name__ == "__main__" : 
    import sys 
    # default_args = {
    #     "n" : 2,
    #     "method" : "admm",
    #     "test_calc_ref" : False,
    #     "calc_ref" : False,
    #     "calc_ref_commu" : False,
    #     "max_iter" : 100
    # }
    # args = sys.argv[1:]
    # # Just first number of members is taken into account, the rest is ignored
    # if len(args) > 0 :
    #     default_args["n"] = int(args[0])
    # retur = test_complexity(**default_args)
    # co = retur[2]
    plot_comparaison(parallel=False)
    
    # eps_r = 5
    # eps_s = 5
    # obj_diffs = []
    # for k in range(6) :
    #     eps_r /= (k%2)*5 + (k+1)%2*2
    #     eps_s /= (k%2)*5 + (k+1)%2*2
    #     diffs = []
    #     for j in range(5) : 
    #         n=5
    #         args_admm = {
    #                 "method" : "admm",
    #                 "test_calc_ref" : False,
    #                 "calc_ref" : False,
    #                 "max_iter" : 50, 
    #                 'parallel' : False, 
    #                 'eps_r' : eps_r,
    #                 'eps_s' : eps_s
    #             }
        
    #         args_centralized = {
    #                 "method" : "centralized",
    #                 "calc_ref" : False
    #         }
        
    #         agents = generate_test_data(n)
    #         retur1 = test_complexity(agents, **args_admm)
    #         retur2 = test_complexity(agents, **args_centralized)
    #         coa = retur1[2]
    #         coc = retur2[2]
    #         obj_admm = coa.results["aggregated_objs"]["price"] + coa.results["aggregated_objs"]["enviro"] + coa.results["aggregated_objs"]["confort"]
    #         obj_centr = coc.results["aggregated_objs"]["price"] + coc.results["aggregated_objs"]["enviro"] + coc.results["aggregated_objs"]["confort"]
    #         relative_diff = abs(obj_admm - obj_centr) / (obj_admm + 1e-8)
    #         diffs.append(relative_diff)
    #     average_diff = sum(diffs) / len(diffs)
    #     obj_diffs.append(average_diff)

    # to_plot = {
    #     "powers" : {
    #         "P_grid" : coa.results['aggregated_powers']['P_grid'],
    #         "P_bat" : coa.results['aggregated_powers']['P_bat'],
    #         "P_cons" : coa.results['aggregated_powers']['P_cons'], 
    #         "P_exchange" : coa.results['aggregated_powers']['P_exchange'],
    #         "P_prod" : coa.results['aggregated_powers']['P_prod']
    #     }, 
    #     "title" : "Power for admm optimization"
    # }
        
    # coa.plot_power_curves(**to_plot)

    # to_plot = {
    #     "powers" : {
    #         "P_grid" : coc.results['aggregated_powers']['P_grid'],
    #         "P_bat" : coc.results['aggregated_powers']['P_bat'],
    #         "P_cons" : coc.results['aggregated_powers']['P_cons'], 
    #         "P_exchange" : coc.results['aggregated_powers']['P_exchange'],
    #         "P_prod" : coc.results['aggregated_powers']['P_prod']
    #     },
    #     "title" : "Power for centralized optimization"
        
    # }
        
    # coc.plot_power_curves(**to_plot)