from .data.generate_data_V2 import (
    generate_profile, generate_building, get_weather_data, 
    device_activation_profile, device_power_profile, one_device_allocation, 
    list_devices, list_locations
)

from .commu_builder import define_members, define_community
from .data.generate_data_V2 import get_price_data
from .data.ev_profile import EV_profile

import datetime as dt
from random import randint
import numpy as np

def generate_devices_data(**kwargs) : 
    
    # define time parameters
    
    deltat = kwargs.get("deltat", 1)
    date = kwargs.get("date")
    nb_of_days = kwargs.get("nb_of_days", 1)
    if not date : 
        # Choose random date in 2020
        day_number = randint(1, 365)
        date = dt.datetime(2025, 1, 1) + dt.timedelta(days=day_number)
    date_start = date
    date_end = date + dt.timedelta(days=nb_of_days)
        
    
    build = generate_building()
    nb_people = build["nb_people"]
    states = [f"{k}{j}" for k in range(nb_people+1) for j in range(nb_people+1)]
    states = {states[i] : i for i in range(len(states))}
    
    
    lat, lon = kwargs.get("location", list_locations[randint(0, len(list_locations)-1)])
    weather_forecast, irradiance_profile = get_weather_data(date_start, date_end, lat=lat, lon=lon, forecast=True, deltat=deltat)
    weather_history, irradiance_history = get_weather_data(date_start, date_end, lat=lat, lon=lon, forecast=False, deltat=deltat)
    weather = {"forecast" : {
        "temperature" : weather_forecast, 
        "irradiance" : irradiance_profile
        },
        "history" : {
            "temperature" : weather_history,
            "irradiance" : irradiance_history
        }
    }
    equipments = {}
    for device in list_devices : 
        equipments[device] = one_device_allocation(list_devices[device], nb_people)
        
    return nb_people, deltat, equipments, build, weather

def generate_devices_profile(nb_people, deltat, equipments, build, weather, **kwargs) :
        
    total_time = kwargs.get("total_time", 24)
    nb_days_profile = int(total_time/24)
    if total_time % 24 != 0 : nb_days_profile += 1
    profile = []
    for _ in range(nb_days_profile) :
        profile += generate_profile(nb_people, False, deltat)
        
    profile = profile[:int(total_time/deltat)]
    if kwargs.get("one_empty_day", False) :
        profile[-(int(24/deltat)):] = ['00' for k in range(int(24/deltat))]
    
    final_result = {}
    args = {}
    for device in equipments : 
        if equipments[device]["Number"] != 0 and equipments[device].get("P") != 0 : 
            # print(f"\nDevice {device} \n")
            activation_profile, when_profile, presence_profile = device_activation_profile(profile, equipments[device], deltat, nb_people, **kwargs)
            # print(f"Activation profile for {device} : {activation_profile}, when_profile : {when_profile}")
            # print("Activation profile copmuted")
            spec_args = {
                "activation_profile" : activation_profile,
                "when_profile" : when_profile,
                "presence_profile" : presence_profile,
                "device_name" : device,
                "allocated" : equipments[device],
                "building" : build,
                "nb_people" : nb_people,
                "deltat" : deltat,
                "weather" : weather
                }
            if not args.get("presence_profile") : 
                args["presence_profile"] = presence_profile
                args["building"] = build
                args["weather"] = weather
                args["nb_people"] = nb_people
                args["deltat"] = deltat
            pow_profile = device_power_profile(**spec_args)
            pow_profile["parameters"]["name"] = device
            # print("Power profile computed")
            
            final_result[device] = {"power_profile" : pow_profile, "args" : spec_args}
    
    devices = {device : final_result[device]["power_profile"] for device in final_result}
    final_result["args"] = args
    # member_param = {
    #     'socio': [1, 1, 0, 1],
    #     'id_': 0,
    # }
    param = {"devices" : devices, "device_options" : {"total_time" : kwargs.get("total_time", 24), "deltat" : deltat}} #, "parameters" : member_param}
    
    return param, final_result
    
    
def generate_member_data_random(**kwargs) : 
    nb_people, deltat, equipments, build, weather = generate_devices_data(**kwargs)
    return generate_devices_profile(nb_people, deltat, equipments, build, weather, **kwargs)

