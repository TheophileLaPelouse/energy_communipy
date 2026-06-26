
# Aggregation from devices to member level

def rule_pcons(m, t) : 
    Pcons = 0
    for i in m.device_set : 
        d = getattr(m, f"device{i}")
        if not (hasattr(d, "p_range_bat") or hasattr(d, "PV_surface")) : 
            Pcons += d.Pcons[t]
    return Pcons

def rule_pbat(m, t) :
    Pbat = 0
    for i in m.device_set : 
        d = getattr(m, f"device{i}")
        if hasattr(d, "p_range_bat") : 
            Pbat += d.Pcons[t] 
    return Pbat

def rule_p_prod(m, t) : 
    Pprod = 0
    for i in m.device_set : 
        d = getattr(m, f"device{i}")
        if hasattr(d, "PV_surface"): 
            Pprod -= d.Pcons[t]
    return Pprod

def rule_p_confort(m, t) : 
    confort = 0
    for i in m.device_set : 
        d = getattr(m, f"device{i}")
        if hasattr(d, "p_confort_lvl") : 
            confort += d.p_confort_lvl[t]
    return confort
def rule_t_confort(m) : 
    confort = 0
    for i in m.device_set : 
        d = getattr(m, f"device{i}")
        if hasattr(d, "t_confort_lvl") : 
            confort += d.t_confort_lvl
    return confort

def rule_PV_surface(m) : 
    surface = 0
    for i in m.device_set : 
        d = getattr(m, f"device{i}")
        if hasattr(d, "PV_surface") : 
            surface += d.PV_surface
    return surface

def bat_cap_rule(m) : 
    cap = 0
    for i in m.device_set : 
        d = getattr(m, f"device{i}")
        if hasattr(d, "capacity") : 
            cap += d.capacity
    return cap

# fetch P exchange 

def simple_power_exchange_sum_centralized(m, t) :  # Vérifier que ça marche quand on change la valeur de m.commu
    # print("Dans la fonction")
    if m.commu.value == 0 : 
        return 0
    else : 
        mod_commu = m.parent_block()
        s = sum(mod_commu.P_exchange[k, m.id.value, t]*m.commu*mod_commu.active_members[k] for k in mod_commu.member_set)
        return s
    
def simple_power_exchange_sum_admm(m, t) : 
    s = sum(m.P_exchange_repr[k, t]*m.active_members[k] for k in m.member_set)
    return s
    
def no_self_exchange(m, t) :
    return m.P_exchange_repr[m.id.value, t] == 0
    
# Power balance 

def P_bat_con_false(mod, t) :
    return (mod.P_bat[t] == mod.P_bat_p[t] - mod.P_bat_m[t])

def P_prod_constraint_false(mod, t) : 
    return mod.P_surplus[t] + mod.P_self[t] == mod.P_prod[t] + mod.P_bat_m[t]

def P_grid_constraint_false(mod, t):
    return mod.P_grid_plus[t] - mod.P_grid_minus[t] == mod.P_cons[t] + mod.P_bat_p[t] - mod.P_exchange[t] - mod.P_self[t]

def P_self_prod_con_false(mod, t) : 
    return mod.P_self[t] - mod.P_bat_m[t]

def P_prod_constraint_true(mod, t) : 
    return mod.P_surplus[t] + mod.P_self[t] == mod.P_prod[t] 

def P_grid_constraint_true(mod, t):
    return mod.P_grid_plus[t] - mod.P_grid_minus[t] == mod.P_cons[t] + mod.P_bat[t] - mod.P_exchange[t] - mod.P_self[t]

def P_self_prod_con_true(mod, t) : 
    return mod.P_self[t]