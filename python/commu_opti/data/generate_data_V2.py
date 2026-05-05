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

def generate_profile(nb_people, weekend, deltat) : 
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
    i = 0
    proba = 0
    while i < len(states) and rd > proba:
        proba += initial_state_probabilities[name].get(i, 0)
        i += 1
    profile0 = i-1
    profile = markov_states(transitions, profile0)
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
        