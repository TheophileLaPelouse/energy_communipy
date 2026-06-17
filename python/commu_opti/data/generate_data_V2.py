from .utils import *
import numpy as np

import os 
import json 

# Define all the data variables (they are small so we can load them all)

from .devices_jsonpy import list_devices
# if not os.path.exists(os.path.join(os.path.dirname(__file__), "devices.json")): 
#     from .devices_jsonpy import list_devices
#     with open(os.path.join(os.path.dirname(__file__), "devices.json"), "w") as f: 
#         json.dump(list_devices, f, indent = 4)
# else:
#     with open(os.path.join(os.path.dirname(__file__), "devices.json"), "r") as f: 
#         list_devices = json.load(f)
#         list_devices = convert_numeric_keys(list_devices)
        
   
from .devices_jsonpy import building     
# if not os.path.exists(os.path.join(os.path.dirname(__file__), "building.json")): 
#     from .devices_jsonpy import building
#     with open(os.path.join(os.path.dirname(__file__), "building.json"), "w") as f: 
#         json.dump(building, f, indent = 4)
# else:
#     with open(os.path.join(os.path.dirname(__file__), "building.json"), "r") as f: 
#         building = json.load(f)
#         building = convert_numeric_keys(building)
        
with open(os.path.join(os.path.dirname(__file__), "initial_state_probabilities.json"), "r") as f:
    initial_state_probabilities = json.load(f)
    
with open(os.path.join(os.path.dirname(__file__), "ev_travel_statistics.json"), "r") as f:
    ev_stat = json.load(f)
    ev_stat = convert_numeric_keys(ev_stat)
    
list_locations = [
    (50.63, 3.06), (50.63, 2.5), (45.76, 4.83), (45.76, 3.8), (43.3, 5.4), 
    (43.4, 5.54), (43.6, 1.44), (43.5, 1.14), (47.22, -1.55), (47.22, -1.9)
]

average_people = compute_average_number(building["nb_popu_proba"])
deviation_people = compute_deviation_number(building["nb_popu_proba"], average_people)   
# print("BOnjour") 
# print(building["surface_probability"])
average_surface = {int(k): compute_average_number(v) for k, v in building["surface_probability"].items()}
# print(average_surface)
deviation_surface = {int(k): compute_deviation_number(v, average_surface[int(k)]) for k, v in building["surface_probability"].items()}    


def get_weather_data(date_start, date_end, lat=45, lon=8, forecast=True) :
    year = date_start.year 
    folder = os.path.join(os.path.dirname(__file__), "weather_data")
    file = f"weather_{'forecast' if forecast else 'archive'}_{year}_{lat}_{lon}.csv"
    if not os.path.exists(os.path.join(folder, file)) :
        raise ValueError(f"Weather data for the year {year} and location ({lat}, {lon}) not found. Should be generated using weather_data.py")
    df = pd.read_csv(os.path.join(folder, file), parse_dates=["time"])
    df = df[(df["time"] >= date_start) & (df["time"] <= date_end)]
    weather = df["temperature_2m"].to_numpy()
    irradiance = df["shortwave_radiation"].to_numpy()
    return weather, irradiance

def get_price_data(date_start, date_end) : 
    year = date_start.year 
    file = "day_ahead_price_FR_2021-01-01_2026-01-01.csv"
    df = pd.read_csv(os.path.join(os.path.dirname(__file__), file))
    df = df[(df["date"] >= date_start) & (df["date"] <= date_end)]
    price_per_hour = df["price"].to_numpy()
    return price_per_hour

