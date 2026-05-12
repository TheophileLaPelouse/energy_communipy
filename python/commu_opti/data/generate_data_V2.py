from .utils import *
import numpy as np

import os 
import json 

# Define all the data variables (they are small so we can load them all)

if not os.path.exists(os.path.join(os.path.dirname(__file__), "devices.json")): 
    from .devices_jsonpy import list_devices
    with open(os.path.join(os.path.dirname(__file__), "devices.json"), "w") as f: 
        json.dump(list_devices, f, indent = 4)
else:
    with open(os.path.join(os.path.dirname(__file__), "devices.json"), "r") as f: 
        list_devices = json.load(f)
        list_devices = convert_numeric_keys(list_devices)
        
        
if not os.path.exists(os.path.join(os.path.dirname(__file__), "building.json")): 
    from .devices_jsonpy import building
    with open(os.path.join(os.path.dirname(__file__), "building.json"), "w") as f: 
        json.dump(building, f, indent = 4)
else:
    with open(os.path.join(os.path.dirname(__file__), "building.json"), "r") as f: 
        building = json.load(f)
        building = convert_numeric_keys(building)
        
with open(os.path.join(os.path.dirname(__file__), "initial_state_probabilities.json"), "r") as f:
    initial_state_probabilities = json.load(f)

average_people = compute_average_number(building["nb_popu_proba"])
deviation_people = compute_deviation_number(building["nb_popu_proba"], average_people)   
# print("BOnjour") 
# print(building["surface_probability"])
average_surface = {int(k): compute_average_number(v) for k, v in building["surface_probability"].items()}
# print(average_surface)
deviation_surface = {int(k): compute_deviation_number(v, average_surface[int(k)]) for k, v in building["surface_probability"].items()}    


def generate_building() : 
    
    nb_people = round(normal(average_people, deviation_people))
    if nb_people < 1 : nb_people = 1
    if nb_people > 6 : nb_people = 6
    
    surface = round(normal(average_surface[nb_people], deviation_surface[nb_people]))
    if surface < 10 : surface = 10
    
    return {"nb_people" : nb_people, "surface" : surface}

def generate_profile(nb_people, weekend, deltat, profile_0 = None) : 
    """Generate a 24 hours profile. The states are in the shape "ij" 
    where i is the number of people at home and j is the number of active people. 
    For us 06 is the same as 00 as the activity outside de home is not relevant for the energy consumption.

    Args:
        nb_people (int): Number of people in the house (between 1 and 6)
        weekend (bool): if weekend or not.
        deltat (float): in hours, minimum resolution is 10 minutes.
        profile_0 (int, optional): The initial state for the Markov chain. Defaults to None.

    Returns:
        list: A list of states representing the generated profile.
    """
    file_path = os.path.join(os.path.dirname(__file__), "transition_matrices")
    name = f"tpm{nb_people}_{'we' if weekend else 'wd'}"
    name = name + ".npy"
    # print(name)
    transitions = np.load(os.path.join(file_path, name))
    n = transitions.shape[0]
    states = [f"{k}{j}" for k in range(nb_people+1) for j in range(nb_people+1)]
    # states = {states[i] : i for i in range(len(states))}
    states_inverse = {i : states[i] for i in range(len(states))}
    
    rd = np.random.rand()
    profile0 = dicotomie_search(initial_state_probabilities[name], rd) if profile_0 is None else profile_0
    profile = markov_states(transitions, profile0)
    if profile.get("Error") : 
        print(profile["Error"])
        print("\n, Attention ! \n")
        print(profile["results"])
    profile_states = [states_inverse[s] for s in profile["results"]]
    
    data_deltat = 10/60 # 10 minutes in hours
    if deltat != data_deltat :
        # There can be a deltat difference, so we need to adapt the profile. 
        # We will do it by taking the state of the profile at the closest time step to the one we want.
        factor = deltat/data_deltat
        profile_states = [profile_states[int(i*factor)] for i in range(int(len(profile_states)/factor))]    
    if len(profile_states) < int(24/deltat) : 
        profile_states.append(profile_states[-1])

    return profile_states
        
        
