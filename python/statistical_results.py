import json, os
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

from commu_opti.data.generate_data import generate_n_profile, create_random_agent
from commu_opti.commu_builder import define_members, define_community
from commu_opti.generate_device_infos import generate_member_data_random, generate_devices_data, generate_devices_profile, separate_horizon_futur
from commu_opti.data.generate_data_V2 import get_weather_data, list_locations, get_price_data
from commu_opti.data.ev_profile import EV_profile
from commu_opti.opti.rolling_horizon import rolling_horizon_optimization
from commu_opti.plotting.plot_functions import plot_power_curves    

def generate_params(**kwargs) :
        
    EV_rate = kwargs.get("EV_rate", 0.3)
    PV_rate = kwargs.get("PV_rate", 0.3)
    Battery_rate = kwargs.get("Battery_rate", 0.2)

    # generate agents data

    possible_socio = []
    for k in range(8) : 
        for j in range(8-k) : 
            for i in range(8-j-k) : 
                # possible_socio.append([k/8, j/8, i/8, (8-k-j-i)/8])
                possible_socio.append([0, 1, 1, 1])
                

    n = kwargs.get('n_members', 5)
    nb_of_days = kwargs.get('nb_of_days', 2)
    deltat = kwargs.get('deltat', 1)
    horizon = kwargs.get("horizon", 24)
    total_time=(horizon*nb_of_days)//deltat

    day_number = np.random.randint(1, 365)
    date = dt.datetime(2025, 1, 1) + dt.timedelta(days=day_number)

    lat, lon = list_locations[np.random.randint(0, len(list_locations)-1)]
    

    weather_forecast, irradiance_forecast = get_weather_data(date, date + dt.timedelta(days=nb_of_days), lat=lat, lon=lon, forecast=True, deltat=deltat)
    weather_history, irradiance_history = get_weather_data(date, date + dt.timedelta(days=nb_of_days), lat=lat, lon=lon, forecast=False, deltat=deltat)

    weather_forecast, irradiance_forecast = list(weather_forecast), list(irradiance_forecast)
    weather_history, irradiance_history = list(weather_history), list(irradiance_history)

    horizon = kwargs.get("horizon", 24)

    EV_allocation = kwargs.get("EV_allocation", {
        "E_range" : [10, 70], # kwh
        "P_max" : [3.6, 7.4, 11, 22], # kW
        "proba_minus" :0.5
    })

    PV_allocation = kwargs.get("PV_allocation", {
        "portion_surf" : 0.7, 
        "eff" : [0.2, 0.05] # average, variance
    })

    bat_allocation = kwargs.get("bat_allocation", {
        "E_range" : [5, 40], # kwh
        "C_range" : [0.25, 1], 
        "charge_eff" : [0.93, 0.02], # average, variance
        "dcharge_eff" : [0.93, 0.02], # average
    })
    
    params = []
    n_PV = 0
    for k in range(n) : 
        rd_EV = np.random.rand()
        rd_PV = np.random.rand()
        rd_bat = np.random.rand()   
        
        nb_people, deltat, equipments, build, weather = generate_devices_data(date=date, nb_of_days=nb_of_days, location=(lat, lon), deltat=deltat)
        
        param, final_result = generate_devices_profile(nb_people, deltat, equipments, build, weather, total_time=total_time, one_empty_day=True)
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
        param["parameters"]["debug_ref"] = True
        param["parameters"]["building"] = building
        param["parameters"]["nb_people"] = final_result['args']['nb_people']
        param["parameters"]["presence_profile"] = presence_profile
        param["parameters"]["bat_exchange"] = kwargs.get("bat_exchange", True)
        
        param["device_options"] = {"total_time" : total_time, "deltat" : deltat}
        param, devices_futur = separate_horizon_futur(param, horizon, deltat=deltat)
        param["parameters"]["time_window"] = [date, date + dt.timedelta(days=nb_of_days)]
        param["parameters"]["horizon"] = horizon
        param["parameters"]["devices_futur"] = devices_futur
            
        params.append(param)
        
    prices = get_price_data(date, date + dt.timedelta(days=nb_of_days))[:(nb_of_days*24)]/10e6
    
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
    
    weather = {"weather_forecast":weather_forecast, "weather_history":weather_history, "irradiance_forecast":irradiance_forecast, "irradiance_history":irradiance_history}
    return params, date, weather, price_options


def generate_community(params_member, param_commu, price_options, **kwargs) : 
    
    if not kwargs.get("skip_params", False) : 
    
        for param in params_member : 
            # Changes needed for building member models
            param["parameters"]["method"] = param_commu.get("method", "centralized")
            param["parameters"].update(kwargs.get("more_member_params", {}))
            if "PV" in param["devices"] : 
                horizon = param["parameters"]['horizon']
                irradiance_forecast = kwargs.get("irradiance_forecast", param["devices"]["PV"]["parameters"]["irradiance_profile"])
                irradiance_history = kwargs.get("irradiance_history", param["devices"]["PV"]["parameters"]["irradiance_profile"])
                param["devices"]["PV"]["parameters"]["irradiance_profile"] = [irradiance_history[0]] + irradiance_forecast[1:horizon]

    
    members = define_members(params_member)
    community = define_community(members, **param_commu, **price_options)
    return community 

def compute_results(**kwargs) :
    
    n_range = kwargs.get("n_range", [5, 20])
    n_iterations = kwargs.get("n_iterations", 10)
    
    list_param_commu = kwargs.get("list_param_commu", [{} for k in range(n_iterations)])
    list_more_members = kwargs.get("list_more_members", [{} for k in range(n_iterations)])
        
    results = {}    
    
    for k in range(n_iterations) : 
        for_generation = {}
        for_generation.update(kwargs)
        for_generation["n_members"] = np.random.randint(n_range[0], n_range[1])
        params, date, weather, price_options = generate_params(**for_generation)
        for_generation["date"] = date
        param_commus = []
        for method in kwargs.get("list_method", ["centralized", "admm"]) : 
            param_commu = list_param_commu[k]
            if not param_commu : 
                param_commu = {
                    "solving_method" : method,
                    "deltat" : 1,
                    "total_time" : kwargs.get("horizon", 24),
                    "calc_ref" : True, 
                    "rho" : 1e-8,
                    "power_max_random" : 10000,
                    "eps_r" : 1e-2,
                    "eps_s" : 1e-2,
                    "max_iter" : 500
                }
                param_commu['help_surplus_admm'] = kwargs.get('help_admm', False)
                param_commu['help_surplus_admm2'] = kwargs.get('help_admm2', False)
            param_commu["method"] = method
            param_commus.append(param_commu)
            
        communities = []
        for k in range(len(param_commus)) :
            param_commu = param_commus[k]
            more_param_members = list_more_members[k]
            community = generate_community(params, param_commu, price_options, **more_param_members, **weather, **for_generation)
            community.kwargs.update(weather)
            communities.append(community)
            
        for commu in communities : 
            res = commu.full_optimization("gurobi", **commu.kwargs)
            name = commu.kwargs.get("name", f"community_{commu.kwargs.get('method')}_{k}")
            results[name] = res
            
    return results
        

