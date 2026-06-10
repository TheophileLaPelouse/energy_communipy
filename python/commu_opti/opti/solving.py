
from . import pyo, SolverFactory

def solve_model(model, solver="gurobi", options={}) : 
    if not options.get("solver_io") : 
        solver = SolverFactory(solver)
    else : 
        solver = SolverFactory(solver, options.pop("solver_io"))
    
    for key in options : 
        solver.options[key] = options[key]
    results = solver.solve(model)
    return results

def treat_members_admm(self, params) :
    member, solver, solver_options = params
    member.self_optimize(solver, options=solver_options)

    return