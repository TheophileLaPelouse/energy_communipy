from numpy.random import normal, rand
import pandas as pd

# Reference functions for the power of the devices
def SAE_frigo(V) : 
    return 1.1*0.12*V + 100 # Voir législation https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:32019R2019#anx_IV, valeur calculée bourrine kWh/an

def SAE_congelateur(V) : 
    return 2.1*0.15 + 138 # même source que pour le frigo. kWh/an

def SEC_four(V) : 
    return 0.0042*V + 0.55 # kWh/cuisson https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=OJ:L:2014:029:FULL

def SCE_washing_machine(C) : 
    return -0.0025*C**2 + 0.0846*C + 0.3920 # kWh/cycle https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:02019R2014-20210501#anx_IV

def SEC_dryer(C, d) :
    # d in hour, C in kg 
    return 140*C**0.8 / 365 * 24/d # kWh/cycle https://eur-lex.europa.eu/legal-content/FR/TXT/PDF/?uri=CELEX:32012R0392

def SAEC_dishwasher(C, d) :
    # d in hour, C in couverts
    return (7*C + 378) / 365 * 24/d # kWh/cycle https://eur-lex.europa.eu/legal-content/FR/TXT/HTML/?uri=CELEX:32010R1059#anx_VI

def frigo_power(IEE, V, deltat_active, deltat_inactive) : 
    time_active_day = 24/(deltat_active + deltat_inactive) * deltat_active
    time_active_year = time_active_day * 365
    return IEE/100 * SAE_frigo(V) / time_active_year

def congelateur_power(IEE, V, deltat_active, deltat_inactive) :
    time_active_day = 24/(deltat_active + deltat_inactive) * deltat_active
    time_active_year = time_active_day * 365
    return IEE/100 * SAE_congelateur(V) / time_active_year

def four_power(IEE, V, cook_time) :
    return IEE/100 * SEC_four(V) / cook_time

def washing_machine_power(IEE, C, cycle_time) :
    return IEE /100 * SCE_washing_machine(C) / cycle_time

def dryer_power(IEE, C, d) :
    return IEE/100 * SEC_dryer(C, d) / d

def dishwasher_power(IEE, C, d) :
    return IEE/100 * SAEC_dishwasher(C, d) / d


# Data

# def get_irradiance_data(lat, lon, t0, tend) : 
#     df = pd.read_csv(f"irradiance_{lat}_{lon}.csv")
#     return df[(df["time"] >= t0) & (df["time"] <= tend)]

# def get_weather_forecast_data(lat, lon, t0, tend) : 
#     df = pd.read_csv(f"weather_forecast_{lat}_{lon}.csv", parse_dates=["time"])
#     return df[(df["time"] >= t0) & (df["time"] <= tend)]

# def get_weather_history_data(lat, lon, t0, tend) : 
#     df = pd.read_csv(f"weather_history_{lat}_{lon}.csv", parse_dates=["time"])
#     return df[(df["time"] >= t0) & (df["time"] <= tend)]

# Thermal models for the heating system and water heater
def thermal_model_heating(T_i_w, T_o_f, T_b_c, R1, R2, C, deltat) :
    """Simple thermal model using 2R1C

    Args:
        T_i_w (float): Inside temperature wanted (°C)
        T_o_f (float): Forecasted outside temperature (°C)
        T_b_c (float): Current temperature of the inertia of the building (°C)
        R1 (float): Thermal resistance between inertia and outside (K/W)
        R2 (float): Thermal resistance between inertia and inside (K/W)
        C (float): Capacitance of the inertia (J/K)
        deltat (float): Time step (s)
    """
    
    
    inertia_coef = deltat / C
    U1 = 1/R1
    U2 = 1/R2
    denom = 1 + inertia_coef * (U1 + U2)
    T_b_next = (T_b_c + inertia_coef * (T_o_f * U1 + T_i_w * U2)) / denom

    flux = (T_b_next - T_i_w) * U2
    
    return T_b_next, flux

def PAC_power(flux, T_i, T_o, heating, eta=0.5) : 
    if heating : 
        carnot = (T_i + 273.15) / (T_i - T_o)
    else :
        carnot = (T_i + 273.15) / (T_o - T_i)
    efficiency = carnot * eta    
    return flux / efficiency

# def thermal_model_water(T_needed, T_outside, type_heating) :
#     return


# Probabilistic functions


def compute_average_number(nb_proba) : 
    # print(nb_proba)
    if 0 not in nb_proba :
        nb_proba[0] = 1 - sum(nb_proba[k] for k in nb_proba)
        
    total= sum(nb_proba[k] for k in nb_proba)
    if total != 1 : # Normalization if probabilities don't sum to 1
        coef = 1/total
        for k in nb_proba :
            nb_proba[k] *= coef
    # print(nb_proba)
    return sum([int(k)*nb_proba[k] for k in nb_proba])

