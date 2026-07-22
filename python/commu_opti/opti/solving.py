
from . import pyo, SolverFactory
from pyomo.contrib.iis import write_iis
import os 

def solve_model(model, solver="gurobi", options={}) : 
    if not options.get("solver_io") : 
        solver = SolverFactory(solver)
    else : 
        solver = SolverFactory(solver, options.pop("solver_io"))
    
    for key in options : 
        solver.options[key] = options[key]
    results = solver.solve(model)
    return results

def treat_members_admm(params) :
    member, solver, solver_options = params
    member.self_optimize(solver, options=solver_options)
    k_1 = {'id' : member.id, 'vars' : extract_variables_values(member.mod_member)}
    return k_1

def extract_variables_values(model) : 
    values = {}
    for var in model.component_objects(pyo.Var, active=True) :
        values[var.name] = var.extract_values()
    return values

def set_values(model, values) : 
    for var in model.component_objects(pyo.Var, active=True) :
        if var.name in values : 
            var.set_values(values[var.name])
            
            
def debug_model(model, solver="gurobi", file_path="debug.ilp") : 
    try : 
        # solver = pyo.SolverFactory(solver)
        # solver.options["OutputFlag"] = 0
        write_iis(model, file_path, solver=solver)
    except Exception as e :
            print("\nERREUR", e)
            
def debug_community(community, solver="gurobi", folder_path="debug") : 
    if not os.path.exists(folder_path) : 
        os.makedirs(folder_path)
    for member in community.members : 
        file_path = os.path.join(folder_path, f"member_{member.id}.ilp")
        try : 
            write_iis(member.mod_member, file_path, solver=solver)
        except Exception as e :
            print("\nERREUR", e)
    file_path = os.path.join(folder_path, f"community.ilp")
    try : 
        write_iis(community.mod, file_path, solver=solver)
    except Exception as e :
        print("\nERREUR", e)
        
def debug_unbounded(model, solver="gurobi") : 
    # Search for unbounded variables in the model
    unbounded_vars = []
    for var in model.component_objects(pyo.Var, active=True):
        if var.is_indexed():
            if var[0].lb is None or var[0].ub is None:
                unbounded_vars.append(var)
        elif var.lb is None or var.ub is None:
            unbounded_vars.append(var)
            
    solver = pyo.SolverFactory("gurobi")
    solver.options["DualReductions"] = 0

    results = solver.solve(model, tee=False)
    if results.solver.termination_condition.name == "unbounded":
        k = 0
        while results.solver.termination_condition.name == "unbounded":
            if unbounded_vars[k].is_indexed() :
                for index in unbounded_vars[k] :
                    if unbounded_vars[k][index].lb is None :
                        unbounded_vars[k][index].setlb(-1e6)
                    if unbounded_vars[k][index].ub is None :
                        unbounded_vars[k][index].setub(1e6)
            else :
                if unbounded_vars[k].lb is None :
                    unbounded_vars[k].setlb(-1e6)
                if unbounded_vars[k].ub is None :
                    unbounded_vars[k].setub(1e6)
            print(f"Variable {unbounded_vars[k].name} is now bounded")
            results = solver.solve(model, tee=False)
            k +=1
    
def minimal_rolling_opti(community, solving_method, solver, **kwargs) : 
    weather_history = kwargs.get("weather_history", [0 for k in range(24)])
    weather_forecast = kwargs.get("weather_forecast", [0 for k in range(24)])
    irradiance_history = kwargs.get("irradiance_history", [0 for k in range(24)])
    irradiance_forecast = kwargs.get("irradiance_forecast", [0 for k in range(24)])
    price_options = kwargs.get("price_options")
    total_time = kwargs.get("total_time", 24)
    horizon = kwargs.get("horizon", 24)    
    old_weather = [weather_history[0]] + weather_forecast[1:horizon]
    old_irradiance = [irradiance_history[0]] + irradiance_forecast[1:horizon]
    old_price_buy = price_options["eco"]["cost_grid_buy"][:horizon]
    old_price_sell = price_options["eco"]["cost_grid_sell"][:horizon]
    old_prices = {"price_buy" : old_price_buy, "price_sell" : old_price_sell}
    for m in community.members :
        m.reset_horizon(old_weather, old_irradiance, old_prices)
        
    if solving_method == "selves" : 
        community.update_model(custom_active_id=[])  
    if solving_method=="admm_selves" : 
        community.update_model(custom_active_id=[])  
        for m in community.members : 
            m.update_model_admm(custom_active_id=[])
    
    for t in range(kwargs.get("until", total_time - horizon)) :
        print("Starting optimization for time step", t)
        if solving_method == "admm" or solving_method == "admm_selves" : 
            community.optimize_admm(solver, **community.kwargs)
        else : 
            community.optimize(solver, **kwargs.get('solver_options', {}))
        print("\nOptimization finished !", t)
        
        irradiance_t = irradiance_history[t+1]
        new_irradiance = [irradiance_t] + irradiance_forecast[t+2:t+1+horizon]
        weather_t = weather_history[t]
        new_weather = [weather_t] + weather_forecast[t+1:t+horizon]
        new_price_buy = price_options["eco"]["cost_grid_buy"][t+1:t+1+horizon]
        new_price_sell = price_options["eco"]["cost_grid_sell"][t+1:t+1+horizon]
        new_prices = {"price_buy" : new_price_buy, "price_sell" : new_price_sell}

        for i in community.current_members_id : 
            m = community.members[i]
            m.keep_in_memory()
            m.rolling_horizon_update(new_weather, new_irradiance, new_prices)
            
    community.aggregate_distributed_information(from_memory=True)
    return community.results.copy()

    