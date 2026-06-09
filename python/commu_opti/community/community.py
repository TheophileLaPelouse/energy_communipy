from . import pyo, np
from .utils import calc_auto, calc_eco, calc_eco_total, calc_enviro, calc_invest_cost, calc_pena_pow, calc_confort
from ..opti.solving import solve_model
from ..plotting.plot_functions import plot_power_curves, plot_hexagon_objective
import itertools
import math
import time

import os
import json
path_file = os.path.dirname(os.path.abspath(__file__))
results_path = os.path.join(path_file, "../../results")

class community : 
    def __init__(self, members, **kwargs) : 
        self.kwargs = kwargs
        self.agent = None
        self.mod = pyo.ConcreteModel()
        self.P_exchange = [[None for k in range(len(members))] for i in range(len(members))]
        self.U_exchange = None # For ADMM
        self.U_surplus = None # For ADMM
        self.members = members
        self.members_id = [k for k in range(len(members))]
        self.current_members_id = [k for k in range(len(members))]
        self.total_time = kwargs.get('total_time', 24)
        self.deltat = kwargs.get('deltat', 1)
        self.socio = [0, 0, 0, 0]
        
        self.members_obj = []
        self.members_price = []
        self.members_details = {}
        self.community_obj = 0
        self.community_price = 0
        self.tot_obj_gains = 0
        self.price_gains = 0
        self.members_gains = {}
        self.tot_members_obj = 0
        self.money_gains = 0
        
        self.combinations = None
        
        self.results = {}
        
        nb_member = len(self.members_id)
        for i in self.members_id : 
            for k in range(4):
                self.socio[k] += self.members[i].socio[k]/nb_member
                
        self.ref_values = kwargs.get("ref_values", [1 for k in range(len(self.socio)+1)])
                
        calc_ref = kwargs.get("calc_ref", True)
        if calc_ref :
            self.calc_ref_values(**kwargs)
            
            
        self.build_model(**kwargs)
        
    def build_model(self, **kwargs) : 
        
        self.clear_model()
        members_id = self.current_members_id
        self.time_set = pyo.RangeSet(0, self.total_time - 1)
        self.member_set = pyo.Set(initialize=members_id)
        self.mod.member_set = self.member_set
        # print("MEMBER SET DEFINED")
        already_done = set()
        for i in self.members_id :
            for j in self.members_id : 
                    # On ne compte que les échanges positifs.
                    if i not in self.member_set or j not in self.member_set :
                        self.P_exchange[i][j]  = 0
                    elif i==j : 
                        if not (i, j) in already_done : 
                            self.P_exchange[i][j] = pyo.Var(self.time_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_set])
                            self.mod.add_component(f"P_exchange_{i}_{j}", self.P_exchange[i][j])
                            already_done.add((i, j))
                    else : 
                        self.P_exchange[i][j] = pyo.Var(self.time_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_set])
                        self.mod.add_component(f"P_exchange_{i}_{j}", self.P_exchange[i][j])
                   
        # print("EXCHANGE VARIABLES DEFINED")
        method = kwargs.get("method", "centralized")
        if method == "centralized" :
            for k in self.members_id :
                if k not in self.member_set : 
                    if hasattr(self.mod, f"member_{k}") : 
                        delattr(self.mod, f"member_{k}")
                else : 
                    member = self.members[k]
                    member.add_to_community(self, k)
                    member.ref_values = self.ref_values
                    member.build_model(**kwargs)
                    member.mod_member.obj.deactivate()
            # print("MEMBER MODELS BUILT")
            self.build_centralized(**kwargs)
            
        if method == "admm" :
            print("BONJOUR")
            for k in self.members_id :
                print(k)
                if k not in self.member_set : 
                    if hasattr(self.mod, f"member_{k}") : 
                        delattr(self.mod, f"member_{k}")
                else : 
                    member = self.members[k]
                    member.add_to_community(self, k)
                    member.ref_values = self.ref_values
                    print("model kwargs : ", kwargs)
                    member.build_model(**kwargs)
            print("MEMBER MODELS BUILT")
            self.build_admm(**kwargs)
    
    def clear_model(self):
        # Remove all variables from the model while keeping other components like devices
        vars_to_remove = [attr for attr in dir(self.mod) if isinstance(getattr(self.mod, attr), (pyo.Var, pyo.Expression, pyo.Constraint, pyo.Objective, pyo.Set, pyo.RangeSet))]
        for var in vars_to_remove:
            delattr(self.mod, var)
            
    def calc_ref_values(self, **kwargs) :
        """
        Calculate some default values to get reference values for normalization of the different criteria in a decentralized way,
        Could also be used in a more general way for centralized as anyway this basic case removes the exchanges.
        """
        ref_values = [0, 0, 0, 0]
        self.build_model(**kwargs)
        for i in self.members_id :
            self.members[i].fix_device_values()
            self.members[i].mod_member.obj.activate()
            solver = kwargs.get("ref_solver", "gurobi")
            results = solve_model(self.members[i].mod_member, solver, **kwargs.get("ref_options", {}))
            objs = self.members[i].send_obj_information()
            ref_values[0] += objs["price"]
            ref_values[1] += objs["enviro"]
            ref_values[2] += objs["auto"]
            ref_values[3] += objs["confort"]
            
        self.ref_values = ref_values
        for k in range(len(self.ref_values)) :
            if self.ref_values[k] == 0 and k != 3 : 
                print("WARNING : REF VALUE IS 0, PROBLEM IN NORMALIZATION, REF VALUES : ", self.ref_values)
                self.ref_values = [1 for val in self.ref_values]
                print("REF VALUES SET TO 1")
                break
            if self.ref_values[k] == 0 and k == 3 : 
                self.ref_values[k] = 1 # Confort is not studied in this case 
        
        for i in self.members_id :
            self.members[i].unfix_device_values()
        
        return 
    
    # def calc_ref_values(self, **kwargs) : 
    #     """
    #     Run the optimization with some default values to get reference values for normalization of the different criteria
    #     """
    #     self.build_model(**kwargs)
    #     for i in self.members_id :
    #         self.members[i].fix_device_values()
            
    #     for i in self.members_id : 
    #         for j in self.members_id : 
    #             if self.P_exchange[i][j] is not None : 
    #                 self.P_exchange[i][j].fix(0)
        
    #     solver = kwargs.get("ref_solver", "gurobi")
    #     results = solve_model(self.mod, solver, **kwargs.get("ref_options", {}))
    #     self.ref_values = [pyo.value(self.price), pyo.value(self.enviro), pyo.value(self.auto), pyo.value(self.confort)]
    
    #     for k in range(len(self.ref_values)) :
    #         if self.ref_values[k] == 0 and k != 3 : 
    #             print("WARNING : REF VALUE IS 0, PROBLEM IN NORMALIZATION, REF VALUES : ", self.ref_values)
    #             self.ref_values = [1 for val in self.ref_values]
    #             print("REF VALUES SET TO 1")
    #             break
    #         if self.ref_values[k] == 0 and k == 3 : 
    #             self.ref_values[k] = 1 # Confort is not studied in this case 
        
    #     for i in self.members_id :
    #         self.members[i].unfix_device_values()
        
    #     self.clear_model()
    #     return 
    
    def create_agent(self) : 
        # Create just the agent for the community and link the members
        return 
    
    def create_agents(self) : 
        # Agents for all member at the time
        return
    
    def add_member(self, member) : 
        # For later because not as useful.
        return
    
    def optimize(self, solver, **options) : 
        results = solve_model(self.mod, solver, **options)
        return results
    
    def save_model_results(self, filename=os.path.join(results_path, "community_results.json")) : 
        if not os.path.exists(results_path) : 
            os.makedirs(results_path)
        results = {
            "community_obj" : pyo.value(self.mod.obj),
            "community_price" : pyo.value(self.mod.price),
            "community_enviro" : pyo.value(self.mod.enviro),
            "community_auto" : pyo.value(self.mod.auto),
            "community_confort" : pyo.value(self.mod.confort)
        }
        
        
        var_values = {}
        for v in self.mod.component_objects((pyo.Var, pyo.Expression), active=True) :
            if v.is_indexed() : 
                values = []
                for index in v :
                    values.append((index, pyo.value(v[index])))
                var_values[str(v.getname())] = values
            else : 
                var_values[str(v.getname())] = pyo.value(v)
        
        results["model_values"] = var_values
        
        results["gains"] = self.members_gains
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=4)
        return
            
    
    def build_centralized(self, **kwargs) :
        
        members_id = self.current_members_id
        
        for id_ in members_id : 
            setattr(self.mod, f"member_{id_}", self.members[id_].mod_member)
            getattr(self.mod, f"member_{id_}").obj.deactivate()
            
        def surplus_only(m, t, i) :
            S = sum(self.P_exchange[i][j][t] for j in members_id)
            # S = what i send to others 
            return S == self.members[i].P_surplus[t]
        self.mod.surplus_only = pyo.Constraint(self.time_set, self.member_set, rule=surplus_only)
        
        def ii_rule(m, t, i) : 
            return self.P_exchange[i][i][t] == 0
        self.mod.ii_rule = pyo.Constraint(self.time_set, self.member_set, rule=ii_rule)
        
        # Construction of Pgrid, Pcons, Pbat, P_self
        # print("DEFINING VALUES")
        # print("MEMBER IDS : ", members_id)
        
        # Useful for analysis but not necessary for the optimization.
        
        self.mod.P_grid_plus = pyo.Expression(self.time_set, rule=lambda m, t: sum(
            self.members[i].P_grid_plus[t] for i in members_id))
        
        self.mod.P_grid_minus = pyo.Expression(self.time_set, rule=lambda m, t: sum(
            self.members[i].P_grid_minus[t] for i in members_id))
        
        self.mod.P_cons = pyo.Expression(self.time_set, rule=lambda m, t: sum(
            self.members[i].P_cons[t] for i in members_id))
        
        self.mod.P_bat = pyo.Expression(self.time_set, rule=lambda m, t: sum(
            self.members[i].P_bat[t] for i in members_id))
        
        self.mod.P_self = pyo.Expression(self.time_set, rule=lambda m, t: sum(
            self.members[i].P_self[t] for i in members_id))
        
        self.mod.P_prod = pyo.Expression(self.time_set, rule=lambda m, t: sum(
            self.members[i].P_prod[t] for i in members_id))
        
        self.mod.PV_surface = pyo.Expression(rule=lambda m: sum(
            self.members[i].PV_surface for i in members_id))
        self.mod.PV_present = kwargs.get("PV_present", 1)
        
        self.mod.bat_cap = pyo.Expression(rule=lambda m: sum(
            self.members[i].bat_cap for i in members_id))
        self.mod.bat_present = kwargs.get("bat_present", 1)
        
        # Antisymetry of exchange so we can count all of them positively and divide by 2.
        self.mod.P_commu_exchange = pyo.Expression(self.time_set, rule=lambda m, t: sum(
            sum(self.P_exchange[i][j][t] for j in members_id) for i in members_id))
        
        self.mod.P_autoconsume = pyo.Expression(self.time_set, rule=lambda m, t: 
            self.mod.P_self[t] + self.mod.P_commu_exchange[t] - self.mod.P_grid_minus[t])
        
        self.mod.p_confort = pyo.Expression(self.time_set, rule=lambda m, t: 
            sum(self.members[i].mod_member.p_confort[t] for i in members_id))
        self.mod.t_confort = pyo.Expression(rule=lambda m: 
            sum(self.members[i].mod_member.t_confort for i in members_id))
        
        self.mod.obj = pyo.Objective(expr=sum(self.members[i].mod_member.obj_expr for i in members_id))
        
        self.price = pyo.Expression(expr=sum(self.members[i].price for i in members_id))
        self.price_operation = pyo.Expression(expr=sum(self.members[i].price_operation for i in members_id))
        self.price_invest = pyo.Expression(expr=sum(self.members[i].price_invest for i in members_id))
        self.enviro = pyo.Expression(expr=sum(self.members[i].enviro for i in members_id))
        self.auto = pyo.Expression(expr=sum(self.members[i].auto for i in members_id))
        self.confort = pyo.Expression(expr=sum(self.members[i].confort for i in members_id))
        
        self.mod.price = self.price
        self.mod.enviro = self.enviro
        self.mod.auto = self.auto
        self.mod.confort = self.confort
        
        
        return 
    
    def build_admm(self, **kwargs) : 
        # Z is the power exchange so we already have it.
        if self.U_exchange is None : 
            self.U_exchange = np.array([[[0. for t in self.time_set] for k in range(len(self.members_id))] for i in range(len(self.members_id))])
            self.U_surplus = np.array([[0. for t in self.time_set] for i in range(len(self.members_id))])
        rho = kwargs.get("rho", 1)
        x_k_1 = kwargs.get("x_k_1", np.array([[[0. for t in self.time_set] for k in range(len(self.members_id))] for i in range(len(self.members_id))]))
        Surplus = kwargs.get("Surplus", np.array([[0. for t in self.time_set] for i in range(len(self.members_id))]))

        members_id = self.current_members_id
        
        if not hasattr(self.mod, "Surplus_repr") :
            self.Surplus_repr = pyo.Var(self.member_set, self.time_set, within=pyo.NonNegativeReals, initialize=0)
            self.mod.Surplus_repr =  self.Surplus_repr
        
        def surplus_only(m, t, i) :
            S = sum(self.P_exchange[i][j][t] for j in members_id)
            # S = what i send to others 
            return S == m.Surplus_repr[i, t]
        if hasattr(self.mod, "surplus_only") :
            del self.mod.surplus_only
        self.mod.surplus_only = pyo.Constraint(self.time_set, self.member_set, rule=surplus_only)
        
        def ii_rule(m, t, i) : 
            return self.P_exchange[i][i][t] == 0
        if hasattr(self.mod, "ii_rule") :
            del self.mod.ii_rule
        self.mod.ii_rule = pyo.Constraint(self.time_set, self.member_set, rule=ii_rule)        

        if hasattr(self.mod, "sqr_pena_expr") :
            del self.mod.sqr_pena_expr
        self.mod.sqr_pena_expr = pyo.Expression(expr=sum((x_k_1[i][j][t] - self.P_exchange[i][j][t] + self.U_exchange[i][j][t])**2 
                                                    for t in self.time_set 
                                                    for i in members_id 
                                                    for j in members_id)
                                                    + sum((Surplus[i][t] - self.Surplus_repr[i, t] + self.U_surplus[i][t])**2 
                                                          for t in self.time_set 
                                                          for i in members_id)
                                                )
        
        if hasattr(self.mod, "obj") :
            del self.mod.obj
        self.mod.obj = pyo.Objective(expr=rho/2*self.mod.sqr_pena_expr, sense=pyo.minimize)
        
    def optimize_admm(self, solver, **kwargs) :
        rho = kwargs.get("rho", 1)
        power_max_random = kwargs.get("power_max_random", 1000)
        
        x_k = kwargs.get("x_k", np.array([[[np.random.rand() * power_max_random for t in self.time_set] for k in range(len(self.members_id))] for i in range(len(self.members_id))]))
        Surplus = kwargs.get("Surplus", np.array([[np.random.rand() * power_max_random for t in self.time_set] for i in range(len(self.members_id))]))
        z_k = np.array([[[np.random.rand() * power_max_random for t in self.time_set] for k in range(len(self.members_id))] for i in range(len(self.members_id))]) # Power exchange
        z2_k = np.array([[np.random.rand() * power_max_random for t in self.time_set] for i in range(len(self.members_id))]) # Power surplus for each member
        r_k = 1000
        s_k = 1000
        eps_r = kwargs.get("eps_r", 1e-3)
        eps_s = kwargs.get("eps_s", 1e-3)
        max_iter = kwargs.get("max_iter", 100)
        iter = 0
        
        solver_options = kwargs.get("solver_options", {})
        
        t_python = 0
        t_optimizer = 0
        
        member_args = {}
        member_args.update(kwargs)
        commu_args = {}
        commu_args.update(kwargs)
        
        t_start = time.time()
        while (r_k > eps_r or s_k > eps_s) and iter < max_iter :
            # Save argmin local 
            
            args = {"rho" : rho, "z_k" : z_k, "z2_k" : z2_k, "u_k" : self.U_exchange, "u2_k" : self.U_surplus}
            member_args.update(args)
            
            for i in self.current_members_id :
                member = self.members[i]
                member.build_model(**member_args)
                
                t_opti_start = time.time()
                member.self_optimize(solver, **solver_options)
                t_optimizer += time.time() - t_opti_start
                
                # self.P_exchange_repr[k][self.id][t]
                for t in self.time_set :
                    for j in self.current_members_id : 
                        x_k[j, i, t] = pyo.value(member.P_exchange_repr[j][i][t])
                    Surplus[i, t] = pyo.value(member.P_surplus[t])
            args = {"rho" : rho, "x_k_1" : x_k, "Surplus" : Surplus}
            commu_args.update(args)
            self.build_admm(**commu_args)
            
            t_opti_start = time.time()
            self.optimize(solver, **solver_options)
            t_optimizer += time.time() - t_opti_start
            
            r_k = 0
            s_k = 0
            for i in self.current_members_id :
                for t in self.time_set : 
                    new_z2 = pyo.value(self.Surplus_repr[i, t])
                    r_k += (Surplus[i][t] - new_z2)**2
                    s_k += (new_z2 - z2_k[i][t])**2
                    self.U_surplus[i][t]  += Surplus[i][t] - new_z2
                    z2_k[i][t] = new_z2
                    for j in self.current_members_id : 
                        new_z = pyo.value(self.P_exchange[i][j][t])
                        print(f"i {i} j {j} t {t} : x_k {x_k[i][j][t]}, z_k {z_k[i][j][t]}, new_z {new_z}, u_k {self.U_exchange[i][j][t]}")
                        r_k += (x_k[i][j][t] - new_z)**2
                        s_k += (new_z - z_k[i][j][t])**2
                        self.U_exchange[i][j][t]  += x_k[i][j][t] - new_z
                        z_k[i][j][t] = new_z
            r_k = math.sqrt(r_k)
            s_k = math.sqrt(s_k)*rho
            
            iter += 1
            print("Surplus : ", Surplus)
            print("\niter, r_k, s_k : ", iter, r_k, s_k)
            
            
            
        t_end = time.time()
        t_python = t_end - t_start - t_optimizer
        t_total = t_end - t_start 
        self.results['admm'] = {"r_k" : r_k, "s_k" : s_k, "iterations" : iter, "final_z_k" : z_k, "final_U_k" : self.U_exchange, "Times" : {"python" : t_python, "optimizer" : t_optimizer, "total" : t_total}}
    
    def optimize_selves(self, solver, **options) :
        
        self.mod.obj.deactivate()
        members_gains = []
        members_price = []
        members_comfort = []
        members_eco = []
        
        for i in self.current_members_id : 
            for j in self.current_members_id : 
                if self.P_exchange[i][j] is not None : 
                    self.P_exchange[i][j].fix(0)
        
        for i in self.current_members_id :
            self.members[i].mod_member.obj.activate()
            self.members[i].self_optimize(solver, **options)
            self.members[i].mod_member.obj.deactivate()
            member_obj = pyo.value(self.members[i].mod_member.obj)
            member_price = pyo.value(self.members[i].mod_member.price)
            members_gains.append(member_obj)
            members_price.append(member_price)
            members_comfort.append(pyo.value(self.members[i].mod_member.confort))
            members_eco.append(pyo.value(self.members[i].mod_member.enviro))
            
        self.mod.obj.activate()
        for i in self.current_members_id : 
            for j in self.current_members_id : 
                if self.P_exchange[i][j] is not None : 
                    self.P_exchange[i][j].unfix()
        
        return {"gains" : members_gains, "price" : members_price, "comfort" : members_comfort, "enviro" : members_eco}
    
    def calc_gains(self, solver, **options) :
        self.current_members_id = self.members_id[:]
        kwargs = self.kwargs
        self.build_model(**kwargs)
        results = self.optimize(solver, **options)
        community_obj = pyo.value(self.mod.obj)
        community_price = pyo.value(self.mod.price)
        # print(f"Community objective value: {community_obj}")
        results = self.optimize_selves(solver, **options)
        members_gains = results["gains"]
        members_price = results["price"]
        
        self.members_obj = members_gains
        self.members_price = members_price
        self.members_details = results
        self.community_obj = community_obj
        self.community_price = community_price
        self.tot_members_obj = sum(members_gains)
        self.tot_obj_gains = self.tot_members_obj - community_obj
        self.money_gains = sum(members_price) - community_price
        
        # print(f"Community objective gain: {self.tot_obj_gains}")
        self.price_gains = sum(members_price) - community_price
                    
        return
        
    def distribute_gains(self, method="proportional") : 
        # Proportional to the gain of each member alone. 
        total_gains = self.tot_obj_gains
        if method == "proportional" : 
            # pas bon 
            self.members_gains["proportional"] = {}
            for i in self.members_id : 
                cost = self.members_obj[i]
                s_abs = sum(abs(self.members_obj[k]) for k in self.members_id)
                abs_cost = abs(cost)
                cost_prop = cost + abs_cost/s_abs*(self.community_obj - self.tot_members_obj)
                gain = self.members_obj[i] - cost_prop
                prop = gain/total_gains if total_gains != 0 else 0
                self.members_gains["proportional"][i] = (gain, prop)
                # print(f"Member {i} gain : {gain}, cost : {cost}, prop : {prop}")
                
        elif method == "equal" :
            gain = total_gains/len(self.members_id)
            self.members_gains["equal"] = {}
            for i in self.members_id : 
                self.members_gains["equal"][i] = (gain, gain/total_gains if total_gains != 0 else 0)
                # print(f"Member {i} gain : {gain}")
                
        elif method == "shapley" : 
            self.members_gains["shapley"] = {}
            combinations = {}
            n = len(self.members_id)
            for k in range(1, n+1) : 
                for comb in itertools.combinations(self.members_id, k) : 
                    combinations[comb] = None
            combinations = self.compute_combinations(combinations)
            self.combinations = combinations
            for m in self.members_id : 
                gain = self.marginal_contribution_sum(m, combinations)
                self.members_gains["shapley"][m] = (gain, gain/total_gains if total_gains != 0 else 0)
                # print(f"Member {m} gain : {gain}")
        return
    
    def compute_combinations(self, combinations) :
        # Si vraiment trop long, faudra réécrire en faisant les choses dans le bon ordre 
        # pour ne pas faire 25 boucles différentes.
        for comb in combinations :
            # print("combinaison", comb)
            self.current_members_id = list(comb)
            kwargs = self.kwargs 
            self.build_model(**kwargs)
            solver = kwargs.get("solver", "gurobi")
            options = kwargs.get("options", {})
            self.optimize(solver, **options)
            
            community_obj = pyo.value(self.mod.obj)
            
            members_details = self.optimize_selves(solver, **options)
            tot_members_obj = sum(members_details["gains"])
            
            # print(f"Combination {comb} : Community obj : {community_obj}, sum of members obj : {tot_members_obj}")
            
            combinations[comb] = tot_members_obj - community_obj
        
        self.current_members_id = [self.members_id[k] for k in range(len(self.members_id))]
        self.clear_model()
        return combinations 
    
    def marginal_contribution_sum(self, member_id, combinations) :
        # Compute the marginal contribution of a member to a given combination of members
        n = len(self.members_id)
        s = 0
        # Probably can be optimized by computing all marginal contributions at the same time
        for comb in combinations : 
            if member_id in comb : 
                comb_without_i = tuple(m for m in comb if m != member_id)
                gain_with_i = combinations[comb]
                if comb_without_i == () : 
                    gain_without_i = 0
                else : 
                    gain_without_i = combinations[comb_without_i] 
                s += (gain_with_i - gain_without_i)/math.comb(n-1, len(comb)-1)/n
        return s
                
    def aggregate_distributed_information(self, privacy=0) : 
        powers = {}
        for i in self.current_members_id :
            member_power = self.members[i].send_power_information(privacy=privacy)
            self.results[f'members_{i}'] = {}
            for key, value in member_power.items() :
                self.results[f'members_{i}'][key] = value
                if key not in powers :
                    powers[key] = value
                else :
                    for k in range(len(value)) : 
                        powers[key][k] += value[k]
                        
        objs = {}
        for i in self.current_members_id :
            member_obj = self.members[i].send_obj_information()
            for key, value in member_obj.items() :
                self.results[f'members_{i}'][key] = value
                if key not in objs :
                    objs[key] = value
                else :
                    objs[key] += value

        self.results['aggregated_powers'] = powers
        self.results['aggregated_objs'] = objs
        
        self.results['power_exchange_commu'] = [[[pyo.value(self.P_exchange[i][j][t]) for t in self.time_set] for j in self.current_members_id] for i in self.current_members_id]

    def plot_power_curves(self, **kwargs) :
        plot_power_curves(self.total_time, self.deltat, **kwargs)
        
    def plot_hexagon(self, values, members, title="Hexagon Plot") :
        plot_hexagon_objective(values, members, title)
        
        