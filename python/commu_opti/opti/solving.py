
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
    write_iis(model, file_path, solver=solver)
    
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