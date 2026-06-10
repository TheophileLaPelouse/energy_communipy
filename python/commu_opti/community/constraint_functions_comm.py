# Constraint functions for the community optimization problem

# Power exchange constraints

def surplus_only_centralized(m, t, i) :
    S = sum(self.P_exchange[i, j, t] for j in members_id)
    # S = what i send to others 
    return S == self.members[i].P_surplus[t]

def ii_rule_centralized(m, t, i) : 
    return self.P_exchange[i, i, t] == 0

# Aggregation expressions

def P_grid_plus_expr(m, t) : 
    return sum(self.members[i].P_grid_plus[t] for i in members_id)

def P_grid_minus_expr(m, t) : 
    return sum(self.members[i].P_grid_minus[t] for i in members_id)

def P_cons_expr(m, t) : 
    return sum(self.members[i].P_cons[t] for i in members_id)

def P_bat_expr(m, t) : 
    return sum(self.members[i].P_bat[t] for i in members_id)

def P_self_expr(m, t) : 
    return sum(self.members[i].P_self[t] for i in members_id)

def P_prod_expr(m, t) : 
    return sum(self.members[i].P_prod[t] for i in members_id)

def PV_surface_expr(m) : 
    return sum(self.members[i].PV_surface for i in members_id)

def bat_cap_expr(m) : 
    return sum(self.members[i].bat_cap for i in members_id)

def P_exchange_expr(m, t) : 
    return sum(sum(self.P_exchange[i, j, t] for j in members_id) for i in members_id)

def P_auto_expr(m, t) : 
    return m.P_self[t] + m.P_commu_exchange[t] - m.P_grid_minus[t]

def p_confort_expr(m, t) : 
    return sum(self.members[i].mod_member.p_confort[t] for i in members_id)

def t_confort_expr(m) :
    return sum(self.members[i].mod_member.t_confort for i in members_id)

# ADMM constraints

def surplus_only_admm(m, t, i) :
    S = sum(self.P_exchange[i, j, t] for j in members_id)
    # S = what i send to others 
    return S == m.Surplus_repr[i, t]