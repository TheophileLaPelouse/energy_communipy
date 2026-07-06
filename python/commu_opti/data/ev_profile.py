from .utils import normal, rand, choice, convert_numeric_keys, dicotomie_search, isnan
import json
import os


with open(os.path.join(os.path.dirname(__file__), "ev_travel_statistics.json"), "r") as f:
    ev_stat = json.load(f)
    ev_stat = convert_numeric_keys(ev_stat)

def possible_travels(presence_profile, deltat) :
    """"
    We want to determine each time there is a travel outside the home that could be made using the EV.
    For this we consider that there is a travel if their is a start and an end.
    Start define as away + 1, end defined as away - 1.
    So this does not consider that there can be exchange in a same time step between people.
    
    When there is several possibilties, we choose at random between them.
    """

    start = 0
    start_stack = []
    possible_travels = []
    
    for i in range(len(presence_profile)) :
        if i == 0 : 
            if presence_profile[i]['away'] > 0 : 
                start += 1
                start_stack.append([i, -1])
        else : 
            if presence_profile[i]['away'] > presence_profile[i-1]['away'] : 
                start += presence_profile[i]['away'] - presence_profile[i-1]['away']
                start_stack.append([i, presence_profile[i]['away'] - presence_profile[i-1]['away']])
            elif presence_profile[i]['away'] < presence_profile[i-1]['away'] : 
                time_start, nb_people = start_stack[-1]
                possible_travels.append((time_start, i))
                if nb_people > 1 : 
                    start_stack[-1][1] -= 1
                if nb_people == 1 : 
                    start_stack.pop()
                start -= 1
                
    if start > 0 : 
        possible_travels.append((-1, len(presence_profile)//deltat+1))
                
    # How much travels is possible is decided by the number of following end and start.
    
    sorted_end = sorted(possible_travels, key=lambda x: x[1])
    sorted_start = sorted(possible_travels, key=lambda x: x[0])

    i, j = 0, 0
    while i < len(sorted_start) and j < len(sorted_end) :
        if sorted_end[j][1] > sorted_start[i][0] : 
            i += 1
        elif sorted_end[j][1] <= sorted_start[i][0] : 
            j += 1
        
    travellers = [{} for k in range(100)]
    traveller_id = 0
    max_id = 0
    i, j = 0, 0
    while i < len(sorted_start) and j < len(sorted_end) :
        if sorted_start[i] == sorted_end[j] and i==j :
            if not travellers[traveller_id] : 
                traveller = {"start" : [sorted_start[i][0]], "end" : [sorted_end[j][1]]}
                travellers[traveller_id] = traveller
            else : 
                travellers[traveller_id]["start"].append(sorted_start[i][0])
                travellers[traveller_id]["end"].append(sorted_end[j][1])
            i += 1
            j += 1
        elif sorted_start[i][0] < sorted_end[j][1] : 
            if not travellers[traveller_id] : 
                traveller = {"start" : [sorted_start[i][0]], "end" : []}
                travellers[traveller_id] = traveller
                # traveller_id += 1
            else :
                travellers[traveller_id]["start"].append(sorted_start[i][0])
            traveller_id += 1
            if traveller_id > max_id : max_id = traveller_id
            i += 1
            
        elif sorted_start[i][0] >= sorted_end[j][1] :
            traveller_id -= 1
            travellers[traveller_id]["end"].append(sorted_end[j][1])
            j += 1
            
    if j < len(sorted_end) :
        while j < len(sorted_end) :
            traveller_id -= 1
            travellers[traveller_id]["end"].append(sorted_end[j][1])
            j += 1
    if max_id == 0 and travellers[0] : max_id = 1
    travellers = travellers[:max_id]
        
    if not travellers :
        return [], 0, [], []
    
    # travellers is a list of possible travelers with the first one having the least possible travels within each possible time interval.
    
    nb_travels_possible = [1 for k in range(len(travellers))]
    js = [0 for k in range(len(travellers))]
    
    nb_travels_parts = [0 for k in range(len(travellers[0]["start"]))]
    depths = [0 for k in range(len(travellers[0]["start"]))]
    
    # possible_travels_bis = set()
    for k in range(len(travellers[0]["start"])) :
        js[0] = k
        # nb_travels_possible[0] += 1
        nb_travels_parts[k] = 1
        i = 1
        # possible_travels_bis.add((travellers[0]["start"][k], travellers[0]["end"][js[0]]))
        while i < len(travellers) :
            previous_value = nb_travels_possible[i]
            while js[i] < len(travellers[i]["start"]) and travellers[i]["start"][js[i]] < travellers[i-1]["end"][js[i-1]] :
                nb_travels_possible[i] += 1
                js[i] += 1
            if js[i] == len(travellers[i]["start"]) : js[i] -= 1
            if nb_travels_possible[i] == previous_value : 
                depths[k] = i
                break
            if nb_travels_possible[i] != previous_value : 
                nb_travels_possible[0] += nb_travels_possible[i] - previous_value - 1
                nb_travels_parts[k] += nb_travels_possible[i] - previous_value - 1
            i += 1
        if i == len(travellers) :
            depths[k] = i
        
    nb_travels_max = sum(nb_travels_parts)
    return travellers, nb_travels_max, nb_travels_parts, depths    

def possible_travels_with_nb_travels(nb_travels, nb_travels_max, nb_travels_parts) : 
    """ 
    Select a subset of possible travels based on the desired number of travels.
    For this we use the fact that there is only one EV and so it should have a travel end before the next travel start.
    
    Idea, name each possible travelers, if there is a possible conflict between two travels.
    """
    
            
            
    # We have a list of groups with nb_travels_parts[k] possible travels,
    # so we want to select n value in each group such that sum(n) = nb_travels.
    # We can do this by first selecting the group and then the travels within the group.
    
    chosen_travels = []
    travel_per_group = [0 for k in range(len(nb_travels_parts))]
    updated_parts = nb_travels_parts[:]
    
    def gen_proba_groups(nb_travels_parts, nb_travels_max) :
        proba_groups = [nb_travels_parts[k]/nb_travels_max for k in range(len(nb_travels_parts))]
        return proba_groups
    
    for k in range(nb_travels) :
        rd = rand()
        proba_groups = gen_proba_groups(updated_parts, nb_travels_max - k)
        proba = proba_groups[0]
        i = 1
        while rd > proba : 
            proba += proba_groups[i]
            i += 1
        updated_parts[i-1] -= 1
        travel_per_group[i-1] += 1
        
    return travel_per_group

def choose_travels_per_group(travellers, group, nb_wanted, depth) : 

    start_mins = [travellers[0]["start"][group]]
    end_maxs = [travellers[0]["end"][group]]
    i = 0
    js = [[0, 0] for k in range(depth)]
    
    def get_travel_depth(travellers, depth, start_min, end_max, no_append=False) :
        while js[depth][0] < len(travellers[depth]["start"]) and travellers[depth]["start"][js[depth][0]] < start_min :
            js[depth][0] += 1
        js[depth][1] = js[depth][0]
        while js[depth][1] < len(travellers[depth]["end"]) and travellers[depth]["end"][js[depth][1]] < end_max :
            js[depth][1] += 1
        if js[depth][1] > js[depth][0] :
            js[depth][1] -= 1
           
        if not no_append : 
            start_mins.append(travellers[depth]["start"][js[depth][0]])
            end_maxs.append(travellers[depth]["end"][js[depth][1]])
            
    get_travel_depth(travellers, 0, start_mins[0], end_maxs[0], no_append=True)
    for i in range(1, depth) :
        get_travel_depth(travellers, i, start_mins[i-1], end_maxs[i-1])
        
    i = 0
    while i < depth and js[i][1] - js[i][0] + 1 < nb_wanted : 
        i += 1
    if i == depth : 
        i -= 1
        nb_wanted = js[i][1] - js[i][0] + 1
    travels_to_choose = [k for k in range(js[i][0], js[i][1]+1)]
    chosen = choice(travels_to_choose, nb_wanted, replace=False)
    travels = []
    for k in chosen :
        if k == js[i][0] == js[i][1] : 
            start = choice(start_mins)
            end = choice(end_maxs)
        if k == js[i][0] : 
            start = choice(start_mins)
            end = travellers[i]["end"][k]
        elif k == js[i][1] : 
            start = travellers[i]["start"][k]
            end = choice(end_maxs)
        else :
            start = travellers[i]["start"][k]
            end = travellers[i]["end"][k]
        travels.append((start, end))
    return travels
       
def EV_profile(allocated, presence_profile, deltat, bypass=False) : 
    """
    Depending on E, we have in the stats the probability of moving or not that day, only for the day. 
    Then we compute the possible travels during the day.
    Depending on the number of travels, we compute possible nb of travels.
    For each travel, we compute the possible length and power needed for the travel.
    -> Constraint on minimum power at each time and power when returning home.
    """
    # power in kW in the data
    E = allocated["E"]
    avg, ecart = ev_stat["travel_proba"][round(E/10)] # standard deviation small so we don't consider it.
    all_travels = []
    if rand() < avg or bypass: 
        travellers, nb_travels_max, nb_travels_parts, depths = possible_travels(presence_profile, deltat)
        nb_travel_proba = ev_stat['nb_travels_proba']
        nbs_proba = [0]
        nb_max = min(5, nb_travels_max)
        for k in range(1,6) :
            nbs_proba.append(nbs_proba[-1] + nb_travel_proba[k])
            
        if nb_max < 5 :
            nbs_proba = [proba * nb_max/5 for proba in nbs_proba[:nb_max+1]]
        
        nb_travels = dicotomie_search(nbs_proba, rand())
        
        travel_per_group = possible_travels_with_nb_travels(nb_travels, nb_travels_max, nb_travels_parts)
        travels = []
        for k in range(len(travel_per_group)) :
            if travel_per_group[k] > 0 : 
                travels += choose_travels_per_group(travellers, k, travel_per_group[k], depths[k])
        
        # Sometimes we have some weird cases where end and start are inversed. Should be fixed in the future but for now : 
        for k in range(len(travels)) :
            start, end = travels[k]
            if end < start : 
                travels[k] = (end, start)
        
        travels = sorted(travels, key=lambda x: x[0]) # sort travels by start time
        
        # Now get the power for each travel
        
        # "parameters" : {
        #                 "p_range" : p_range, 
        #                 "E_range" : [soc_min, soc_max],
        #                 "time_home" : time_home, 
        #                 "E0s" : E0s,
        #                 "E_min" : Emin, 
        #                 "E_end" : Emin[0]
        #             }, 
        #             "type" : "EV"
        
        p_range = [allocated["power_neg"]*1000, allocated["power_pos"]*1000] # If can't discharge put 0 at power min. Otherwise only positive values are wanted.
        E_range = [0.2*E*1000, 0.8*E*1000] 
        
        E_min_min = 0.2*E*1000*(1 + 0.2) 
        energy_travels = []
        for start, end in travels :
            length = round((end - start)*deltat) # in hour
            if length > 18 : length = 18
            if E >= 75 : E = 74.9
            power_avg = ev_stat["power_by_capacity_length"][round(E/10)][length][0] # in kW
            var = ev_stat["power_by_capacity_length"][round(E/10)][length][1]
            if not isnan(var) : 
                power = normal(power_avg, var**0.5)*1000
            else : 
                power = power_avg*1000
            power = -power # It was computed on the vehicle side, here it is on the house side.
            if power*length > (E_range[1] - E_range[0]) : 
                power = (E_range[1] - E_range[0])/length*0.9
            energy_travels.append(power*length)
            
        
        Emin = [min(energy_travels[k] + E_min_min, E_range[1]) for k in range(len(energy_travels))] # fill with the energy needed for the travels with a minimum of 20% of the capa
        E0s = [0.5*E*1000] + [-energy_travels[k] for k in range(len(energy_travels))] 
        E_end = [E0s[0]] # Look at the definitions
        # print("energy_travels", energy_travels, "E0s", E0s, "Emin", Emin)
        
        time_home = []
        for k in range(len(travels)) :
            if k==0 and travels[k][0] > 0 : 
                time_home.append([0, travels[k][0]])
            else : 
                time_home.append([travels[k-1][1], travels[k][0]])
        
        return ({
            "parameters" : {
                "p_range" : p_range, 
                "E_range" : E_range,
                "time_home" : time_home, 
                "E0s" : E0s,
                "E_min" : Emin, 
                "E_end" : E_end[0]
            }, 
            "type" : "EV"
        })
        
        
def ev_device_allocation(E_avg, E_var, P_avg, P_var, v2g=True) : 
    allocated = {}
    allocated["E"] = normal(E_avg, E_var**0.5)
    P = normal(P_avg, P_var**0.5)
    if not v2g :
        power_neg = 0
    else :
        power_neg = P
    allocated["power_neg"] = power_neg
    allocated["power_pos"] = P
    return allocated
        