
# Aggregation from devices to member level

def rule_pcons(m, t) : 
    Pcons = 0
    for d in self.devices : 
        if not (hasattr(d, "E") or d.__class__.__name__ == "PV") : 
            Pcons += d.mod.Pcons[t]
    return Pcons
def rule_pbat(m, t) :
    Pbat = 0
    for d in self.devices : 
        if hasattr(d, "E") : 
            Pbat += d.mod.Pcons[t] 
    return Pbat

def rule_p_prod(m, t) : 
    Pprod = 0
    for d in self.devices : 
        if d.__class__.__name__ == "PV": 
            Pprod -= d.mod.Pcons[t]
    return Pprod

def rule_p_confort(m, t) : 
    confort = 0
    for d in self.devices : 
        if hasattr(d.mod, "p_confort_lvl") : 
            confort += d.mod.p_confort_lvl[t]
    return confort
def rule_t_confort(m) : 
    confort = 0
    for d in self.devices : 
        if hasattr(d.mod, "t_confort_lvl") : 
            confort += d.mod.t_confort_lvl
    return confort

def rule_PV_surface(m) : 
    surface = 0
    for d in self.devices : 
        if d.__class__.__name__ == "PV" : 
            surface += d.mod.PV_surface
    return surface

def bat_cap_rule(m) : 
    cap = 0
    for d in self.devices : 
        if d.__class__.__name__ == "battery" : 
            cap += d.capacity
    return cap

# fetch P exchange 

def simple_power_exchange_sum_centralized(m, t) : 
    if self.commu is None : 
        return 0
    else : 
        s = sum(self.commu.P_exchange[k, self.id, t] for k in self.commu.current_members_id)
    
    if s is None : 
        return 0
    else : 
        return s
    
def simple_power_exchange_sum_admm(m, t) : 
    if self.commu is None : 
        return 0
    else : 
        s = sum(self.P_exchange_repr[k, t] for k in self.commu["current_members_id"])
    if s is None : 
        return 0
    else : 
        return s 
    
    
# Power balance 

def P_bat_con_false(mod, t) :
    return (mod.P_bat[t] == self.P_bat_p[t] - self.P_bat_m[t])

def P_prod_constraint_false(mod, t) : 
    return self.P_surplus[t] + self.P_self[t] == self.P_prod[t] + mod.P_bat_m[t]

def P_grid_constraint_false(mod, t):
    return mod.P_grid_plus[t] - mod.P_grid_minus[t] == self.P_cons[t] + mod.P_bat_p[t] - self.P_exchange[t] - self.P_self[t]

def P_self_prod_con_false(mod, t) : 
    return mod.P_self[t] - mod.P_bat_m[t]

def P_prod_constraint_true(mod, t) : 
    return self.P_surplus[t] + self.P_self[t] == self.P_prod[t] 

def P_grid_constraint_true(mod, t):
    return mod.P_grid_plus[t] - mod.P_grid_minus[t] == self.P_cons[t] + self.P_bat[t] - self.P_exchange[t] - self.P_self[t]

def P_self_prod_con_true(mod, t) : 
    return mod.P_self[t]