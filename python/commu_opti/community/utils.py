import math
from functools import reduce
from pyexpat import model
from . import pyo
# from . import SolverFactory
import numpy as np
import gurobipy as gp
from gurobipy import GRB


def calc_enviro(Pgrid, Pex, Pself, **kwargs) : 
    # Peut être ajouter test pour si viens d'un modèle pyomo ou pas 
    deltat = kwargs.get("deltat", 1)
    carbone_grid = kwargs.get("carbone_grid", 1)
    carbone_commu = kwargs.get("carbone_commu", 0.5)
    ref_value = kwargs.get("ref", 1)
    return (
        sum(Pgrid[k]*deltat*carbone_grid for k in range(len(Pgrid))) 
        + sum(Pex[k]*deltat*carbone_commu for k in range(len(Pex)))
        + sum(Pself[k]*deltat*carbone_commu for k in range(len(Pself)))
        )/ref_value

def calc_auto(Pgrid_plus, Pgrid_minus, **kwargs) : 
    deltat = kwargs.get("deltat", 1)
    coef_auto = kwargs.get("coef_auto", 1)
    ref_value = kwargs.get("ref", 1)
    return sum((Pgrid_plus[k]+Pgrid_minus[k])*deltat*coef_auto for k in range(len(Pgrid_plus)))/ref_value

def calc_eco(Pgrid_plus, Pgrid_minus, Pex, price_buy, price_sell, **kwargs) : 
    deltat = kwargs.get("deltat", 1)
    cost_ex = kwargs.get("cost_ex", 0)
    ref_value = kwargs.get("ref", 1)
    taxes_buy = kwargs.get("turpe_buy", 1)
    taxes_sell = kwargs.get("turpe_sell", 1)
    
    return (
        sum(Pgrid_plus[k]*deltat*price_buy[k]*taxes_buy for k in range(len(Pgrid_plus))) 
        + sum(Pex[k]*deltat*cost_ex*taxes_sell for k in range(len(Pex)))
        + sum(Pgrid_minus[k]*deltat*price_sell[k]*taxes_sell for k in range(len(Pgrid_minus)))
        )/ref_value

def calc_pena_pow(excess_l, excess_u, **pena_args) : 
    coef = pena_args.get("coef_pena", 1)
    ref_value = pena_args.get("ref", 1)
    return sum(excess_l[t] + excess_u[t] for t in range(len(excess_l)))*coef/ref_value

def calc_confort(p_confort, t_confort, charge_confort, **kwargs) : 
    coef_p = kwargs.get("coef_p", 1)
    coef_t = kwargs.get("coef_t", 1)
    coef_c = kwargs.get("coef_c", 1)
    ref_value = kwargs.get("ref", 1)
    return (sum(p_confort[t]*coef_p  for t in range(len(p_confort))) 
            + t_confort*coef_t*len(p_confort) + sum(charge_confort[t]*coef_c for t in range(len(charge_confort))))/ref_value

def calc_invest_cost(PV_cap, PV_present, bat_cap, bat_present, **kwargs) : 
    cost_PV = kwargs.get("cost_PV", 1000)
    cost_PV_min = kwargs.get("PV_min", 0)
    cost_bat = kwargs.get("cost_bat", 500)
    cost_bat_min = kwargs.get("bat_min", 0)
    ref_value = kwargs.get("ref", 1)
    discount_rate = kwargs.get("discount_rate", 0.05)
    lifetime = kwargs.get("lifetime", 10)
    simul_time = kwargs.get("total_time", 24)
    
    PV_price = invest_cost(cost_PV*PV_cap + PV_present*cost_PV_min, discount_rate, lifetime)
    bat_price = invest_cost(cost_bat*bat_cap + bat_present*cost_bat_min, discount_rate, lifetime)
    return (PV_price + bat_price)/ref_value*(simul_time/8760)

def calc_eco_total(Pgrid_plus, Pgrid_minus, Pex, PV_cap, PV_present, bat_cap, bat_present, price_buy, price_sell, **kwargs) :
    eco = calc_eco(Pgrid_plus, Pgrid_minus, Pex, price_buy, price_sell, **kwargs)
    invest = calc_invest_cost(PV_cap, PV_present, bat_cap, bat_present, **kwargs)
    return (eco + invest)
    
    
def invest_cost(initial_cost, discount, lifetime) : 
    return initial_cost*discount/(1-(1+discount)**(-lifetime))

