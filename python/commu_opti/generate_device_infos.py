from .data.generate_data_V2 import (
    generate_profile, generate_building, get_weather_data, 
    device_activation_profile, device_power_profile, one_device_allocation, 
    list_devices, list_locations
)

import datetime as dt
from random import randint

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
    
    final_result = {}
    args = {}
    for device in equipments : 
        if equipments[device]["Number"] != 0 and equipments[device].get("P") != 0 : 
            # print(f"\nDevice {device} \n")
            activation_profile, when_profile, presence_profile = device_activation_profile(profile, equipments[device], deltat, nb_people, **kwargs)
            print(f"Activation profile for {device} : {activation_profile}, when_profile : {when_profile}")
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

def separate_horizon_futur(param, horizon) : 
    # Horizon, total_time as indices and not hours
    devices_futur = {}
    param["device_options"]["total_time"] = horizon
    for dev in param["devices"] : 
        dico = param["devices"][dev]
        typ = dico["type"]
        if typ == 'EV' : 
            time_home = dico["parameters"]["time_home"]
            Emins = dico["parameters"]["E_min"]
            E0s = dico["parameters"]["E0s"]
            i = 0
            while time_home[i][1] <= horizon : 
                i += 1
            if time_home[i][0] < horizon : 
                time_home_horizon = time_home[:i] + [[time_home[i][0], horizon]]
                time_home_futur = [[horizon, time_home[i][1]]] + time_home[i+1:]
            else : 
                time_home_horizon = time_home[:i]
                time_home_futur = time_home[i:]
            
            Emins_horizon = Emins[:i] # One value for each end of a home period. And as much not home periods as 
            Emins_futur = Emins[i:]
            
            E0s_horizon = E0s[:i] # One value for each start of a home period
            E0s_futur = E0s[i:]
                
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