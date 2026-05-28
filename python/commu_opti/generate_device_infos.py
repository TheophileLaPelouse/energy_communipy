from .data.generate_data_V2 import (
    generate_profile, generate_building, get_weather_data, 
    device_activation_profile, device_power_profile, one_device_allocation, 
    list_devices
)

import datetime as dt
from random import randint

def generate_member_data_random(**kwargs) : 
    
    # define time parameters
    
    deltat = kwargs.get("deltat", 1)
    date = kwargs.get("date")
    nb_of_days = kwargs.get("nb_of_days", 1)
    if not date : 
        # Choose random date in 2020
        day_number = randint(1, 365)
        date = dt.datetime(2020, 1, 1) + dt.timedelta(days=day_number)
    date_start = date
    date_end = date + dt.timedelta(days=nb_of_days)
        
    
    build = generate_building()
    nb_people = build["nb_people"]
    states = [f"{k}{j}" for k in range(nb_people+1) for j in range(nb_people+1)]
    states = {states[i] : i for i in range(len(states))}
    profile = generate_profile(nb_people, False, deltat)
    weather_forecast, irradiance_profile = get_weather_data(date_start, date_end)
    weather_history, irradiance_history = get_weather_data(date_start, date_end, forecast=False)
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
        
        
    final_result = {}
    for device in equipments : 
        if equipments[device]["Number"] != 0 and equipments[device].get("P") != 0 : 
            # print(f"\nDevice {device} \n")
            activation_profile, when_profile, presence_profile = device_activation_profile(profile, equipments[device], deltat, nb_people)
            # print("Activation profile copmuted")
            args = {
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
            pow_profile = device_power_profile(**args)
            pow_profile["parameters"]["name"] = device
            # print("Power profile computed")
            
            final_result[device] = {"power_profile" : pow_profile, "args" : args}

    devices = {device : final_result[device]["power_profile"] for device in final_result}
    member_param = {
        'socio': [1, 1, 0, 1],
        'id_': 0,
    }
    param = {"devices" : devices, "device_options" : {"total_time" : 24, "deltat" : 1}, "parameters" : member_param}
    
    return param, final_result
    