def one_device_allocation(device, nb_people) :
    """
    Allocate power information to the device depending on the number of people and the different probabilities.
    """
    # Compute probability of presence of equipment
    rd_presence = rand()
    presence = rd_presence < device.get("proba", 1)
    
    # For readability purpose, we will remove the keys used for this step
    key_to_use = ["nb_proba", "types_proba", "P_types", "E_types", "net_deviation", "deviation", "power", 'proba']
    
    E_P = None
    # If there can be several devices
    if presence and device.get("nb_proba") and nb_people >= 3: 
        if device.get("types_proba") : 
            # Power probability of the different devices. So we don't keep track of the number of devices but only of the power.
            E_P = power_normal_distribution(device["nb_proba"], 
                                            device["types_proba"], 
                                            device.get("P_types", device.get("E_types"))
                                            )
            nb = -1 # Not useful anymore as included in E_P
        else : 
            # If there is one type of device, we can just compute the number of such device
            nb = round(normal_distribution_number(device["nb_proba"]))
    else : 
        nb = int(presence)
        if device.get("types_proba") and device.get("P_types", device.get("E_types")):
            # Same as above 
            E_P = power_normal_distribution({0: 1-nb, 1: nb}, 
                                            device["types_proba"], 
                                            device.get("P_types", device.get("E_types"))
                                            )
    
    # Net deviation is not relative while deviation is
    deviation = device.get("net_deviation", device.get("deviation", 0.2*device.get("power", 0)))
    if E_P is None :
        power = normal_positive(device.get("power", 0), deviation)*nb
        c= 0
        while power < 0 and c < 10 : 
            power = normal_positive(device.get("power", 0), deviation)*nb
            c += 1
    
    allocated = {
        "Number" : nb, 
    }
    
    # Different cases depending on the type of information (power or energy)    
    if device.get("E_types") : 
        allocated["E"] = E_P
    elif device.get("P_types") : 
        allocated["P"] = E_P
    elif device.get("power") : 
        allocated["P"] = power
    elif device.get("energy_needed") : 
        allocated["E"] = normal_positive(device["energy_needed"], deviation)
        
    for key in device : 
        # If there is an information related to the number of people for computing the power 
        if key.endswith("popu") : 
            name, popu = key.split("_")
            key_to_use.append(key)
            if name == "P" : 
                allocated["P"] = normal_positive(device[key][nb_people], 0.2*device[key][nb_people]) # Aléatoire le 0.2
            else : 
                # Will be used depending on the device
                allocated["popu"] = normal_positive(device[key][nb_people], deviation)
    
    for key in device : 
        if key not in key_to_use : 
            allocated[key] = device[key]
    
    return allocated

def state_to_presence(nb_people, state) : 
    """
    Translate the state of the profile into a presence state. 
    The presence state is in the form of a dictionary with the keys "awake", "asleep" and "away" 
    and the values are the number of people in each state.
    """
    # state is in the form "ij" where i is the number of people at home and j the number of active people. 
    i, j = int(state[0]), int(state[1])
    if i > j : 
        return {"awake" : j, "asleep" : i-j, "away" : nb_people-i}
    else : 
        return {"awake" : i, "asleep" : 0, "away" : nb_people-i} # Choice need to be verified in article about occupancy

def profile_to_presence(profile, nb_people) :
    # Iterate over the profile and translate it into a presence profile.
    return [state_to_presence(nb_people, state) for state in profile]

def when_to_profile(deltat, device) :
    """
    Translate the when field in devices into a list of interval 
    with the different possible states for each deltat during the day.
    """
    
    intervals = [{} for _ in range(int(24/deltat))]
    when = device.get("when", None)
    
    if not when : 
        # Always used
        union = {"awake" : 1, "asleep" : 1, "away" : 1}
        return [union for _ in range(int(24/deltat))]
    
    if when.get("time") : 
        for time_interval in when["time"] : 
            start, end, proba = time_interval
            start_index = int(round(start/deltat))
            end_index = int(round(end/deltat))
            if when.get("spec") : 
                finish_before_end = when["spec"] == "before leave"
            indices = possible_starts(end-start, range(start, end+1), deltat, device.get("cycle_length", 0), finish_before_end=finish_before_end)
            for i in indices :
                intervals[i]  = {}
                for key in when["presence_state"] : 
                    intervals[i][key] = {"proba" : proba, "time" : (start, end)}
            
    if when.get("moment") :
        translation = {"morning" : (6, 12), "afternoon" : (12, 20), "night" : (20, 6), "sleep" : (22, 6)}
        
        for moment in when["moment"] :
            start, end = translation[moment]
            start, end = round(normal(moment[0], 0.3*moment[0])), round(normal(moment[1], 0.3*moment[1]))
            if end < start : start, end = end, start
            start_index = int(round(start/deltat))
            end_index = int(round(end/deltat))
            for i in range(start_index, end_index) :
                intervals[i]  = {}
                for key in when["presence_state"] : 
                    intervals[i][key] = {"probat" : 1, "time" : (start, end)}
                    
        
    if not when.get("time") and not when.get("moment") : 
        start, end = 0, 24
        start_index = int(round(start/deltat))
        end_index = int(round(end/deltat))
        indices = possible_starts(end-start, range(start, end+1), deltat, device.get("cycle_length", 0))
        proba = when.get("proba")
        probat = when.get("probat")
        for i in indices : 
            intervals[i]  = {}
            for key in when["presence_state"] : 
                if proba : 
                    intervals[i][key] = {"proba" : proba}
                elif probat : 
                    intervals[i][key] = {"probat" : probat}
                else :  
                    intervals[i][key] = {"probat" : 1}
            
    return intervals

