# Define all the constraint function outside of the class to avoid pickling problems with multiprocessing

# General constraints : 

def power_constraint_lower(mod, t_set) : 
    # print("Bonjour", self.p_range)
    return (mod.allocated_power[t_set] + mod.p_excess_l[t_set] >= self.p_range[t_set][0])

def power_constraint_upper(mod, t_set) :
    return mod.allocated_power[t_set] <= self.p_range[t_set][1] + mod.p_excess_u[t_set]


# Battery constraints :

def soc(mod, t) :
    if t == 0 : 
        return mod.E[t] == self.E0[0]
    return mod.E[t] == mod.E[t - 1] + mod.P_plus[t] * self.charge_eff - mod.P_minus[t] / self.dcharge_eff


def soc_max(mod, t) :
    return mod.E[t] <= self.E_range[1]
def soc_min(mod, t) :
    return mod.E[t] >= self.E_range[0]

def P_plus_max(mod, t) :
    return mod.P_plus[t] <= self.p_range_bat[1]
def P_minus_max(mod, t) :
    return mod.P_minus[t] <= -self.p_range_bat[0]
        
def power_constraint(mod, t) :
    if t == 0 : 
        return mod.Pcons[t] == 0
    return mod.Pcons[t] == mod.P_plus[t] - mod.P_minus[t] 
    # Pour l'instant on fait comme ça pour rester un max linéaire, on verra si on ajoute une fonction de pénalisation
        
def Pcons_0_constraint(mod, t) : 
    return mod.Pcons[t] == 0

def soc_end(mod) :
    return mod.E[self.t_set.at(-1)] == E_end
        
def start_constraint(mod, t) : 
    c = 0 
    # if t == 0 : 
    #     return mod.E[t] == self.E0[c]
    for i in mod.start_set :
        if i == t :
            break 
        else : 
            c += 1
    if c == 0 : 
        return mod.E[t] == self.E0[c]
    else : 
        return mod.E[t] == mod.E[mod.end_set.at(c)] + self.E0[c]
    
def end_constraint(mod, t) : 
    c = 0 
    for i in mod.end_set :
        if i == t :
            break 
        else : 
            c += 1
    return mod.E[t] >= self.E_min[c]


# White goods : 

def rule_pow_wg(mod, t) :
    S = 0
    for p in range(max(t-cycle_length, t_min), min(t, t_max-cycle_length)+1) :
        S += self.p_range[instant][0]*getattr(mod, f"bin_{instant}")[p] 
        # If we need to add power profiles in the cycle, 
        # cycle_length - c with c the number of time in the loop would work.
        # (Can be proven by induction)
    return mod.Pcons[t] == S
            
def rule_confort(mod) : 
    return starting_time_plus + starting_time_minus
            
def rule_pow_wg2(mod, t) : 
    return mod.Pcons[t] == 0

# Fixed devices

def rule_fixed(mod, t) :
    return mod.Pcons[t] == power_profile[t] 

# PV devices 

def rule_PV(mod, t) :
    return mod.Pcons[t] == -irradiance_profile[t]*mod.PV_surface*eff

# Flex devices 

def rule_flex(mod, t) : 
    return mod.Pcons[t] == mod.allocated_power[t]

def confort_rule_flex(mod, t) :
    return self.p_range[t][1] - mod.allocated_power[t]

# AoN devices

def rule_AoN(mod, t) : 
    return mod.Pcons[t] == mod.on_off[t]*self.power_needed