def separate_horizon_futur(param, horizon, deltat=1) : 
    # Horizon, total_time as indices and not hours
    devices_futur = {}
    param["device_options"]["total_time"] = horizon
    for dev in param["devices"] : 
        dico = param["devices"][dev]
        typ = dico["type"]
        if typ == 'EV' : 
            # print("\nEV device : ", dico)
            time_home = dico["parameters"]["time_home"]
            # print(time_home)
            Emins = dico["parameters"]["E_min"]
            E0s = dico["parameters"]["E0s"]
            i = 0
            while i < len(time_home) and time_home[i][1] <= horizon : 
                i += 1
            if i < len(time_home) and time_home[i][0] < horizon : 
                time_home_horizon = time_home[:i] + [[time_home[i][0], horizon]]
                time_home_futur = [[horizon, time_home[i][1]]] + time_home[i+1:]
                E0s_horizon = E0s[:i+1] # One value for each start of a home period, Not sure about this
                E0s_futur = [0] + E0s[i+1:] # Duplicate starting energy.
                delta_e_max = deltat * dico["parameters"]["p_range"][1]
                Emins_horizon = Emins[:i] + [Emins[i]/((time_home[i][1] - horizon)*delta_e_max)] # Minimum energy needed for validating the futur constraint
                Emins_futur = Emins[i:] 
            else : 
                time_home_horizon = time_home[:i]
                time_home_futur = time_home[i:]
                E0s_horizon = E0s[:i] # One value for each start of a home period
                E0s_futur = E0s[i:]
                Emins_horizon = Emins[:i] # One value for each end of a home period. And as much not home periods as 
                Emins_futur = Emins[i:]
            
            
                
            devices_futur[dev] = {
                "futur_time_home" : time_home_futur,
                "futur_Emins" : Emins_futur,
                "futur_E0s" : E0s_futur
            }
            dico["parameters"]["time_home"] = time_home_horizon
            dico["parameters"]["E_min"] = Emins_horizon
            dico["parameters"]["E0s"] = E0s_horizon

  

        if typ == 'white_good' : 
            # Attention pour le moment on ne s'occupe pas de la puissance, faudra le faire
            
            start_time = dico["parameters"]["start_pref"]
            cycle_length = dico["parameters"]["cycle_length"]
            time_range = dico["parameters"]["time_range"]
            power_needed = dico["parameters"]["power_needed"]
            i = 0
            while i < len(start_time) and start_time[i] + time_range[i][1] <= horizon :
                i += 1
            if i >= len(start_time) :
                start_time_horizon = start_time[:]
                cycle_length_horizon = cycle_length[:]
                time_range_horizon = time_range[:]
                power_needed_horizon = power_needed[:]
            else :
                start_time_horizon = start_time[:i]
                cycle_length_horizon = cycle_length[:i]
                time_range_horizon = time_range[:i]
                power_needed_horizon = power_needed[:i]
            start_time_futur = start_time[i:]
            cycle_length_futur = cycle_length[i:]
            time_range_futur = time_range[i:]
            power_needed_futur = power_needed[i:]
            devices_futur[dev] = {
                "futur_starts" : start_time_futur,
                "futur_lengths" : cycle_length_futur,
                "futur_time_range" : time_range_futur,
                "futur_power_needed" : power_needed_futur
            }
            dico["parameters"]["start_pref"] = start_time_horizon
            dico["parameters"]["cycle_length"] = cycle_length_horizon
            dico["parameters"]["time_range"] = time_range_horizon
            dico["parameters"]["power_needed"] = power_needed_horizon
            
    return param, devices_futur