def device_activation_profile(profile, device, deltat, nb_people) : 
    """
    Generate the activation profile of the device depending on the presence profile and the when field of the device.
    """
    profile_presence = profile_to_presence(profile, nb_people)
    when_profile = when_to_profile(deltat, device)
    activation_profile = [0 for _ in range(int(24/deltat))]
    i = 0
    set_proba = {}
    while i < len(when_profile) : 
        presence_state = profile_presence[i]
        when = when_profile[i]
        if presence_state in when : 
            if "probat" in when[presence_state] : 
                # Has a probability of probat to be activated at each time step during the time interval
                if rand() < when[presence_state]["probat"] : 
                    activation_profile[i] = 1
                i += 1
                    
            elif "proba" in when[presence_state] and not "time" in when[presence_state] :
                # Will be activated once a day with a certain probability 
                set_proba.add(i)
                i += 1
                
            elif "proba" in when[presence_state] and "time" in when[presence_state] :
                # Will be activated once during the time interval with a certain probability
                proba = when[presence_state]["proba"]
                time_interval = when[presence_state]["time"]
                indices = possible_starts(time_interval[1]-time_interval[0], range(i, len(when_profile)), deltat, device.get("cycle_length", 0), finish_before_end=True)
                rd_indice = np.random.choice(indices)
                if rand() < proba : 
                    activation_profile[rd_indice] = 1
                i = indices[-1] + 1
                
        rd_indice = np.random.choice(list(set_proba))
        if rand() < when_profile[rd_indice][presence_state]["proba"] : 
            activation_profile[rd_indice] = 1
                
    return activation_profile    



### Device power profile generation (final steps)

def fridge_profile(device_name, allocated, deltat, total_time) : 
    E, time_active, time_inactive, V = allocated["E"], allocated["cycle_length"], allocated["time_between_cycles"], allocated["popu"]
    if device_name == 'refrigerator' : 
        power = frigo_power(E, V, time_active, time_inactive)
    else : 
        power = congelateur_power(E, V, time_active, time_inactive)
    total_cycle = time_active + time_inactive
    power_profile_needed = [power 
                            if k/deltat % total_cycle < time_active 
                            else 0 for k in range(total_time)]
    
    confort_diff = allocated.get("confort_temp", 0) # For now this key does not exist
    power_profile_confort = [power + power*allocated['increase_power']*confort_diff 
                                if k/deltat % total_cycle < time_active 
                                else 0 for k in range(total_time)]
    p_range = [(power_profile_needed[i], power_profile_confort[i]) for i in range(total_time)]
    param = {"parameters" : {"p_range" : p_range}, "type" : "flex"}
    
def white_goods_profile(device_name, allocated, deltat, when_profile, activation_profile) :
    cycle_length = allocated.get("cycle_length", 0)
    if device_name == "washing_machine" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], allocated["popu"]
        power = washing_machine_power(E, popu, cycle_length)
    elif device_name == "dishwasher" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], allocated["popu"]
        power = dishwasher_power(E, popu, cycle_length)
    elif device_name == "dryer" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], allocated["popu"]
        power = dryer_power(E, popu, cycle_length)
    elif device_name == "hoven" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], 60 # Not exact but does not change much (5%)
        power = four_power(E, popu, cycle_length)

    start_pref = []
    time_range = []
    for interval in when_profile['time'] : 
        start, end, proba = interval
        indices = possible_starts(end-start, range(int(start/deltat), int(end/deltat)+1), deltat, cycle_length, finish_before_end=True)
        for i in indices : 
            if activation_profile[i] == 1 :
                # Slow but I don't see how to accelerate it  
                start_pref.append(i)
                time_range.append((start, end))
                break
            
    white_good = {'cycle_length' : [cycle_length], # For now no variation on the cycle length, but it could be done. 
                    'power_needed' : power, 
                    "start_pref" : start_pref, 
                    "time_range" : time_range, 
                    }
    return {"parameters" : white_good, "type" : "white_good"}
        
