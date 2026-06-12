# Constraint functions for the community optimization problem

# Power exchange constraints

def surplus_only_centralized(m, t, i) :
    S = sum(m.P_exchange[i, j, t]*m.active_members[j]*m.active_members[i] for j in m.member_set)
    # S = what i send to others 
    return S == getattr(m, f'member_{i}').P_surplus[t]*m.active_members[i]

def ii_rule_centralized(m, t, i) : 
    return m.P_exchange[i, i, t] == 0

# Aggregation expressions

def P_grid_plus_expr(m, t) : 
    return sum(getattr(m, f'member_{i}').P_grid_plus[t]*m.active_members[i] for i in m.member_set)

def P_grid_minus_expr(m, t) : 
    return sum(getattr(m, f'member_{i}').P_grid_minus[t]*m.active_members[i] for i in m.member_set)

def P_cons_expr(m, t) : 
    return sum(getattr(m, f'member_{i}').P_cons[t]*m.active_members[i] for i in m.member_set)

def P_bat_expr(m, t) : 
    return sum(getattr(m, f'member_{i}').P_bat[t]*m.active_members[i] for i in m.member_set)

def P_self_expr(m, t) : 
    return sum(getattr(m, f'member_{i}').P_self[t]*m.active_members[i] for i in m.member_set)

def P_prod_expr(m, t) : 
    return sum(getattr(m, f'member_{i}').P_prod[t]*m.active_members[i] for i in m.member_set)

def PV_surface_expr(m) : 
    return sum(getattr(m, f'member_{i}').PV_surface*m.active_members[i] for i in m.member_set)

def bat_cap_expr(m) : 
    return sum(getattr(m, f'member_{i}').bat_cap*m.active_members[i] for i in m.member_set)

def P_exchange_expr(m, t) : 
    return sum(sum(m.P_exchange[i, j, t]*m.active_members[j]*m.active_members[i] for j in m.member_set) for i in m.member_set)

def P_auto_expr(m, t) : 
    return m.P_self[t] + m.P_commu_exchange[t] - m.P_grid_minus[t]

def p_confort_expr(m, t) : 
    return sum(getattr(m, f'member_{i}').mod_member.p_confort[t]*m.active_members[i] for i in m.member_set)

def t_confort_expr(m) :
    return sum(getattr(m, f'member_{i}').mod_member.t_confort*m.active_members[i] for i in m.member_set)

# ADMM constraints

def surplus_only_admm(m, t, i) :
    S = sum(m.P_exchange[i, j, t]*m.active_members[j]*m.active_members[i] for j in m.member_set)
    # S = what i send to others 
    return S == m.Surplus_repr[i, t]*m.active_members[i]