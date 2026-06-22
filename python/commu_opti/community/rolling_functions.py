from . import np, pyo


def white_goods_rolling(dico, total_time, current_time_index, d, new_params, **kwargs) :

    if dico.get('length', 0) > 0 : 
        to_supply = dico['to_supply']
        length = dico['length']
        for k in range(length) : 
            to_supply[k] = to_supply[k+1]
        length -= 1
        dico['length'] = length
        dico['to_supply'] = to_supply
        
        start_pref = kwargs.get(d.name, {}).get(
            'start_pref', [d.start_pref[k] for k in range(len(d.start_pref)-1)]
            )
        time_range = kwargs.get(d.name, {}).get(
            'time_range', [d.time_range[k] for k in range(len(d.time_range)-1)]
            )
        cycle_length = kwargs.get(d.name, {}).get(
            'cycle_length', [d.cycle_length[k] for k in range(len(d.cycle_length)-1)]
            )
    else :
        if pyo.value(d.mod.Pcons[0]) > 0 : 
            length = d.cycle_length[0]
            to_supply = np.zeros(total_time)
            to_supply[0:length] = d.p_range[0, 0]
            dico['length'] = length
            dico['to_supply'] = to_supply
            
            start_pref = kwargs.get(d.name, {}).get(
                'start_pref', [d.start_pref[k+1] for k in range(len(d.start_pref)-1)]
                )
            time_range = kwargs.get(d.name, {}).get(
                'time_range', [d.time_range[k+1] for k in range(len(d.time_range)-1)]
                )
            cycle_length = kwargs.get(d.name, {}).get(
                'cycle_length', [d.cycle_length[k+1] for k in range(len(d.cycle_length)-1)]
                )
        else : 
            start_pref = kwargs.get(d.name, {}).get(
                'start_pref', [d.start_pref[k] for k in range(len(d.start_pref)-1)]
                )
            time_range = kwargs.get(d.name, {}).get(
                'time_range', [d.time_range[k] for k in range(len(d.time_range)-1)]
                )
            cycle_length = kwargs.get(d.name, {}).get(
                'cycle_length', [d.cycle_length[k] for k in range(len(d.cycle_length)-1)]
                )
            
    if dico.get('length', 0) > 0 :
        if not new_params.get(d.name):
            new_params[d.name] = {}
        new_params[d.name]["previous_cycle"] = dico['to_supply']
        
    n_set = len(start_pref)
    
    # new_params["start_pref"], new_params["cycle_length"], new_params["time_range"], new_params["power_needed"]
    futur_starts = dico.get('futur_starts', [])
    futur_lengths = dico.get('futur_lengths', [])
    futur_time_range = dico.get('futur_time_range', [])
    if (len(futur_starts) > 0  
        and futur_starts[0] + futur_time_range[0][0] == current_time_index[1]): 
        start_pref.append(futur_starts[0])
        time_range.append([0, 0])
        cycle_length.append(1)
        
    elif (len(futur_starts) > 0  
        and futur_starts[0] + futur_time_range[0][0] > current_time_index[1]
        and futur_starts[0] > current_time_index[1]): 
        start_pref[-1] = current_time_index[1]
        time_range[-1] = [current_time_index[1] - futur_starts[0] + futur_time_range[0][0], 0]
        cycle_length[-1] += 1 if cycle_length[-1] < futur_lengths[0] else 0
        
    elif (len(futur_starts) > 0  
        and futur_starts[0] <= current_time_index[1]
        and futur_starts[0] + futur_time_range[0][1] > current_time_index[1]):
        start_pref[-1] = futur_starts[0]
        time_range[-1] = [futur_starts[0] + futur_time_range[0][0], current_time_index[1] - futur_starts[0]]
        cycle_length[-1] += 1 if cycle_length[-1] < futur_lengths[0] else 0
        
    elif (len(futur_starts) > 0
        and futur_starts[0] + futur_time_range[0][1] <= current_time_index[1]
        and futur_starts[0] + futur_time_range[0][1] + futur_lengths[0] > current_time_index[1]):
        time_range[-1] = [futur_time_range[0][0], futur_time_range[0][1]]
        cycle_length[-1] += 1 if cycle_length[-1] < futur_lengths[0] else 0
        
    elif (len(futur_starts) > 0
            and futur_starts[0] + futur_time_range[0][1] + futur_lengths[0] == current_time_index[1]):
        futur_lengths.pop(0)
        futur_starts.pop(0)
        futur_time_range.pop(0)
        
    if len(futur_starts) > 0 : 
        new_params[d.name] = {
            "start_pref" : start_pref,
            "time_range" : time_range,
            "cycle_length" : cycle_length,
            "power_needed" : d.p_range[0, 0],
        }
        
    if kwargs.get("remember", False) : 
        if not d.memory.get("start_pref") : 
            d.memory["start_pref"] = {}
        d.memory['start_pref'][current_time_index[0]] = start_pref
        
def EV_rolling(current_time_index, dico, new_params, d) :
    if not new_params.get(d.name):
        new_params[d.name] = {}
    E0 = pyo.value(d.mod.E[0])
    new_params[d.name]["E0"] = E0
    
    # time_home, E0s, E_min
    
    # End >= Emin_futur[0] - T*P
    time_home = d.time_home
    E0s = d.E0
    Emins = d.Emin
    futur_time_home = dico.get('futur_time_home', [])
    futur_E0s = dico.get('futur_E0s', [])
    futur_Emins = dico.get('futur_Emins', [])
    if time_home[0][1] <= current_time_index[0] and len(time_home) > 1 and time_home[1][0] > current_time_index[0] :
        time_home.pop(0)
        Emins.pop(0)
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
    
    E_end_min = max((sum(futur_Emins[k] 
                         - (futur_time_home[k][1] - futur_time_home[k][0])*d.p_range_bat[1]*d.deltat*d.charge_eff) 
                     for k in range(u)) for u in range(len(futur_Emins)))
    new_params[d.name]["E_end"] = E_end_min