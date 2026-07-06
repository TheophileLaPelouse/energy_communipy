import math
from functools import reduce
from . import pyo

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

def calc_auto(Pgrid, **kwargs) : 
    deltat = kwargs.get("deltat", 1)
    coef_auto = kwargs.get("coef_auto", 1)
    ref_value = kwargs.get("ref", 1)
    return sum(Pgrid[k]*deltat*coef_auto for k in range(len(Pgrid)))/ref_value

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

    