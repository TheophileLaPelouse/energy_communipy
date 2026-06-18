from . import pyo, np
from .utils import calc_auto, calc_eco, calc_eco_total, calc_enviro, calc_invest_cost, calc_pena_pow, calc_confort
from ..opti.solving import solve_model, treat_members_admm, set_values
from ..plotting.plot_functions import plot_power_curves, plot_hexagon_objective
from .constraint_functions_comm import *
import itertools
import math
import time
from multiprocessing import Pool

import os
import json
path_file = os.path.dirname(os.path.abspath(__file__))
results_path = os.path.join(path_file, "../../results")

class community : 
    def __init__(self, members, **kwargs) : 
        self.kwargs = kwargs
        self.agent = None
        self.mod = pyo.ConcreteModel()
        self.P_exchange = None
        self.U_exchange = None # For ADMM
        self.U_surplus = None # For ADMM
        self.members = members
        self.members_id = [k for k in range(len(members))]
        self.current_members_id = [k for k in range(len(members))]
        self.total_time = kwargs.get('total_time', 24)
        self.deltat = kwargs.get('deltat', 1)
        self.socio = [0, 0, 0, 0]
        
        self.member_set = pyo.Set(initialize=self.members_id)
        self.time_set = pyo.RangeSet(0, self.total_time - 1)
        
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
                
        self.ref_values = kwargs.get("ref_values", [1 for k in range(4)])
                
        calc_ref = kwargs.get("calc_ref", True)
        if calc_ref :
            self.calc_ref_values(**kwargs)
            
            
        self.build_model(**kwargs)
        
    def build_model(self, **kwargs) : 
        
        self.clear_model()
        self.mod.member_set = self.member_set
        self.mod.time_set = self.time_set
        self.mod.active_members = pyo.Param(self.member_set, initialize={i : 1 if i in self.current_members_id else 0 for i in self.members_id}, mutable=True)
        # print("MEMBER SET DEFINED")
        already_done = set()
        self.P_exchange = pyo.Var(self.members_id, self.members_id, self.time_set, within=pyo.NonNegativeReals, initialize=0)
        self.mod.P_exchange = self.P_exchange
                   
        # print("EXCHANGE VARIABLES DEFINED")
        method = kwargs.get("method", "centralized")
        if method == "centralized" :
            for k in self.members_id :
                member = self.members[k]
                member.add_to_community(self, k)
                member.ref_values = self.ref_values
                setattr(self.mod, f"member_{k}", member.mod_member)
                member.build_model(**kwargs)
                getattr(self.mod, f"member_{k}").obj.deactivate()
                member.mod_member.obj.deactivate()
            # print("MEMBER MODELS BUILT")
            self.build_centralized(**kwargs)
            
        if method == "admm" :
            # print("BONJOUR")
            for k in self.members_id :
                member = self.members[k]
                member.add_to_community(self, k, method)
                member.ref_values = self.ref_values
                # print("model kwargs : ", kwargs)
                member.build_model(**kwargs)
            print("MEMBER MODELS BUILT")
            self.build_admm(**kwargs)
    
    def clear_model(self):
        # Remove all variables from the model while keeping other components like devices
        vars_to_remove = [attr for attr in dir(self.mod) if isinstance(getattr(self.mod, attr), (pyo.Var, pyo.Expression, pyo.Constraint, pyo.Objective, pyo.Set, pyo.RangeSet))]
        for var in vars_to_remove:
            delattr(self.mod, var)
            
    def update_model(self) : 
        # For now just update the list of active members, maybe later we'll have other parameters to update.
        self.active_members = {i : 1 if i in self.current_members_id else 0 for i in self.members_id}
        
    def update_devices(self, **kwargs) :
        for k in self.current_members_id : 
            self.members[k].update_devices(**kwargs)
            
    def calc_ref_values(self, **kwargs) :
        """
        Calculate some default values to get reference values for normalization of the different criteria in a decentralized way,
        Could also be used in a more general way for centralized as anyway this basic case removes the exchanges.
        """
        # print("Premier passage")
        ref_values = [0, 0, 0, 0]
        
        for i in self.members_id :
            member_args = {}
            member_args.update(kwargs)
            # print()
            self.members[i].calc_ref_values(**member_args, from_community=True)
            # print(f"Member {i} ref values : ", self.members[i].ref_values)
            for k in range(4) : ref_values[k] += self.members[i].ref_values[k]
            
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
        t0 = time.time()
        results = solve_model(self.mod, solver, **options)
        if self.kwargs["method"] == "centralized" :
            if not self.results.get("centralized") :
                self.results["centralized"] = {}
            if not self.results["centralized"].get("Times") : 
                self.results["centralized"]["Times"] = {}
            self.results["centralized"]["Times"]["self_optimize"] = time.time() - t0
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
            
        self.mod.surplus_only = pyo.Constraint(self.time_set, self.member_set, rule=surplus_only_centralized)
        

        self.mod.ii_rule = pyo.Constraint(self.time_set, self.member_set, rule=ii_rule_centralized)
        
        # Construction of Pgrid, Pcons, Pbat, P_self
        # print("DEFINING VALUES")
        # print("MEMBER IDS : ", members_id)
        
        # Useful for analysis but not necessary for the optimization.
        
        self.mod.P_grid_plus = pyo.Expression(self.time_set, rule=P_grid_plus_expr)
        
        self.mod.P_grid_minus = pyo.Expression(self.time_set, rule=P_grid_minus_expr)
        
        self.mod.P_cons = pyo.Expression(self.time_set, rule=P_cons_expr)
        
        self.mod.P_bat = pyo.Expression(self.time_set, rule=P_bat_expr)
        
        self.mod.P_self = pyo.Expression(self.time_set, rule=P_self_expr)
        
        self.mod.P_prod = pyo.Expression(self.time_set, rule=P_prod_expr)
        
        self.mod.PV_surface = pyo.Expression(rule=PV_surface_expr)
        self.mod.PV_present = kwargs.get("PV_present", 1)
        
        self.mod.bat_cap = pyo.Expression(rule=bat_cap_expr)
        self.mod.bat_present = kwargs.get("bat_present", 1)
        
        # Antisymetry of exchange so we can count all of them positively and divide by 2.
        self.mod.P_commu_exchange = pyo.Expression(self.time_set, rule=P_exchange_expr)
        
        self.mod.P_autoconsume = pyo.Expression(self.time_set, rule=P_auto_expr)
        
        self.mod.p_confort = pyo.Expression(self.time_set, rule=p_confort_expr)
        self.mod.t_confort = pyo.Expression(rule=t_confort_expr)
        
        self.mod.obj = pyo.Objective(expr=sum(self.members[i].mod_member.obj_expr*self.mod.active_members[i] for i in self.mod.member_set), sense=pyo.minimize)
        
        self.price = pyo.Expression(expr=sum(self.members[i].price*self.mod.active_members[i] for i in self.mod.member_set))
        self.price_operation = pyo.Expression(expr=sum(self.members[i].price_operation*self.mod.active_members[i] for i in self.mod.member_set))
        self.price_invest = pyo.Expression(expr=sum(self.members[i].price_invest*self.mod.active_members[i] for i in self.mod.member_set))
        self.enviro = pyo.Expression(expr=sum(self.members[i].enviro*self.mod.active_members[i] for i in self.mod.member_set))
        self.auto = pyo.Expression(expr=sum(self.members[i].auto*self.mod.active_members[i] for i in self.mod.member_set))
        self.confort = pyo.Expression(expr=sum(self.members[i].confort*self.mod.active_members[i] for i in self.mod.member_set))
        
        self.mod.price = self.price
        self.mod.enviro = self.enviro
        self.mod.auto = self.auto
        self.mod.confort = self.confort
        
        
        return 
    
    def build_admm(self, **kwargs) : 
        # Z is the power exchange so we already have it.
        members_id = self.current_members_id
        if self.U_exchange is None : 
            self.U_exchange = pyo.Param(members_id, members_id, self.time_set, initialize=0, mutable=True)
            self.U_surplus = pyo.Param(self.member_set, self.time_set, initialize=0, mutable=True)
            self.mod.U_exchange = self.U_exchange
            self.mod.U_surplus = self.U_surplus
        
        rho = pyo.Param(initialize=1, mutable=True)
        x_k_1 = pyo.Param(members_id, members_id, self.time_set, initialize=0, mutable=True)
        Surplus_k_1 = pyo.Param(self.member_set, self.time_set, initialize=0, mutable=True)
        
        self.mod.rho = rho
        self.mod.x_k_1 = x_k_1
        self.mod.Surplus_k_1 = Surplus_k_1
        
        if not hasattr(self.mod, "Surplus_repr") :
            self.Surplus_repr = pyo.Var(self.member_set, self.time_set, within=pyo.NonNegativeReals, initialize=0)
            self.mod.Surplus_repr =  self.Surplus_repr
        

        if hasattr(self.mod, "surplus_only") :
            del self.mod.surplus_only
        self.mod.surplus_only = pyo.Constraint(self.time_set, self.member_set, rule=surplus_only_admm)
        
        if hasattr(self.mod, "ii_rule") :
            del self.mod.ii_rule
        self.mod.ii_rule = pyo.Constraint(self.time_set, self.member_set, rule=ii_rule_centralized)        

        if hasattr(self.mod, "sqr_pena_expr") :
            del self.mod.sqr_pena_expr
        self.mod.sqr_pena_expr = pyo.Expression(expr=sum((x_k_1[i, j, t] - self.P_exchange[i, j, t]+ self.U_exchange[i, j, t])**2*self.mod.active_members[i]*self.mod.active_members[j]  
                                                    for t in self.time_set 
                                                    for i in self.mod.member_set 
                                                    for j in self.mod.member_set)
                                                    + sum((Surplus_k_1[i, t] - self.Surplus_repr[i, t]+ self.U_surplus[i, t])**2*self.mod.active_members[i]
                                                          for t in self.time_set 
                                                          for i in self.mod.member_set)
                                                )
        
        if hasattr(self.mod, "obj") :
            del self.mod.obj
        self.mod.obj = pyo.Objective(expr=self.mod.rho/2*self.mod.sqr_pena_expr, sense=pyo.minimize)
        
    # def update_params_admm(self, **kwargs) :
    #     self.mod.rho.set_value(kwargs.get("rho", 1))
    #     self.mod.x_k_1.store_values(kwargs.get("x_k_1"))
    #     self.mod.Surplus_k_1.store_values(kwargs.get("Surplus_k_1"))
    
    def optimize_admm(self, solver, **kwargs) :
        
        power_max_random = kwargs.get("power_max_random", 1000)
        rho = kwargs.get("rho", 1/(power_max_random+1))
        mu = kwargs.get("mu", 100)
        tau_incr = kwargs.get("tau_incr", 2)
        tau_decr = kwargs.get("tau_decr", 2)
        
        x_k = kwargs.get("x_k", {(i, j, t) : np.random.rand() * power_max_random for t in self.time_set for i in self.current_members_id for j in self.current_members_id})
        Surplus = kwargs.get("Surplus", {(i, t) : np.random.rand() * power_max_random for t in self.time_set for i in self.current_members_id})
        z_k = kwargs.get("z_k", {(i, j, t) : np.random.rand() * power_max_random for t in self.time_set for i in self.current_members_id for j in self.current_members_id})
        z2_k = kwargs.get("z2_k", {(i, t) : np.random.rand() * power_max_random for t in self.time_set for i in self.current_members_id})
        r_k = 1000000000000
        s_k = 1000000000000
        eps_r = kwargs.get("eps_r", 1e-2)
        eps_s = kwargs.get("eps_s", 1e-2)
        max_iter = kwargs.get("max_iter", 100)
        iter = 0
        
        solver_options = kwargs.get("solver_options", {"MIPGap" : 0.01, 
                                                       "FeasibilityTol" : 1e-2,
                                                       "OptimalityTol" : 1e-2, 
                                                       "Threads": 1})
        
        t_python = 0
        t_optimizer1 = 0
        t_optimizer2 = 0
        
        member_args = {}
        member_args.update(kwargs)
        commu_args = {}
        commu_args.update(kwargs)
        
        
        len1 = len(self.current_members_id)*len(self.time_set)
        len2 = len(self.time_set)
        len3 = len(self.current_members_id)*len(self.current_members_id)*len(self.time_set)
        def dico_to_numpy(dico, array) :
            for key in dico : 
                if len(key) == 3 :
                    i, j, t = key
                    indice = i*len1 + j*len2 + t
                if len(key) == 2 : 
                    i, t = key
                    indice = len3 + i*len2 + t
                array[indice] = dico[key]
            return
                    
                    
        U_numpy = np.array([0. for i in range(len(z_k))] + [0. for i in range(len(z2_k))])
        z_k_numpy = np.array([0. for i in range(len(z_k))] + [0. for i in range(len(z2_k))])
        x_k_1_numpy = np.array([0. for i in range(len(x_k))] + [0. for i in range(len(Surplus))])
        z_k_1_numpy = np.array([0. for i in range(len(z_k))] + [0. for i in range(len(z2_k))])
        
        parallel = kwargs.get("parallel", False)
        if parallel :
            pool = Pool(processes=8) # 8 available on this computer
        
        print("\nStart ADMM iteration")
        t_start = time.time()
        while (r_k > eps_r or s_k > eps_s) and iter < max_iter :
            
            # Save argmin local 
            
            args = {"rho" : rho, "z_k" : z_k, "z2_k" : z2_k, "u_k" : self.U_exchange, "u2_k" : self.U_surplus}
            member_args.update(args)
            
            
            # def treat_members(i) :
            #     member = self.members[i]
            #     member.update_params_admm(**member_args)
            #     # member.build_model(**member_args)
                
            #     t_opti_start = time.time()
            #     member.self_optimize(solver, options=solver_options)
            #     t_optimizer1 += time.time() - t_opti_start
                
            #     for_x_k_1 = member.P_exchange_repr.extract_values()
            #     for_surplus = member.P_surplus.extract_values()
            #     for t in self.time_set :
            #         for j in self.current_members_id : 
            #             self.mod.x_k_1[j, i, t].set_value(for_x_k_1[(j, t)])
            #         self.mod.Surplus_k_1[i, t].set_value(for_surplus[t])
            #     return
            
            if parallel:
                t_opti_start = time.time()
                params = [[self.members[i], solver, solver_options] for i in self.current_members_id]
                
                for i in self.current_members_id :
                    member = self.members[i]
                    member.update_params_admm(**member_args)
                
                k_1 = pool.map(treat_members_admm, params)

                for i in self.current_members_id :                    
                    id_ = k_1[i]['id']
                    member = self.members[id_]
                    for_x_k_1 = k_1[i]['vars']['P_exchange_repr']
                    for_surplus = k_1[i]['vars']['P_surplus']
                    # set_values(member.mod_member, k_1[i]['vars'])
                    # Set values for the next iteration as the paralellization is not updating the members
                    # (what happens in parallel stay in parallel)
                    # member.mod_member.P_exchange_repr.set_values(for_x_k_1)
                    # member.mod_member.P_surplus.set_values(for_surplus)
                    for t in self.time_set :
                        for j in self.current_members_id : 
                            self.mod.x_k_1[j, i, t].set_value(for_x_k_1[(j, t)])
                        self.mod.Surplus_k_1[i, t].set_value(for_surplus[t])
                t_optimizer1 += time.time() - t_opti_start
            
            else : 
                for i in self.current_members_id :
                    member = self.members[i]
                    member.update_params_admm(**member_args)
                    # member.build_model(**member_args)
                    
                    t_opti_start = time.time()
                    member.self_optimize(solver, options=solver_options)
                    t_optimizer1 += time.time() - t_opti_start
                    
                    for_x_k_1 = member.P_exchange_repr.extract_values()
                    for_surplus = member.P_surplus.extract_values()
                    for t in self.time_set :
                        for j in self.current_members_id : 
                            self.mod.x_k_1[j, i, t].set_value(for_x_k_1[(j, t)])
                        self.mod.Surplus_k_1[i, t].set_value(for_surplus[t])
            
            self.mod.rho.set_value(rho)
            
            print("le modèle")
            # self.mod.pprint()
            
            t_opti_start = time.time()
            self.optimize(solver, options=solver_options)
            t_optimizer2 += time.time() - t_opti_start

            r_k = 0
            s_k = 0
            Surplus_repr_values = self.Surplus_repr.extract_values()
            Surplus_k_1_values = self.mod.Surplus_k_1.extract_values()
            P_exchange_values = self.P_exchange.extract_values()
            x_k_1_values = self.mod.x_k_1.extract_values()
            
            z_k.update(z2_k)
            dico_to_numpy(z_k, z_k_numpy)
            x_k_1_values.update(Surplus_k_1_values)
            dico_to_numpy(x_k_1_values, x_k_1_numpy)
            z_k_1_values = {**P_exchange_values, **Surplus_repr_values}
            dico_to_numpy(z_k_1_values, z_k_1_numpy)
            
            r_k = np.linalg.norm(x_k_1_numpy - z_k_1_numpy)
            s_k = np.linalg.norm(z_k_numpy - z_k_1_numpy)*rho
            
            U_numpy = U_numpy + x_k_1_numpy - z_k_1_numpy

            z_k = P_exchange_values
            z2_k = Surplus_repr_values
            
            
            old_rho = rho
            if r_k > mu*s_k :
                rho *= tau_incr
            elif s_k > mu*r_k :
                rho /= tau_decr
            if rho != old_rho :
                U_numpy = U_numpy * old_rho/rho
                
            self.U_exchange.store_values({(i, j, t) : U_numpy[i*len1 + j*len2 + t] for i in self.current_members_id for j in self.current_members_id for t in self.time_set})
            self.U_surplus.store_values({(i, t) : U_numpy[len3 + i*len2 + t] for i in self.current_members_id for t in self.time_set})

            iter += 1
            # print("Surplus : ", Surplus)
            print("\niter, r_k, s_k : ", iter, r_k, s_k)
            print("rho : ", rho)
            
        if parallel :
            for i in self.current_members_id :
                id_ = k_1[i]['id']
                member = self.members[id_]
                set_values(member.mod_member, k_1[i]['vars'])
            
        t_end = time.time()
        t_python = t_end - t_start - t_optimizer1 - t_optimizer2
        t_total = t_end - t_start 
        self.results['admm'] = {"r_k" : r_k, "s_k" : s_k, "iterations" : iter, "final_z_k" : z_k, "final_U_k" : self.U_exchange, "Times" : {"python" : t_python, "optimizer" : t_optimizer1 + t_optimizer2, "local_optimizer" : t_optimizer1, "global_optimizer" : t_optimizer2, "total" : t_total}}
        return not(r_k > eps_r or s_k > eps_s)
    
    
        
    def optimize_selves(self, solver, **options) :
        
        self.mod.obj.deactivate()
        members_gains = []
        members_price = []
        members_comfort = []
        members_eco = []
        
        for i in self.current_members_id : 
            for j in self.current_members_id : 
                self.P_exchange[i, j, :].fix(0)
        
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
                self.P_exchange[i, j, :].unfix()
        
        return {"gains" : members_gains, "price" : members_price, "comfort" : members_comfort, "enviro" : members_eco}
    
    def calc_gains(self, solver, **options) :
        self.current_members_id = self.members_id[:]
        self.update_model()
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
            self.update_model()
            # self.build_model(**kwargs)
            solver = kwargs.get("solver", "gurobi")
            options = kwargs.get("options", {})
            self.optimize(solver, **options)
            
            community_obj = pyo.value(self.mod.obj)
            
            members_details = self.optimize_selves(solver, **options)
            tot_members_obj = sum(members_details["gains"])
            
            # print(f"Combination {comb} : Community obj : {community_obj}, sum of members obj : {tot_members_obj}")
            
            combinations[comb] = tot_members_obj - community_obj
        
        self.current_members_id = [self.members_id[k] for k in range(len(self.members_id))]
        # self.clear_model()
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
        
        self.results['power_exchange_commu'] = [[[pyo.value(self.P_exchange[i, j, t]) for t in self.time_set] for j in self.current_members_id] for i in self.current_members_id]

    def plot_power_curves(self, **kwargs) :
        plot_power_curves(self.total_time, self.deltat, **kwargs)
        
    def plot_hexagon(self, values, members, title="Hexagon Plot") :
        plot_hexagon_objective(values, members, title)
        
        