def small_white_goods_profile(allocated, deltat, total_time, activation_profile) :
    power = allocated.get("P", 0)
    cycle_length = allocated.get("cycle_length", 0)
    if cycle_length > deltat : 
        power = power * deltat/cycle_length # Adapt the power to the cycle length
    power_profile = []
    active_time = 0
    flag = False
    for i in range(total_time) : 
        if activation_profile[i] == 1 : 
            power_profile.append(power)
            active_time += deltat 
            flag = True 
        elif flag and active_time < cycle_length :
            power_profile.append(power)
            active_time += deltat
        else : 
            power_profile.append(0)
            active_time = 0
            flag = False
    params = {"parameters" : {"power_profile" : power_profile}, "type" : "fixed"}
    return params
    

def lighting_profile(allocated, deltat, total_time, activation_profile, surface, presence_profile, nb_people) : 
    # The lighting power is cvonsidered proportional to the number of people at home and to the surface of the house.  
    power_profile = []
    for i in range(total_time) : 
        if activation_profile[i] == 1 : 
            power = allocated.get("power", 0) * surface * (presence_profile[i]['awake'] / nb_people)
        else : 
            power = 0
        power_profile.append(power)
     
    params = {"parameters" : {"power_profile" : power_profile}, "type" : "fixed"}
    return params

def water_heater_profile(allocated, deltat, total_time, activation_profile, nb_people) :
    # The water heater needs to provide a certain amount of energy
    energy_needed = allocated["E"] * nb_people
    P = allocated['P']
    params = {"parameters" : {"energy_needed" : energy_needed, "power" : P}, "type" : "water_heater"}
    return params

def heating_power_model(T, presence_profile, weather, R1, R2, C, total_time, deltat, typ, **options) : 
    T_in = []
    for t in range(total_time) : 
        if presence_profile[t].get("awake", 0) > 0 : 
            T_in.append(T['awake'])
        elif presence_profile[t].get("asleep", 0) > 0 : 
            T_in.append(T['asleep'])
        else : 
            T_in.append(T['away'])
    T_out = weather["forecast"]["temperature"]
    T_b = options.get("T_b", T_out[0]) # Initial temperature of the inertia of the building, we will update it at each time step
    power_profile = [0]
    for t in range(total_time-1) :
        T_b, flux = thermal_model_flux(T_b, T_out[t+1], T_in[t+1], R1, R2, C, deltat)
        power_profile.append(flux)
        
    if typ == "resistor" :
        carnot = [1 for k in range(total_time)]
    elif typ == "heat_pump" :
        carnot = [max(1, (T_in[k]+273.15) / (T_in[k]- T_out[k])) for k in range(total_time)]
    # elif not heating : 
    #     carnot = [(T_in[k]+273.15) / (T_out[k] - T_in[k]) for k in range(total_time)]
        
    power_profile[0] = power_profile[-1] # We consider that the power needed at the first time step is the same as the one needed at the second time step, but it could be done differently.
    return power_profile, carnot
    
    
def heating_system_profile(allocated, deltat, total_time, surface, presence_profile, weather, **options) :
    # 2R1C model, we compute first the power range for a certain temperature
    T_wanted = {"awake" : normal_positive(allocated["T_wanted_awake"], 1), 
                "asleep" : normal_positive(allocated["T_wanted_asleep"], 1), 
                "away" : normal_positive(allocated["T_wanted_away"], 1)}
    T_min = {
        "awake" : 16, 
        "asleep" : 14,
        "away" : 10
    }
    
    R_DPE = power_normal_distribution({0: 1-allocated['Number'], 1: allocated['Number']}, 
                                        allocated["DPE_proba"], 
                                        allocated["R_DPE"])
    C = normal_distribution_number(allocated["C_proba"])
    R1 = R_DPE * surface * allocated['coef_R']
    R2 = R_DPE * surface * (1-allocated['coef_R'])
    T0 = options.get("T0", T_wanted["asleep"])
    
    typ = allocated.get("type", "resistor")
    power_confort_forecast, carnot = heating_power_model(T_wanted, presence_profile, weather, R1, R2, C, total_time, deltat, typ, **options)
    power_min_forecast, carnot = heating_power_model(T_min, presence_profile, weather, R1, R2, C, total_time, deltat, typ, **options)
    
    efficiency = normal_positive(allocated.get("efficiency", 0.5), 0.1)
    
    p_range_forecast = [(power_min_forecast[i]*efficiency*carnot[i], 
                         power_confort_forecast[i]*efficiency*carnot[i]) 
                        for i in range(total_time)]
    params = {"parameters" : {"p_range" : p_range_forecast}, "type" : "flex"}
    
    if weather.get("history") : 
        presence_profile_history  = options.get("presence_profile_history", presence_profile)
        power_confort_history, carnot_history = heating_power_model(T_wanted, presence_profile_history, weather, R1, R2, C, total_time, deltat, typ, **options)
        power_min_history, carnot_history = heating_power_model(T_min, presence_profile_history, weather, R1, R2, C, total_time, deltat, typ, **options)
        p_range_history = [(power_min_history[i]*efficiency*carnot_history[i], 
                            power_confort_history[i]*efficiency*carnot_history[i]) 
                           for i in range(total_time)]
        params["parameters"]["p_range_history"] = p_range_history
        
    return params
    