def compute_deviation_number(nb_proba, average) : 
    return sum([nb_proba[k]*(int(k)-average)**2 for k in nb_proba])**0.5

def compute_average_type(type_proba, power_types) : 
    total= sum(type_proba[t] for t in type_proba)
    if total != 1 : # Normalization if probabilities don't sum to 1
        coef = 1/total
        for t in type_proba :
            type_proba[t] *= coef
    return sum([type_proba[t]*power_types[t] for t in type_proba])

def compute_deviation_type(type_proba, power_types, average) : 
    return sum([type_proba[t]*(power_types[t]-average)**2 for t in type_proba])**0.5

def normal_positive(mu, sigma) :
    x = normal(mu, sigma)
    c = 0
    while x < 0 and c < 10 : 
        x = normal(mu, sigma)
        c += 1
    return max(x, 0)

def normal_distribution_number(nb_proba) : 
    mu = compute_average_number(nb_proba)
    sigma = compute_deviation_number(nb_proba, mu)
    return normal_positive(mu, sigma)

def normal_distribution_type(type_proba, power_types) : 
    mu = compute_average_type(type_proba, power_types)
    sigma = compute_deviation_type(type_proba, power_types, mu)
    return normal_positive(mu, sigma)

def power_normal_distribution(nb_proba, type_proba, power_types) :
    # P = sum over N of Xi where Xi are random variables and N is a random variable independent of the Xi (approximation). 
    mu_N = compute_average_number(nb_proba)
    sigma_N = compute_deviation_number(nb_proba, mu_N)
    mu_type = compute_average_type(type_proba, power_types)
    sigma_type = compute_deviation_type(type_proba, power_types, mu_type) 
    combined_mean = mu_N * mu_type 
    combined_deviation = mu_N * sigma_type**2 + mu_type**2 * sigma_N**2 
    # Made it using AI assistance needs to be checked
    return normal_positive(combined_mean, combined_deviation**0.5)


# Utilities in general 

def _parse_key(key):
    # Try int first, then float, otherwise keep string
    try:
        return int(key)
    except (ValueError, TypeError):
        try:
            return float(key)
        except (ValueError, TypeError):
            return key

def convert_numeric_keys(obj):
    if isinstance(obj, dict):
        return { _parse_key(k): convert_numeric_keys(v) for k, v in obj.items() }
    if isinstance(obj, list):
        return [convert_numeric_keys(v) for v in obj]
    return obj

def dicotomie_search(l, val) : 
    # l is a list of increasing values, val is a value. We want to find the index i such that l[i] <= val < l[i+1]
    if val < l[0] : return 0
    if val >= l[-1] : return len(l)-1
    left = 0
    right = len(l)-1
    while left <= right : 
        mid = (left + right) // 2
        if l[mid] <= val < l[mid+1] : 
            return mid
        elif val < l[mid] : 
            right = mid - 1
        else : 
            left = mid + 1
    return None # Should not happen if the input is correct

# Markov chain functions

def markov_states(transitions, current_state, starting_step=0, step_number=-1) : 
    n = transitions.shape[0]
    if step_number == -1 : 
        step_number = n
    
    states = []
    for k in range(starting_step, step_number) :
        rd = rand()
        j = current_state
        # print(k, rd, j, i, transitions.shape[1])
        i = dicotomie_search(transitions[k%n, j, :], rd)
        if i == None : 
            return {"Error" : "Probability does not sum to 1", "results" : states}
        current_state = i
        states.append(current_state)
    return {"results" : states}

def possible_starts(time_interval, indices, deltat, cycle_length, finish_before_end=True) :
    # print("args possible starts", time_interval, indices, deltat, cycle_length, finish_before_end)
    if finish_before_end : 
        return [i for i in indices if (i - indices[0])*deltat + cycle_length <= time_interval]
    else :
        return [i for i in indices if (i - indices[0])*deltat <= time_interval]
    
    
# Thermal model functions 

def thermal_model_flux(T_out_t1, T_b_t, T_in_t1, R1, R2, C, deltat) : 
    T_b_t1 = ((T_b_t + deltat/C * (T_out_t1/R1 + T_in_t1/R2)) 
            / 
            (1 + deltat/C * (1/R1 + 1/R2))
            )
    flux_t1 = (T_b_t1 - T_in_t1) / R2
    return T_b_t1, flux_t1

def thermal_model_Tin(T_out_t1, T_b_t, flux_t1, R1, R2, C, deltat) : 
    # Voir feuille de note de calcul
    B = 1 + deltat/C * (1/R1 + 1/R2)
    A = (
        (T_b_t + deltat/C*(T_out_t1/R1 + flux_t1))
        / 
        B
    )
    T_b_t1 = A / (1 - deltat/C * 1/R2 / B)
    T_in_t1 = T_b_t1 - flux_t1 * R2
    return T_b_t1, T_in_t1
    