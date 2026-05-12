from .utils import *
import numpy as np

import os 
import json 

if not os.path.exists(os.path.join(os.path.dirname(__file__), "devices.json")): 
    from .devices_jsonpy import list_devices
    with open(os.path.join(os.path.dirname(__file__), "devices.json"), "w") as f: 
        json.dump(list_devices, f, indent = 4)
else:
    with open(os.path.join(os.path.dirname(__file__), "devices.json"), "r") as f: 
        list_devices = json.load(f)
        
        
if not os.path.exists(os.path.join(os.path.dirname(__file__), "building.json")): 
    from .devices_jsonpy import building
    with open(os.path.join(os.path.dirname(__file__), "building.json"), "w") as f: 
        json.dump(building, f, indent = 4)
else:
    with open(os.path.join(os.path.dirname(__file__), "building.json"), "r") as f: 
        building = json.load(f)
        
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
    print(name)
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
    rd_presence = rand()
    presence = rd_presence < device["proba"]
    
    key_to_use = ["nb_proba", "type_proba", "P_types", "E_types", "net_deviation", "devitation", "power"]
    
    E_P = None
    if presence and device.get("nb_proba") and nb_people >= 3: 
        if device.get("type_proba") : 
            E_P = power_normal_distribution(device["nb_proba"], 
                                            device["type_proba"], 
                                            device.get("P_types", device.get("E_types"))
                                            )
        else : 
            nb = normal_distribution_number(device["nb_proba"])
    else : 
        nb = int(presence)
        if device.get("type_proba") : 
            E_P = power_normal_distribution({0: 1-nb, 1: nb}, 
                                            device["type_proba"], 
                                            device.get("P_types", device.get("E_types"))
                                            )
    
    deviation = device.get("net_deviation", device.get("devitation", 0.2*device.get("power", 0)))
    if E_P is None :
        power = normal(device.get("power", 0), deviation)*nb
    
    allocated = {
        "Number" : nb, 
    }
        
    if device.get("E_types") : 
        allocated["E"] = E_P
    elif device.get("P_types") : 
        allocated["P"] = E_P
    elif device.get("power") : 
        allocated["P"] = power
    elif device.get("energy_needed") : 
        allocated["E"] = normal(device["energy_needed"], deviation)
        
    for key in device : 
        if key.endswith("popu") : 
            name, popu = key.split("_")
            key_to_use.append(key)
            if name == "P" : 
                allocated["P"] = normal(device[key][nb_people], 0.2*device[key][nb_people]) # Aléatoire le 0.2
            else : 
                allocated["popu"] = normal(device[key]["nb_people"], deviation) # Aléatoire le 0.2
    
    for key in device : 
        if key not in key_to_use : 
            allocated[key] = device[key]
    
    return allocated

def state_to_presence(nb_people, state) : 
    # state is in the form "ij" where i is the number of people at home and j the number of active people. 
    i, j = int(state[0]), int(state[1])
    if i > j : 
        return {"awake" : j, "asleep" : i-j, "away" : nb_people-i}
    else : 
        return {"awake" : i, "asleep" : 0, "away" : nb_people-i} # Choice need to be verified in article about occupancy

def profile_to_presence(profile, nb_people) :
    return [state_to_presence(nb_people, state) for state in profile]

def when_to_profile(deltat, device) :
    """
    Translate the when field in devices into a list of interval 
    with the different possible states for each deltat during the day.
    """
    
    intervals = [{} for _ in range(int(24/deltat))]
    when = device.get("when", None)
    
    if not when : 
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
                    intervals[i][key] = {"proba" : 1}
            
    return intervals

def device_activation_profile(profile, device, deltat, nb_people) : 
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
                if rand() < when[presence_state]["probat"] : 
                    activation_profile[i] = 1
                i += 1
                    
            elif "proba" in when[presence_state] and not "time" in when[presence_state] : 
                set_proba.add(i)
                i += 1
                
            elif "proba" in when[presence_state] and "time" in when[presence_state] :
                proba = when[presence_state]["proba"]
                time_interval = when[presence_state]["time"]
                indices = possible_starts(time_interval[1]-time_interval[0], range(i, len(when_profile)), deltat, device.get("cycle_length", 0), finish_before_end=True)
                rd_indices = np.random.choice(indices, replace=False, size=len(indices))
                for j in rd_indices : 
                    if rand() < proba : 
                        activation_profile[j] = 1
                        break 
                i = indices[-1] + 1
                
    return activation_profile    


        
    
            
