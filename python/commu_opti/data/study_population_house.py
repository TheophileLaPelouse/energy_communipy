import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os 
import json
import sys
#%%

"""
Les variables sont : NBPIR = nombre de pièces, SURF_15 = surface et NPERC = nombre de personnes.

Pour SURF_15 :
1 : Moins de 30 m²
2 : De 30 m² à moins de 40 m² 
3 : De 40 m² à moins de 60 m² 
4 : De 60 m² à moins de 80 m² 
5 : De 80 m² à moins de 100 m² 
6 : De 100 m² à moins de 120 m² 
7 : 120 m² ou plus
"""

path_person = "/Users/theophilemounier/Documents/Stage_these/Data/data_menage/nb_room_nb_person.csv"
path_surface = "/Users/theophilemounier/Documents/Stage_these/Data/data_menage/nb_room_surface.csv"

df_person = pd.read_csv(path_person, sep=";", usecols=["NPERC", "NBPIR"])
df_surface = pd.read_csv(path_surface, sep=";", usecols=["SURF_15", "NBPIR"])
df_room = pd.read_csv(path_person, sep=";", usecols=["NBPIR"])

# On veut P(S|p), on fait probabilité totales : P(S|p) = sum_r P(S|R=r)P(R=r|p)

# Create rooms given people 

joint = df_person.groupby(['NPERC', 'NBPIR']).size()
proba_p_r = (joint/joint.sum()).reset_index(name="count_p_r")
proba_p = proba_p_r.groupby("NPERC")["count_p_r"].sum().reset_index(name="count_p")
proba_r_given_p = proba_p_r.merge(proba_p, on="NPERC")
proba_r_given_p["proba_r_given_p"] = proba_r_given_p["count_p_r"] / proba_r_given_p["count_p"]

# Create surface given rooms

joint = df_surface.groupby(['SURF_15', 'NBPIR']).size()
proba_s_r = (joint/joint.sum()).reset_index(name="count_s_r")
proba_r = proba_s_r.groupby("NBPIR")["count_s_r"].sum().reset_index(name="count_r")
proba_s_given_r = proba_s_r.merge(proba_r, on="NBPIR")
proba_s_given_r["proba_s_given_r"] = proba_s_given_r["count_s_r"] / proba_s_given_r["count_r"]

proba_s_given_p = proba_r_given_p.merge(proba_s_given_r, on="NBPIR")

# Compute surface given people

proba_s_given_p["to_sum"] = proba_s_given_p["proba_r_given_p"] * proba_s_given_p["proba_s_given_r"]
final = (proba_s_given_p.groupby(["NPERC", "SURF_15"], as_index=False)["to_sum"].sum()).rename(columns={'to_sum' : "s_given_p"})

surface = {1 : 20, 2 : 35, 3 : 50, 4 : 70, 5 : 90, 6 : 110, 7 : 140}

proba_dico = {}
for val in final.index : 
    key_people = int(final.iloc[val]["NPERC"])
    key_surf = int(final.iloc[val]["SURF_15"])
    proba = final.iloc[val]["s_given_p"]
    if not proba_dico.get(key_people) :
        proba_dico[key_people] = {}
    proba_dico[key_people][surface[key_surf]] = float(proba)
    




#%% On veut les tables de proba de chaine de markov pour les 

path_crest = "/Users/theophilemounier/Documents/Stage_these/Data/crest_data/CREST_Demand_Model_v2.3.3.xlsm"

sheet_names = [f"tpm{k}_we" for k in range(1, 7)] + [f"tpm{k}_wd" for k in range(1, 7)]

folder_path = os.path.join(os.path.dirname(__file__), "transition_matrices")
if not os.path.exists(folder_path) : 
    os.mkdir(folder_path)

#%%
for name in sheet_names : 
    df = pd.read_excel(path_crest, sheet_name=name, skiprows=9)
    cols = df.columns
    k = int(str(cols[-1]).strip()[-1])
    k = (k+1)**2
    n = len(range(0, df.index[-1], k))
    transitions = np.zeros((n, k, k))
    for i in range(0, df.index[-1], k) : 
        transitions[int(i/k), :, :] = df.iloc[i:i+k, 2:2+k].cumsum(axis=1)
    np.save(os.path.join(folder_path, name), transitions)
    
#%% Faire tourner en boucle pour avoir la probabilité de l'état initial

sys.path.append(os.path.dirname(__file__))
from utils import markov_states

probas = {}
for files in os.listdir(folder_path)[:] : 
    print("processing file : ", files)
    transitions = np.load(os.path.join(folder_path, files))
    n = transitions.shape[0]
    k = transitions.shape[1]
    profiles = []
    flag_for = True
    for _ in range(10) : 
        flag = True
        c = 0
        starting_state = 0
        while flag and c < k : 
            print(c)
            profile = markov_states(transitions, starting_state, step_number=144*1000)
            error = profile.get("Error")
            profile = profile["results"]
            if error : 
                if len(profile)/144 > 30: 
                    flag = False
                    profiles.append(profile)
                else :
                    flag = True
                    starting_state += 1
                    c += 1
            else : 
                flag = False
                flag_for = False
        if not flag_for : break
    if profiles : 
        profile = max(profiles, key=lambda x : len(x))
            
    if not flag :
        init_steps = [profile[i] for i in range(0, len(profile), 144)]
        initial_state_proba = {i: init_steps.count(i)/len(init_steps) for i in set(init_steps)}
        probas[files] = initial_state_proba
        
#%% Proba initial from crest

sheet_name = "Starting states"
skiprows = [0, 1, 2, 3, 5]
cols = ["occ", 1, 2, 3, 4, 5, 6]
df_wd = pd.read_excel(path_crest, sheet_name=sheet_name, skiprows=skiprows, nrows=55-5)
df_wd.columns = cols

df_we = pd.read_excel(path_crest, sheet_name=sheet_name, skiprows=58).drop(index=0)
df_we.columns = cols


probas = {}
for nb_people in range(6) : 
    file_we = f"tpm{nb_people+1}_we.npy"
    file_wd = f"tpm{nb_people+1}_wd.npy"
    states = [f"{k}{j}" for k in range(nb_people+1) for j in range(nb_people+1)]
    states = {states[i] : i for i in range(len(states))}
    
    probas[file_we] = [0 for _ in range(len(states))]
    probas[file_wd] = [0 for _ in range(len(states))]
    proba = 0
    for i in df_we.index : 
        occ = str(df_we["occ"][i])
        if len(occ) == 1 : 
            occ = "0" + occ
        if occ in states :
            proba += df_we[1][i]
            probas[file_we][states[occ]] = float(proba)
    proba = 0
    for i in df_wd.index : 
        occ = str(df_wd["occ"][i])
        if len(occ) == 1 : 
            occ = "0" + occ
        if occ in states :
            proba += df_wd[1][i]
            probas[file_wd][states[occ]] = float(proba)
    

with open(os.path.join(os.path.dirname(__file__),"initial_state_probabilities.json"), "w") as f: 
    json.dump(probas, f, indent = 4)
#%% Save the initial state probabilities in a json file
# probas = initial_state_probabilities
for key in probas :
    transitions = np.load(os.path.join(folder_path, key))
    k = transitions.shape[1]
    array = [0 for _ in range(k)]
    proba = None
    for i in range(k) : 
        if probas[key].get(i) :
            if proba is None : 
                proba = probas[key][i]
            else :
                proba += probas[key][i]
        array[i] = proba 
    probas[key] = array
    

with open(os.path.join(os.path.dirname(__file__),"initial_state_probabilities.json"), "w") as f: 
    json.dump(probas, f, indent = 4)


