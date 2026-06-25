# Define all the constraint function outside of the class to avoid pickling problems with multiprocessing

# General constraints : 

def power_constraint_lower(mod, t_set) : 
    # print("Bonjour", self.p_range)
    return (mod.allocated_power[t_set] + mod.p_excess_l[t_set] >= mod.p_range[t_set, 0])

def power_constraint_upper(mod, t_set) :
    return mod.allocated_power[t_set] <= mod.p_range[t_set, 1] + mod.p_excess_u[t_set]


# Battery constraints :

def soc(mod, t) :
    if t == 0 : 
        return mod.E[t] == mod.E0[0]
    # active_time is used for knowing is the battery is at home or not. And E_return is giving the energy used when the battery was not at home when it returns.
    return mod.E[t] == mod.E[t - 1] + (mod.P_plus[t-1] * mod.charge_eff - mod.P_minus[t-1] / mod.dcharge_eff)*mod.active_time[t-1] + mod.E_return[t]


def soc_max(mod, t) :
    return mod.E[t] <= mod.E_range[1]
def soc_min(mod, t) :
    return mod.E[t] >= mod.E_range[0]

def P_plus_max(mod, t) :
    return mod.P_plus[t] <= mod.p_range_bat[1]
def P_minus_max(mod, t) :
    return mod.P_minus[t] <= -mod.p_range_bat[0]
        
def power_constraint_bat(mod, t) :
    if t == 0 : 
        return mod.Pcons[t] == 0
    return mod.Pcons[t] == (mod.P_plus[t] - mod.P_minus[t])*mod.active_time[t]
    # Pour l'instant on fait comme ça pour rester un max linéaire, on verra si on ajoute une fonction de pénalisation

def soc_end(mod) :
    return mod.E[mod.t_set.at(-1)] == mod.E_end
    
def end_constraint(mod, t) : 
    return mod.E[t] >= mod.E_min_t[t]


# White goods : 

#     For each cycle, we have a constraint, we will use 1 constraint for the power 
#     and 2 others to count positively and negatively the time gap with the comfort value
    
#     For the power : 
#     S = [max(t - cycle_length, tmin), min(t, tmax - cycle_length)] ([tmin, tmax] being set_t0)
#     sum bin_t0[t]*power_needed for t in S) == Pcons[t] (power_needed is constant during a cycle)
    
#     For the comfort : 
#     starting_time_plus >= sum bin_t0[t]*t for t in set_t0) - start_pref
#     starting_time_minus >= start_pref - sum bin_t0[t]*t for t in set_t0)

def rule_pow_wg(mod, t) : 
  
    return (
        sum(mod.bin_t0[t_set, t2]*mod.p_range_wg[t_set, (t-t2)%len(mod.double_set)]#*mod.available_time_set[t_set, t2]
            for t_set in mod.max_set
            for t2 in mod.time_total_set) 
        + mod.power_previous_cycle[t] # For cycles that have already began before the optimization (for rolling horizon)
        == mod.Pcons[t]
            )

def time_constraint(mod, t_set) : 
    return (sum(
        mod.bin_t0[t_set, t]*mod.available_time_set[t_set, t]  
        for t in mod.time_total_set)
            == mod.used_time[t_set]
    )
    
def time_constraint2(mod, t_set) : 
    return (sum(
        mod.bin_t0[t_set, t]  
        for t in mod.time_total_set)
            <= 1
    )
    
def starttime_con_plus(mod, t_set) : 
    # expr=sum(t*bin_t0[t] for t in set_t0)- self.t_use[instant][0] <= starting_time_plus
    return (sum(t*mod.bin_t0[t_set, t] for t in mod.time_total_set)- mod.t_wanted[t_set] <= mod.starting_time_plus[t_set])

def starttime_con_minus(mod, t_set) :
    return (mod.t_wanted[t_set] - sum(t*mod.bin_t0[t_set, t] for t in mod.time_total_set) <= mod.starting_time_minus[t_set])
# def rule_pow_wg(mod, t) :
#     S = 0
#     for p in range(max(t-cycle_length, t_min), min(t, t_max-cycle_length)+1) :
#         S += self.p_range[instant][0]*getattr(mod, f"bin_{instant}")[p] 
#         # If we need to add power profiles in the cycle, 
#         # cycle_length - c with c the number of time in the loop would work.
#         # (Can be proven by induction)
#     return mod.Pcons[t] == S
            
            
# def rule_pow_wg2(mod, t) : 
#     return mod.Pcons[t] == 0

# Fixed devices

def rule_fixed(mod, t) :
    return mod.Pcons[t] == mod.power_profile[t] 

# PV devices 

def rule_PV(mod, t) :
    return mod.Pcons[t] == -mod.irradiance_profile[t]*mod.PV_surface*mod.eff

# Flex devices 

def rule_flex(mod, t) : 
    return mod.Pcons[t] == mod.allocated_power[t]

def confort_rule_flex(mod, t) :
    return mod.p_range[t, 1] - mod.allocated_power[t]

# AoN devices

def rule_AoN(mod, t) : 
    return mod.Pcons[t] == mod.on_off[t]*mod.power_needed