def clim_profile(allocated, deltat, total_time, surface, presence_profile, weather, **options)  :
    T_out_forecast = weather["forecast"]["temperature"]
    T_in_forecast = []
    flux_forecast = []
    T_activation = normal_positive(allocated.get("T_activation", 25), 2)
    T_minus = normal_positive(allocated.get("T_minus", -7), 2)
    T_b = options.get("T_b", T_out_forecast[0]) # Initial temperature of the inertia of the building, we will update it at each time step
    
    R1, R2, C = options["R1"], options["R2"], options["C"]
    for t in range(total_time) :
        if presence_profile[t].get("awake", 0) > 0 or presence_profile[t].get("asleep", 0) > 0 : 
            if T_out_forecast[t] > T_activation - T_minus : 
                T_in_forecast.append(T_activation + T_minus)
                T_b, flux = thermal_model_flux(T_b, T_out_forecast[t], T_in_forecast[-1], R1, R2, C, deltat)
                flux_forecast.append(flux)
            elif T_out_forecast[t] > T_activation : 
                T_in_forecast.append(T_activation)
                T_b, flux = thermal_model_flux(T_b, T_out_forecast[t], T_in_forecast[-1], R1, R2, C, deltat)
                flux_forecast.append(flux)
            else : 
                flux_forecast.append(0)
                T_b, T_in = thermal_model_Tin(T_b, T_out_forecast[t], flux_forecast[-1], R1, R2, C, deltat)
                T_in_forecast.append(T_in)
                
        else : 
            flux_forecast.append(0)
            T_b, T_in = thermal_model_Tin(T_b, T_out_forecast[t], flux_forecast[-1], R1, R2, C, deltat)
            T_in_forecast.append(T_in)
            
            
            
    

    
def device_power_profile(activation_profile, when_profile, presence_profile, device_name, allocated, surface, nb_people, deltat, **options) : 
    """
    Generate the power profile of the device depending on the activation profile and the device characteristics.
    """
    
    total_time = len(activation_profile)
    if device_name in ['refrigerator', 'congelateur'] : 
        # E, cycle_lenght, time_between_cycles 
        params = fridge_profile(device_name, allocated, deltat, total_time)
    
    if device_name in ['TV', 'fix_computer', 'fixed_load_parameters'] : 
        power = allocated.get("P", 0)
        power_profile = [power if activation_profile[i] == 1 else 0 for i in range(total_time)]
        params = {"parameters" : {"power_profile" : power_profile}, "type" : "fixed"}
        
    if device_name in ['washing_machine', 'dishwasher', 'dryer', 'plaque_electrique', 'hoven'] : 
        params = white_goods_profile(device_name, allocated, deltat, when_profile, activation_profile)
    
    if device_name in ['toaster', 'boiler', 'small_object_charge', 'microwave'] : 
        params = small_white_goods_profile(allocated, deltat, total_time, activation_profile)
        
    if device_name == 'lighting' : 
        params = lighting_profile(allocated, deltat, total_time, activation_profile, surface, presence_profile, nb_people)
        
    if device_name == 'water_heater' : 
        params = water_heater_profile(allocated, deltat, total_time, activation_profile, nb_people)
        
    if device_name == 'heating_system' : 
        params = heating_system_profile(allocated, deltat, total_time, activation_profile, surface, presence_profile, nb_people, **options)
    
    if device_name == 'climatisation' : 
        params = clim_profile(allocated, deltat, total_time, surface, presence_profile, nb_people, **options)
    
    return params
    
            