def generate_member_params(**kwargs) :
    """Generate member params based on kwargs : 
    
    {
        EV_rate # probability of having an EV in the community
        PV_rate # probability of having a PV in the community
        Battery_rate # probability of having a battery in the community
        n_members # number of members in the community
        nb_of_days # number of days for the simulation
        deltat # time step in hours
        horizon # horizon in hours
        EV_allocation # allocation of EV parameters
        PV_allocation # allocation of PV parameters
        bat_allocation # allocation of battery parameters
        bat_exchange # Whether to allow battery exchange with the grid or not 
    }

    Returns:
        what is needed to generate a community : params, date, weather, price_options
    """
        
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
    
    flag = True
    c = 0
    while flag : 
        day_number = np.random.randint(1, 365)
        date = dt.datetime(2025, 1, 1) + dt.timedelta(days=day_number)
    
        lat, lon = list_locations[np.random.randint(0, len(list_locations)-1)]
        
    
        weather_forecast, irradiance_forecast = get_weather_data(date, date + dt.timedelta(days=nb_of_days), lat=lat, lon=lon, forecast=True, deltat=deltat)
        weather_history, irradiance_history = get_weather_data(date, date + dt.timedelta(days=nb_of_days), lat=lat, lon=lon, forecast=False, deltat=deltat)
        flag = False
        if len(weather_forecast) < total_time : flag=True
        if len(irradiance_forecast) < total_time : flag=True
        if len(weather_history) < total_time : flag=True
        if len(irradiance_history) < total_time : flag=True
        c+=1
        if c >= 10 : flag=False
        
        
        
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
    """Generate a community, kwargs are composed of 
    {
        skip_params : whether to skip the work on member parameters or not 
        more_member_params : dictionary of parameters to add to each member parameters
        irradiance_forecast : irradiance forecast to use for PV devices
        irradiance_history : irradiance history to use for PV devices
    }

    Args:
        params_member (_type_): _description_
        param_commu (_type_): _description_
        price_options (_type_): _description_

    Returns:
        _type_: _description_
    """
    
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
    """Take args to define communities and compute optimization results for each settings. kwargs is composed of 
    {
        **kwargs for generate_member_params (except n_members)
        n_range : range of number of members in the community
        n_iterations : number of community to generate for each method
        list_method : list of methods to use for each community optimization, default is ["centralized", "admm"]
        list_param_commu : list of parameters for the community optimization, one for each iteration
        list_more_members : list of parameters to add to each member parameters, one for each iteration
        
        help_admm : whether to add a constraint to help the convergence of ADMM (not so good)
        help_admm2 : whether to add a penalization cost in objective to help the convergence of ADMM (not so good)
    }
    
    Returns:
        dict : results of the optimization for each community, with keys being either a given name of the community or "community_{method}_{k}" where k is the iteration number and method is the optimization method used
    """
    
    n_range = kwargs.get("n_range", [5, 20])
    n_iterations = kwargs.get("n_iterations", 10)
    
    list_param_commu = kwargs.get("list_param_commu", [{} for k in range(n_iterations)])
    list_more_members = kwargs.get("list_more_members", [{} for k in range(n_iterations)])
        
    results = {}    
    
    for k_iter in range(n_iterations) : 
        for_generation = {}
        for_generation.update(kwargs)
        for_generation["n_members"] = np.random.randint(n_range[0], n_range[1])
        params, date, weather, price_options = generate_member_params(**for_generation)
        for_generation["date"] = date
        param_commus = []
        for method in kwargs.get("list_method", ["centralized", "admm"]) : 
            param_commu = {
                "solving_method" : method,
                "deltat" : kwargs.get("deltat", 1),
                "total_time" : kwargs.get("horizon", 24),
                "calc_ref" : True, 
                "rho" : 1e-8,
                "power_max_random" : 10000,
                "eps_r" : 1e-2,
                "eps_s" : 1e-2,
                "max_iter" : 500
            }
            param_commu.update(list_param_commu[k_iter])
            print(param_commu)
            param_commu['help_surplus_admm'] = kwargs.get('help_admm', False)
            param_commu['help_surplus_admm2'] = kwargs.get('help_admm2', False)
            param_commu["method"] = method
            param_commus.append(param_commu)
            
        communities = []
        for i in range(len(param_commus)) :
            param_commu = param_commus[i]
            more_param_members = list_more_members[i]
            community = generate_community(params, param_commu, price_options, **more_param_members, **weather, **for_generation)
            community.kwargs.update(weather)
            communities.append(community)
            
        for commu in communities : 
            res = commu.full_optimization("gurobi", **commu.kwargs)
            name = commu.kwargs.get("name", f"community_{commu.kwargs.get('method')}_{k_iter}")
            print(name)
            results[name] = res
        print(communities)
            
    return results
        