def generate_building() : 
    
    nb_people = round(normal(average_people, deviation_people))
    if nb_people < 1 : nb_people = 1
    if nb_people > 6 : nb_people = 6
    
    surface = round(normal(average_surface[nb_people], deviation_surface[nb_people]))
    if surface < 10 : surface = 10
    
    R_DPE = power_normal_distribution({1: 1}, 
                                        building["DPE_proba"], 
                                        building["R_DPE"])
    C = normal_distribution_number(building["C_proba"])*10e6
    R1 = R_DPE / surface * building['coef_R'][0]
    R2 = R_DPE / surface * building['coef_R'][1]
    
    
    return {"nb_people" : nb_people, "surface" : surface, "R1" : R1, "R2" : R2, "C" : C}

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
    # print("testrd", rd)
    # print("testprofile0", profile0)
    # print("testprofile", profile)
    if profile.get("Error") : 
        print(profile["Error"])
        print("\n, Attention ! \n")
        print(profile["results"])
    profile_states = [states_inverse[s] for s in profile["results"]]
    # print("testprofile_states", profile_states)
    
    
    
    data_deltat = 10/60 # 10 minutes in hours
    n_states = len(profile_states)
    profile_states0_24 = [profile_states[(i - int(4/data_deltat)) % n_states] for i in range(n_states)] # Initially from 4am to 4am, we want from 0 to 24
    # print("testprofile_states0_24", profile_states0_24)
    if deltat != data_deltat :
        # There can be a deltat difference, so we need to adapt the profile. 
        # We will do it by taking the state of the profile at the closest time step to the one we want.
        factor = deltat/data_deltat
        profile_states0_24 = [profile_states0_24[int(i*factor)] for i in range(int(len(profile_states0_24)/factor))]    
    if len(profile_states0_24) < int(24/deltat) : 
        profile_states0_24.append(profile_states0_24[-1])


    return profile_states0_24
        
        
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
    
    
    State is in the form "ij" where i is the number of people at home and j the number of active people and N is the total number of people.
    But there can be several possibilities for the same state. So we need to choose between every possibilities.
    For this we will assume that each combination has the same probability.
    In the end we want to know the number of 10 people, 11 people and 0x people.
    
    We consider coordinate (x_k, y_k) with x = 0 or 1 and y = 1 or 0 for member k.
    So let's consider Pr = {k in [1, i]} (set of people present at home) and and A = {k in [1, N] | y_k = 1}, 
    we want to know the size of NS = {k in [1, i] | y_k = 1} the number of people awake at home.
    We have |Pr| = i, |A| = j and we want to know the probability of having |NS| = s for s in [0, j] knowing that every combination have the same probability.
    This is then an hypergeometric distribution with parameters j, N-j and i.
    """ 
    
    i, j = int(state[0]), int(state[1])
    if i > 0 :
        awake = np.random.hypergeometric(
                ngood=j,          # actifs
                nbad=nb_people - j, # Non actifs
                nsample=i         # présents
            )
    else :
        awake = 0

    return {"awake" : awake, "asleep" : i-awake, "away" : nb_people - i}

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
        # print("Bonjour", when["time"])
        for time_interval in when["time"] : 
            start, end, proba = time_interval
            start_index = int(start/deltat)
            end_index = int(end/deltat)
            finish_before_end = when.get("spec") == "before leave"
            indices = possible_starts(end-start, range(start, end), deltat, device.get("cycle_length", 0), finish_before_end=finish_before_end)
            # print("indices", indices, start_index, end_index)
            for i in indices :
                intervals[i]  = {}
                for key in when["presence_state"] : 
                    intervals[i][key] = {"proba" : proba, "time" : (start, end)}
            
    if when.get("moment") :
        translation = {"morning" : (6, 12), "afternoon" : (12, 20), "night" : (20, 6), "sleep" : (22, 6)}
        
        for moment in when["moment"] :
            start, end = translation[moment]
            start, end = round(normal(start, 0.3*start)), round(normal(end, 0.3*end))
            if end < start : start, end = end, start
            start_index = int(round(start/deltat))
            end_index = int(round(end/deltat))
            if start_index < 0 : start_index = 0
            if end_index > len(intervals) : end_index = len(intervals) - 1
            for i in range(start_index, end_index) :
                intervals[i]  = {}
                for key in when["presence_state"] : 
                    intervals[i][key] = {"probat" : 1, "time" : (start, end)}
                    
        
    if not when.get("time") and not when.get("moment") : 
        start, end = 0, 24
        start_index = int(round(start/deltat))
        end_index = int(round(end/deltat))
        indices = possible_starts(end-start, range(start, end), deltat, device.get("cycle_length", 0))
        proba = when.get("proba")
        probat = when.get("probat")
        # print("Bonjour", indices, len(intervals))
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
    set_proba = set()
    while i < len(when_profile) : 
        presence_state = profile_presence[i]
        when = when_profile[i]
        # print(presence_state, when)
        flag = False
        for state in presence_state : 
            if presence_state[state] > 0 and state in when : 
                flag = True
                break
        if flag : 
            
            if isinstance(when[state], (int, float)) or "probat" in when[state] : 
                # Has a probability of probat to be activated at each time step during the time interval
                if isinstance(when[state], (int, float)) : 
                    if rand() < when[state] :
                        activation_profile[i] = 1
                elif rand() < when[state]["probat"] : 
                    activation_profile[i] = 1
                i += 1
                    
            elif "proba" in when[state] and not "time" in when[state] :
                # Will be activated once a day with a certain probability 
                set_proba.add(i)
                i += 1
                
            elif "proba" in when[state] and "time" in when[state] :
                # Will be activated once during the time interval with a certain probability
                proba = when[state]["proba"]
                time_interval = when[state]["time"]
                indices = possible_starts(time_interval[1]-time_interval[0], range(i, len(when_profile)), deltat, device.get("cycle_length", 0), finish_before_end=True)
                rd_indice = np.random.choice(indices)
                if rand() < proba : 
                    activation_profile[rd_indice] = 1
                i = indices[-1] + 1
        else : 
            i += 1
                
        # print("bonjour", list(set_proba))
    if set_proba : 
        rd_indice = np.random.choice(list(set_proba))
        # print("bonjour", rd_indice, when_profile[rd_indice])
        if rand() < when_profile[rd_indice]['awake']["proba"] : 
            activation_profile[rd_indice] = 1
                
    return activation_profile, when_profile, profile_presence     
    
    
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
    increased_pow = allocated.get("increase_power", 0)
    power_profile_confort = [power + power*increased_pow*confort_diff 
                                if k/deltat % total_cycle < time_active 
                                else 0 for k in range(total_time)]
    p_range = [(power_profile_needed[i], power_profile_confort[i]) for i in range(total_time)]
    param = {"parameters" : {"power_range" : p_range}, "type" : "flex"}
    return param
    
def white_goods_profile(device_name, allocated, deltat, when_profile, activation_profile) :
    cycle_length = allocated.get("cycle_length", 0)
    if device_name == "washing_machine" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], allocated["popu"]
        finish_before_end = False
        power = washing_machine_power(E, popu, cycle_length)
    elif device_name == "dishwasher" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], allocated["popu"]
        finish_before_end = False
        power = dishwasher_power(E, popu, cycle_length)
    elif device_name == "dryer" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], allocated["popu"]
        finish_before_end = False
        power = dryer_power(E, popu, cycle_length)
    elif device_name == "hoven" :
        E, cycle_length, popu = allocated["E"], allocated["cycle_length"], 60 # Not exact but does not change much (5%)
        finish_before_end = True
        power = E/cycle_length
        # print("power", power, E, popu, cycle_length)

    else : 
        power, cycle_length = allocated["P"], allocated["cycle_length"]
        finish_before_end = True

    start_pref = []
    time_range = []
    # print(when_profile)
    if allocated['when'].get('time') :
        for interval in allocated['when']['time'] : 
            start, end, proba = interval
            indices = possible_starts(end-start, range(int(start/deltat), int(end/deltat)+1), deltat, cycle_length, finish_before_end=finish_before_end)
            for i in indices : 
                if activation_profile[i] == 1 :
                    # Slow but I don't see how to accelerate it  
                    start_pref.append(i)
                    time_range.append((start-i, end-i))
                    break
                
    else :
        # We'll see later, for now no time range for these devices 
        # flag = True
        # t0 = 0
        # c = 
        # while flag : 
        #     while not when_profile[t0] :
        #         t0 += 1
        #     tend = t0
        #     while when_profile[tend] : 
        #         if activation_profile[t0]
        #         tend += 1
        for k in range(len(activation_profile)) :
            if activation_profile[k] == 1 : 
                start_pref.append(k) # To verify if needs to be multiplied by deltat
                time_range.append([0, 0])
                break
                
    if int(cycle_length/deltat) != cycle_length/deltat :
        energy = power * cycle_length 
        power = energy / (deltat * (int(cycle_length/deltat)+1)) # Adapt the power to the cycle length
            
    white_good = {'cycle_length' : [cycle_length for k in range(len(start_pref))], # For now no variation on the cycle length, but it could be done. 
                    'power_needed' : [power for k in range(len(start_pref))], 
                    "start_pref" : start_pref, 
                    "time_range" : time_range, 
                    }
    return {"parameters" : white_good, "type" : "white_good"}
        
def small_white_goods_profile(allocated, deltat, total_time, activation_profile) :
    power = allocated.get("P", 0)
    cycle_length = allocated.get("cycle_length", 0)

    if int(cycle_length/deltat) != cycle_length/deltat :
        energy = power * cycle_length 
        power = energy / (deltat * (int(cycle_length/deltat)+1)) # Adapt the power to the cycle length
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
    

def lighting_profile(allocated, total_time, activation_profile, building, presence_profile, nb_people) : 
    # The lighting power is cvonsidered proportional to the number of people at home and to the surface of the house.  
    surface = building["surface"]
    power_profile = []
    for i in range(total_time) : 
        if activation_profile[i] == 1 : 
            power = allocated.get("P", 0) * surface * (presence_profile[i]['awake'] / nb_people)
        else : 
            power = 0
        power_profile.append(power)
     
    params = {"parameters" : {"power_profile" : power_profile}, "type" : "fixed"}
    return params

def water_heater_profile(allocated, nb_people) :
    # The water heater needs to provide a certain amount of energy
    energy_needed = allocated["E"] * nb_people
    P = allocated['P']
    params = {"parameters" : {"energy_needed" : energy_needed, "power_needed" : P}, "type" : "water_heater"}
    return params

def heating_power_model(T, T_out, presence_profile, R1, R2, C, total_time, deltat, typ, **options) : 
    T_bs = []
    T_in = []
    
    def iterate_thermic_model(T_b, T_out, R1, R2, C, deltat, T_set) : 
        if T_out < T['away'] : 
            T_in = T_set
            T_b, flux = thermal_model_flux(T_b, T_out, T_in, R1, R2, C, deltat)
        else : 
            flux = 0
            T_b, T_in = thermal_model_Tin(T_b, T_out, flux, R1, R2, C, deltat)
        return T_b, T_in, flux    

    power_profile = []
    T_in = []
    T_b = options.get("T_b", T_out[0]) 
    for t in range(total_time) : 
        if presence_profile[t].get("awake", 0) > 0 : 
            T_set = T['awake']
        elif presence_profile[t].get("asleep", 0) > 0 : 
            T_set = T['asleep']
        else : 
            T_set = T['away']
            
        T_b, T_in_t, flux = iterate_thermic_model(T_b, T_out[t], R1, R2, C, deltat, T_set)
        T_bs.append(T_b)
        power_profile.append(max(0, -flux))
        T_in.append(T_in_t)

        
    if typ == "resistor" :
        carnot = [1 for k in range(total_time)]
    elif typ == "heat_pump" :
        carnot = []
        for k in range(total_time) : 
            if T_in[k] + 0.1 <= T_out[k] :
                carnot.append(1)
            else :
                carnot.append(max(1, (T_in[k]+273.15) / (T_in[k]- T_out[k])))
        
    power_profile[0] = power_profile[-1] # We consider that the power needed at the first time step is the same as the one needed at the second time step, but it could be done differently.
    # print("\nT_in:", T_in)
    # print("\nT_out:", T_out)
    # print("\nT_b:", T_bs)
    # print("\npower_profile:", power_profile)
    return power_profile, carnot
    

def heating_system_profile(allocated, deltat, total_time, building, presence_profile, weather, **options) :
    # 2R1C model, we compute first the power range for a certain temperature
    T_wanted = {"awake" : normal_positive(allocated["T_wanted_awake"], 1), 
                "asleep" : normal_positive(allocated["T_wanted_asleep"], 1), 
                "away" : normal_positive(allocated["T_wanted_away"], 1)}
    T_min = {
        "awake" : 16, 
        "asleep" : 14,
        "away" : 10
    }
    R1, R2, C = building["R1"], building["R2"], building["C"]
    # T0 = options.get("T0", T_wanted["asleep"])
    
    typ = allocated.get("type", "resistor")
    power_confort_forecast, carnot_confort = heating_power_model(T_wanted, weather["forecast"]["temperature"], presence_profile, R1, R2, C, total_time, deltat, typ, **options)
    power_min_forecast, carnot_min = heating_power_model(T_min, weather["forecast"]["temperature"], presence_profile, R1, R2, C, total_time, deltat, typ, **options)
    
    efficiency = normal_positive(allocated.get("efficiency", 0.5), 0.1)
    
    p_range_forecast = [(min(power_min_forecast[i], power_confort_forecast[i])/(efficiency*carnot_min[i]), 
                         max(power_min_forecast[i], power_confort_forecast[i])/(efficiency*carnot_confort[i])) 
                        for i in range(total_time)]
    params = {"parameters" : {"power_range" : p_range_forecast}, "type" : "flex"}
    
    if weather.get("history") : 
        presence_profile_history  = options.get("presence_profile_history", presence_profile)
        power_confort_history, carnot_confort_history = heating_power_model(T_wanted, weather["history"]["temperature"], presence_profile_history, R1, R2, C, total_time, deltat, typ, **options)
        power_min_history, carnot_min_history = heating_power_model(T_min, weather["history"]["temperature"], presence_profile_history, R1, R2, C, total_time, deltat, typ, **options)
        p_range_history = [(min(power_min_history[i], power_confort_history[i])/(efficiency*carnot_min_history[i]), 
                            max(power_min_history[i], power_confort_history[i])/(efficiency*carnot_confort_history[i])) 
                           for i in range(total_time)]
        params["parameters"]["p_range_history"] = p_range_history
        
    return params
    
def clim_profile(allocated, deltat, total_time, presence_profile, weather, building, **options)  :
    T_out_forecast = weather["forecast"]["temperature"]
    T_in_forecast = []
    flux_forecast = []
    if weather.get("history") : 
        T_out_history = weather["history"]["temperature"]
        T_in_history = []
        flux_history = []
        
    T_activation = allocated.get("T_activation", 25)
    T_minus = allocated.get("T_minus", -7)
    T_b = options.get("T_b", T_out_forecast[0]) # Initial temperature of the inertia of the building, we will update it at each time step
    
    R1, R2, C = building["R1"], building["R2"], building["C"]
    
    def iterate_clim(presence_profile, T_b, T_out, T_in_t, R1, R2, C, deltat) :
        if presence_profile.get("awake", 0) > 0 or presence_profile.get("asleep", 0) > 0 : 
            if T_in_t >= T_activation - T_minus and T_out > T_activation - T_minus : 
                T_in = T_activation + T_minus
                T_b, flux = thermal_model_flux(T_b, T_out, T_in, R1, R2, C, deltat)
            elif T_in_t >= T_activation and T_out > T_activation : 
                T_in = T_activation
                T_b, flux = thermal_model_flux(T_b, T_out, T_in, R1, R2, C, deltat)
            else : 
                flux = 0
                T_b, T_in = thermal_model_Tin(T_b, T_out, flux, R1, R2, C, deltat)

        else : 
            flux = 0
            T_b, T_in = thermal_model_Tin(T_b, T_out, flux, R1, R2, C, deltat)
        
        return T_b, T_in, flux


    carnot_forecast = []
    carnot_history = []
    for t in range(total_time) :
        if t == 0 : 
            if T_out_forecast[t] > T_activation - T_minus : 
                T_in = T_activation + T_minus
            elif T_out_forecast[t] > T_activation : 
                T_in = T_activation
            else : 
                T_in = T_out_forecast[t]
        T_b, T_in, flux = iterate_clim(presence_profile[t], T_b, T_out_forecast[t], T_in, R1, R2, C, deltat)
        flux_forecast.append(max(0, flux))
        T_in_forecast.append(T_in)
        if flux != 0 or T_in >= T_out_forecast[t] + 0.1 : # We add a small margin to avoid numerical issues
            carnot_forecast.append(max(1, (T_in+273.15) / (T_out_forecast[t]- T_in)))
        else :
            carnot_forecast.append(1)

        if weather.get('history') :
            if t == 0 : 
                if T_out_history[t] > T_activation - T_minus : 
                    T_in_hist = T_activation + T_minus
                elif T_out_history[t] > T_activation : 
                    T_in_hist = T_activation
                else : 
                    T_in_hist = T_out_history[t] 
            presence_history = options.get("presence_profile_history", presence_profile)
            T_b, T_in_hist, flux = iterate_clim(presence_history[t], T_b, T_out_history[t], T_in_hist, R1, R2, C, deltat)
            flux_history.append(max(0, flux))
            if flux != 0 or T_in_hist >= T_out_history[t] + 0.1 : # We add a small margin to avoid numerical issues
                # print("T_in_hist", T_in_hist, "T_out_history[t]", T_out_history[t])
                carnot_history.append(max(1, (T_in_hist+273.15) / (T_out_history[t]- T_in_hist)))
            else : 
                carnot_history.append(1)
            T_in_history.append(T_in_hist)            
    

    efficiency = normal_positive(allocated.get("efficiency", 0.5), 0.1)
    
    p_range = [(0, flux_forecast[i]/(efficiency*carnot_forecast[i])) for i in range(total_time)]
    params = {"parameters" : {"power_range" : p_range}, "type" : "flex"}
    if weather.get("history") :
        p_range_history = [(0, flux_history[i]/(efficiency*carnot_history[i])) for i in range(total_time)]
        params["parameters"]["p_range_history"] = p_range_history
        
    if options.get("debug") : 
        return params, {"T_in_forecast" : T_in_forecast, "T_out_forecast" : T_out_forecast, 
                        "flux_forecast" : flux_forecast, "carnot_forecast" : carnot_forecast,
                        "T_in_history" : T_in_history, "T_out_history" : T_out_history, 
                        "flux_history" : flux_history, "carnot_history" : carnot_history}
    return params

    
def device_power_profile(activation_profile, when_profile, presence_profile, device_name, allocated, building, nb_people, deltat, weather, **options) : 
    """
    Generate the power profile of the device depending on the activation profile and the device characteristics.
    
    - activation_profile, when_profile computed using the function device_activation_profile
    - presence_profile computed using the function profile_to_presence
    - allocated computed using the function one_device_allocation
    - building generated using the function generate_building
    - Possible options for now : presence_profile_history, T_b (initial value of the temperature of the inertia of the building)
    """
    if allocated['Number'] == 0 : 
        return None
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
        params = lighting_profile(allocated, total_time, activation_profile, building, presence_profile, nb_people)
        
    if device_name == 'water_heater' : 
        params = water_heater_profile(allocated, nb_people)
        
    if device_name == 'heating_system' : 
        params = heating_system_profile(allocated, deltat, total_time, building, presence_profile, weather, **options)
    
    if device_name == 'climatisation' : 
        params = clim_profile(allocated, deltat, total_time, presence_profile, weather, building, **options)
        # print("params clim", params)
        
    return params
    
            
