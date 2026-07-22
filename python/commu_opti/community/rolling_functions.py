from . import np, pyo


def white_goods_rolling(dico, total_time, current_time_index, d, new_params, **kwargs) :
    
    previous_to_change = False
    old_dico = dico.copy()
    
    if dico.get('length', 0) > 0 : 
        to_supply = dico['to_supply']
        length = dico['length']
        for k in range(length) : 
            to_supply[k] = to_supply[k+1]
        length -= 1
        dico['length'] = length
        dico['to_supply'] = to_supply
        previous_to_change = True
        keep_id_0=True
        
    else :
        if pyo.value(d.mod.Pcons[0]) > 0 and not kwargs.get("reset", True): 
            length = d.cycle_length[0]
            # print("length", length, "pcons", pyo.value(d.mod.Pcons[0]))
            to_supply = np.zeros(total_time)
            to_supply[0:length] = d.mod.p_range[0, 0].value
            dico['length'] = length
            dico['to_supply'] = to_supply
            keep_id_0=False
            previous_to_change=True
        else : 
            keep_id_0=True
    
    # print(f"\n start of rolling, {current_time_index=}, {dico.get('length', 0)=}, {dico.get('to_supply', None)=}, {keep_id_0=}")
        
    futur_starts = dico.get('futur_starts', [])
    futur_lengths = dico.get('futur_lengths', [])
    futur_time_range = dico.get('futur_time_range', [])
    futur_power_needed = dico.get('futur_power_needed', [])
    
    # Donc on remplace ce qu'on avait avant par, on change premier et dernier ou on ajoute. Et on change les trucs de base si demandé indice par indice.
    # Dans device il faudra donc d'abord changer le premiers, ensuite changer les autres, puis changer le derniers
    
    to_add = {}
    last_to_change = False
    last = {
        "start_pref" : d.start_pref[-1] if len(d.start_pref) > 0 else 0,
        "time_range" : d.time_range[-1] if len(d.time_range) > 0 else [0, 0],
        "cycle_length" : d.cycle_length[d.n_set-1],
        "power_needed" : d.mod.p_range[len(d.mod.t_set)-1, 0].value if len(d.mod.t_set) > 0 else 0
    }
    
    if (len(futur_starts) > 0  
        and futur_starts[0] + futur_time_range[0][0] == current_time_index[1]): 
        to_add["start_pref"] = futur_starts[0] + futur_time_range[0][0]
        to_add["time_range"] = [0, 0]
        to_add["cycle_length"] = 0
        to_add["power_needed"] = futur_power_needed[0]

    elif (len(futur_starts) > 0  
        and futur_starts[0] + futur_time_range[0][0] <= current_time_index[1]
        and futur_starts[0] > current_time_index[1]): 
        last_to_change = True
        last["start_pref"] = current_time_index[1]
        last["time_range"] = [current_time_index[1] - futur_starts[0] + futur_time_range[0][0], 0] # Peut être erreur ici
        last["cycle_length"] += 1 if last["cycle_length"] < futur_lengths[0] - 1 else 0

    elif (len(futur_starts) > 0  
        and futur_starts[0] <= current_time_index[1]
        and futur_starts[0] + futur_time_range[0][1] > current_time_index[1]):
        last_to_change = True
        last["start_pref"] = futur_starts[0]
        last["time_range"] = [futur_time_range[0][0], current_time_index[1] - futur_starts[0]]
        last["cycle_length"] += 1 if last["cycle_length"] < futur_lengths[0] - 1 else 0
        
    elif (len(futur_starts) > 0
        and futur_starts[0] + futur_time_range[0][1] <= current_time_index[1]
        and futur_starts[0] + futur_time_range[0][1] + futur_lengths[0] > current_time_index[1]):
        last_to_change = True
        last["time_range"] = [futur_time_range[0][0], futur_time_range[0][1]]
        last["cycle_length"] += 1 if last["cycle_length"] < futur_lengths[0] - 1 else 0

    elif (len(futur_starts) > 0
            and futur_starts[0] + futur_time_range[0][1] + futur_lengths[0] == current_time_index[1]):
        futur_lengths.pop(0)
        futur_starts.pop(0)
        futur_time_range.pop(0)
        futur_power_needed.pop(0)
    
    other_changes = {
        "start_pref" : kwargs.get(d.name, {}).get("start_pref", None), 
        "time_range" : kwargs.get(d.name, {}).get("time_range", None),
        "cycle_length" : kwargs.get(d.name, {}).get("cycle_length", None),
        "power_needed" : kwargs.get(d.name, {}).get("power_needed", None)
    }
    
    
        # print(f"Values to update : {time_range=}, {cycle_length=}, {start_pref=}, {power_needed=}")
    new_params[d.name] = {
        "last_to_change" : last_to_change,
        "last" : last,
        "to_add" : to_add,
        "other_changes" : other_changes,
        "keep_id_0" : keep_id_0
    }
    if previous_to_change :
        new_params[d.name]["previous_cycle"] = dico['to_supply']
        
    # print("\nIn rolling function:", d.name, new_params.get(d.name, {}))
    # print("Old dico:", old_dico, "New dico:", dico)

        
def EV_rolling(current_time_index, dico, new_params, d, **kwargs) :
    # print(f"[EV_rolling] {d.name=} {current_time_index=}")
    if not new_params.get(d.name):
        new_params[d.name] = {}
    E0 = kwargs.get('E0', pyo.value(d.mod.E[1]))
    
    # time_home, E0s, E_min
    
    # End >= Emin_futur[0] - T*P
    time_home = d.time_home
    E0s = d.E0
    E0s[0] = E0
    Emins = d.E_min
    futur_time_home = dico.get('futur_time_home', [])
    futur_E0s = dico.get('futur_E0s', [])
    futur_Emins = dico.get('futur_Emins', [])
    if time_home[0][1] <= current_time_index[0] and len(time_home) > 1 and time_home[1][0] > current_time_index[0] :
        # print(f"[EV_rolling] removing past home slot for {d.name}")
        time_home.pop(0)
        Emins.pop(0)
        
    if time_home[0][0] == current_time_index[0] and time_home[0][0] != 0 : 
        E0s = [E0s[k+1] if k !=0 else E0s[k] for k in range(len(E0s)-1)]
        
    if len(futur_time_home) > 0 and futur_time_home[0][0] == current_time_index[1] : 
        # To verify but should be ok to just add futur values, if they are too high they just won't be used
        E0s.append(futur_E0s[0])
        Emins.append(futur_Emins[0])
        time_home.append(futur_time_home[0])
        futur_time_home.pop(0)
        futur_E0s.pop(0)
        futur_Emins.pop(0)
            
    new_params[d.name]["time_home"] = time_home
    new_params[d.name]["E0s"] = E0s
    new_params[d.name]["E_min"] = Emins
    
    E_end_possible = [sum(futur_Emins[k] 
                         - (futur_time_home[k][1] - futur_time_home[k][0])*d.p_range_bat[1]*d.deltat*d.charge_eff 
                     for k in range(u+1)) for u in range(len(futur_Emins))]
    if E_end_possible : 
        E_end_min = max(E_end_possible)
        new_params[d.name]["E_end"] = E_end_min
    else : 
        new_params[d.name]["E_end"] = E0
        
    # print("\ndico", dico)
    # print("\nnew_params", new_params[d.name])