def extract_values(m, dico) :
    for k in range(len(m.devices)) :
        dev = m.devices[k]
        if not dico.get(dev.name) : 
            dico[dev.name] = {
                "Pcons_max" : [], 
                "Pcons_min" : [],
                "Econs" : [], 
            }
        if len(dev.mod.t_set) : 
            dico[dev.name]["Pcons_max"].append(max(pyo.value(dev.mod.Pcons[t]) for t in dev.time_total_set))
            dico[dev.name]["Pcons_min"].append(min(pyo.value(dev.mod.Pcons[t]) for t in dev.time_total_set))
            dico[dev.name]["Econs"].append(sum(pyo.value(dev.mod.Pcons[t]) for t in dev.time_total_set)*m.deltat)
    if not dico.get("Econs") : dico["Econs"] = []
    if not dico.get("Pcons_max") : dico["Pcons_max"] = []
    if not dico.get("Pcons_min") : dico["Pcons_min"] = []
    if not dico.get("Pgrid_max") : dico["Pgrid_max"] = []
    if not dico.get("Pgrid_min") : dico["Pgrid_min"] = []
    if not dico.get("Egrid_plus") : dico["Egrid_plus"] = []
    if not dico.get("Egrid_minus") : dico["Egrid_minus"] = []
    dico["Econs"].append(sum(pyo.value(m.P_cons[t]) for t in m.time_index)*m.deltat)
    dico["Pcons_max"].append(max(pyo.value(m.P_cons[t]) for t in m.time_index))
    dico["Pcons_min"].append(min(pyo.value(m.P_cons[t]) for t in m.time_index))
    dico["Pgrid_max"].append(max(pyo.value(m.P_grid_plus[t]) for t in m.time_index))
    dico["Pgrid_min"].append(min(pyo.value(m.P_grid_minus[t]) for t in m.time_index))
    dico["Egrid_plus"].append(sum(pyo.value(m.P_grid_plus[t]) for t in m.time_index)*m.deltat)
    dico["Egrid_minus"].append(sum(pyo.value(m.P_grid_minus[t]) for t in m.time_index)*m.deltat)
    return dico

    


def coalition_vector(S, n_player):
    a = np.zeros(n_player)
    a[list(S)] = 1.0
    return a
    

def nucleolus(vs, n_player, tol=1e-8):
    """Compute nucleolus

    Args:
        vs (list): [set S of the coalition, value of the coalition] for all coalitions
        n_player (int): Number of players to consider 
    """
            
    to_deactivate = set(range(len(vs)))
    
    mod = gp.Model("nucleolus")
    mod.setParam("OutputFlag", 0)

    x = mod.addVars(n_player, lb=-GRB.INFINITY, name="x")

    eps = mod.addVar(lb=-GRB.INFINITY,name="eps")

    mod.setObjective(eps, GRB.MINIMIZE)
    
    constraints = {}
    
    for k, (S, v) in enumerate(vs):
        expr = gp.quicksum(x[i] for i in S)
        if len(S) == n_player:
            constraints[k] = mod.addConstr(expr == v, name=f"total")
            to_deactivate.remove(k)
        else:
            constraints[k] = mod.addConstr(expr >= v - eps, name=f"coal_{k}")
    
    A = np.zeros((2*n_player, n_player))
    A[0, :] = 1
    r = 1
    rank = np.linalg.matrix_rank(A)
    
    while rank < n_player and to_deactivate:
        previous_r = r
        mod.update()
        mod.optimize()
        if mod.Status != GRB.OPTIMAL:
            raise RuntimeError("Optimization failed")
        
        eps_opti = eps.X
        x_val = np.array([x[i].X for i in range(n_player)])
        print("x_val:",x_val, "eps_opti:", eps_opti)
        to_pop = set()
        flag = False
        for k in to_deactivate : 
            if flag : break
            S, v = vs[k]
            lhs = x_val[list(S)].sum()
            print(f"Checking coalition {S} with value {v}: lhs = {lhs}, rhs = {v - eps_opti}")
            if abs(lhs - (v - eps_opti)) < tol :
                a = coalition_vector(S, n_player)
                old_rank = rank
                A[r, :] = a
                new_rank = np.linalg.matrix_rank(A)
                print(A, new_rank, old_rank, r)
                if new_rank > old_rank :
                    r += 1
                    rank = new_rank
                    if r >= n_player :
                        flag = True
                    constraints[k].RHS = v - eps_opti
                    constraints[k].Sense = GRB.EQUAL
                    to_pop.add(k)
        
        to_deactivate -= to_pop
        if previous_r == r:
            break  # No new constraints were added, exit the loop
            
            
    return x_val
        
        
        
        