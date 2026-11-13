from . import pyo, np
from .utils import nucleolus, choose_combination, random_factor
from ..opti.solving import solve_model, treat_members_admm, set_values, debug_community, minimal_rolling_opti
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

from .utils import centralized_methods

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
            print("Computing reference values")
            self.calc_ref_values(**kwargs)
            
        print("Building community model")
        self.build_model(**kwargs)
        
    def build_model(self, **kwargs) : 
        
        self.clear_model()
        self.mod.member_set = self.member_set
        self.mod.time_set = self.time_set
        self.mod.active_members = pyo.Param(self.member_set, initialize={i : 1 if i in self.current_members_id else 0 for i in self.members_id}, mutable=True)
        self.mod.active_members_obj= pyo.Param(self.member_set, initialize={i : 1 if i in self.current_members_id else 0 for i in self.members_id}, mutable=True)
        # print("MEMBER SET DEFINED")
        already_done = set()
        self.P_exchange = pyo.Var(self.members_id, self.members_id, self.time_set, within=pyo.NonNegativeReals, initialize=0)
        self.mod.P_exchange = self.P_exchange
                   
        # print("EXCHANGE VARIABLES DEFINED")
        method = kwargs.get("method", "centralized")
        if method in centralized_methods :
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
                commu = {
                    "members_id" : self.members_id[:],
                    "member_set" : set(self.member_set),
                    "current_members_id" : self.current_members_id[:],
                }
                member.add_to_community(commu, k)
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
            
    def update_model(self, custom_active_id=None, custom_independant_id=None) : 
        # For now just update the list of active members
        # print("Updating model with custom_active_id: ", custom_active_id, " and custom_independant_id: ", custom_independant_id)
        if custom_active_id is not None : 
            self.mod.active_members.store_values({i : 1 if i in custom_active_id else 0 for i in self.members_id})
        else : 
            self.mod.active_members.store_values({i : 1 if i in self.current_members_id else 0 for i in self.members_id})
        if custom_independant_id is not None : 
            self.mod.active_members_obj.store_values({i : 1 if i in custom_independant_id else 0 for i in self.members_id})
        else : 
            self.mod.active_members_obj.store_values({i : 1 if i in self.current_members_id else 0 for i in self.members_id})
    
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
        # Optimize the community model
        t0 = time.time()
        results = solve_model(self.mod, solver, **options)
        #verify if solved to optimality
        if self.kwargs["method"] == "centralized" :
            self.results["solving_status"] = str(results.solver.termination_condition)
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
        
        # Power exchange constraints 
        
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
        
        self.mod.P_commu_exchange = pyo.Expression(self.time_set, rule=P_exchange_expr)
        
        self.mod.P_autoconsume = pyo.Expression(self.time_set, rule=P_auto_expr)
        
        self.mod.p_confort = pyo.Expression(self.time_set, rule=p_confort_expr)
        self.mod.t_confort = pyo.Expression(rule=t_confort_expr)
        
        # Objective function
        self.mod.obj = pyo.Objective(expr=sum(self.members[i].mod_member.obj_expr*self.mod.active_members_obj[i] for i in self.mod.member_set), sense=pyo.minimize)
        
        self.price = pyo.Expression(expr=sum(self.members[i].price*self.mod.active_members_obj[i] for i in self.mod.member_set))
        self.price_operation = pyo.Expression(expr=sum(self.members[i].price_operation*self.mod.active_members_obj[i] for i in self.mod.member_set))
        self.price_invest = pyo.Expression(expr=sum(self.members[i].price_invest*self.mod.active_members_obj[i] for i in self.mod.member_set))
        self.enviro = pyo.Expression(expr=sum(self.members[i].enviro*self.mod.active_members_obj[i] for i in self.mod.member_set))
        self.auto = pyo.Expression(expr=sum(self.members[i].auto*self.mod.active_members_obj[i] for i in self.mod.member_set))
        self.confort = pyo.Expression(expr=sum(self.members[i].confort*self.mod.active_members_obj[i] for i in self.mod.member_set))
        
        self.mod.price = self.price
        self.mod.enviro = self.enviro
        self.mod.auto = self.auto
        self.mod.confort = self.confort
        
        
        return 
    
    def build_admm(self, **kwargs) : 
        # We want to have as global variables the power exchanges between members. Surplus here is the power sent to the community by the members.
        members_id = self.current_members_id
        # U is the dual variable for the power exchanges and the surplus. 
        if self.U_exchange is None : 
            self.U_exchange = pyo.Param(members_id, members_id, self.time_set, initialize=0, mutable=True)
            self.U_surplus = pyo.Param(self.member_set, self.time_set, initialize=0, mutable=True)
            self.mod.U_exchange = self.U_exchange
            self.mod.U_surplus = self.U_surplus
        
        rho = pyo.Param(initialize=1, mutable=True)
        # x at step k+1
        x_k_1 = pyo.Param(members_id, members_id, self.time_set, initialize=0, mutable=True)
        Surplus_k_1 = pyo.Param(self.member_set, self.time_set, initialize=0, mutable=True)
        
        self.mod.rho = rho
        self.mod.x_k_1 = x_k_1
        self.mod.Surplus_k_1 = Surplus_k_1
        
        if not hasattr(self.mod, "Surplus_repr") :
            # Z value in the ADMM algorithm
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
        self.mod.sqr_pena_expr1 = pyo.Expression(expr=sum((x_k_1[i, j, t] - self.P_exchange[i, j, t]+ self.U_exchange[i, j, t])**2*self.mod.active_members[i]*self.mod.active_members[j]  
                                                    for t in self.time_set 
                                                    for i in self.mod.member_set 
                                                    for j in self.mod.member_set)
                                                 )
        self.mod.sqr_pena_expr2 = pyo.Expression(expr=sum((Surplus_k_1[i, t] - self.Surplus_repr[i, t]+ self.U_surplus[i, t])**2*self.mod.active_members_obj[i]
                                                          for t in self.time_set 
                                                          for i in self.mod.member_set)
                                                )
        
        if hasattr(self.mod, "obj") :
            del self.mod.obj
        self.mod.obj = pyo.Objective(expr=self.mod.rho/2*(self.mod.sqr_pena_expr1 + self.mod.sqr_pena_expr2), sense=pyo.minimize)
        
    # def update_params_admm(self, **kwargs) :
    #     self.mod.rho.set_value(kwargs.get("rho", 1))
    #     self.mod.x_k_1.store_values(kwargs.get("x_k_1"))
    #     self.mod.Surplus_k_1.store_values(kwargs.get("Surplus_k_1"))
    
    def init_admm(self, init_function_, time_set, current_members_id, **kwargs) : 
        power_max_random = kwargs.get("power_max_random", 1000)
        if init_function_ == "random" : 
            
            x_k = kwargs.get("x_k", {(i, j, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id for j in current_members_id})
            Surplus = kwargs.get("Surplus", {(i, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id})
            z_k = kwargs.get("z_k", {(i, j, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id for j in current_members_id})
            z2_k = kwargs.get("z2_k", {(i, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id})
        
        if init_function_ == "heuristic" : 
            print("Initializing ADMM with heuristic optimization")
            print(kwargs.get("for_initialization"))
            active_members = self.mod.active_members.extract_values()
            active_members_obj = self.mod.active_members_obj.extract_values()
            heuristic_exchange = self.heuristic_optimization(for_initialization=True, **kwargs)
            print("WHO", active_members, active_members_obj)
            self.update_model(custom_active_id=active_members, custom_independant_id=active_members_obj)
            for i in self.current_members_id :
                member = self.members[i]
                member.update_model_admm(custom_active_id=active_members)
            
            fac = kwargs.get("random_factor", 0.1)
            x_k = {key : heuristic_exchange[key]*random_factor(fac) + np.random.rand()*power_max_random for key in heuristic_exchange}
            z_k = {key : heuristic_exchange[key]*random_factor(fac) + np.random.rand()*power_max_random for key in heuristic_exchange}
            
            Surplus = {(i, t) : sum(heuristic_exchange[i, j, t]*random_factor(fac) + np.random.rand()*power_max_random for j in current_members_id) for t in time_set for i in current_members_id}
            z2_k = {(i, t) : sum(heuristic_exchange[i, j, t]*random_factor(fac) + np.random.rand()*power_max_random for j in current_members_id) for t in time_set for i in current_members_id}
            
            # x_k = kwargs.get("x_k", {(i, j, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id for j in current_members_id})
            # Surplus = kwargs.get("Surplus", {(i, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id})
            # z_k = kwargs.get("z_k", {(i, j, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id for j in current_members_id})
            # z2_k = kwargs.get("z2_k", {(i, t) : np.random.rand() * power_max_random for t in time_set for i in current_members_id})
                    
            
            for id_ in self.current_members_id : 
                member = self.members[id_]
                x_k_member = {(j, t) : x_k[j, id_, t] for j in self.current_members_id for t in time_set}
                Surplus_member = {t : Surplus[id_, t] for t in time_set}
                member.init_values(x_k=x_k_member, Surplus=Surplus_member)
                
            self.mod.P_exchange.set_values(x_k)
            self.mod.Surplus_repr.set_values(Surplus)
            
        return x_k, Surplus, z_k, z2_k
    
    
    def optimize_admm(self, solver, **kwargs) :
        
        # power_max_random = kwargs.get("power_max_random", 1000)
        rho = kwargs.get("rho", 1)
        mu = kwargs.get("mu", 100)
        tau_incr = kwargs.get("tau_incr", 1)
        tau_decr = kwargs.get("tau_decr", 1)
        
        init_function = kwargs.get("init_function", "random")
        x_k, Surplus, z_k, z2_k = self.init_admm(init_function, self.time_set, self.current_members_id, solver=solver, **kwargs)
        
        r_k = 1000000000000
        s_k = 1000000000000
        eps_r = kwargs.get("eps_r", 1e-2)
        eps_s = kwargs.get("eps_s", 1e-2)
        max_iter = kwargs.get("max_iter", 10)
        iter = 0
        
        # High resolution to try to get the best value (otherwise, does not always converge to the best value)
        solver_options = kwargs.get("solver_options", {"MIPGap" : 1e-6, 
                                                       "FeasibilityTol" : 1e-6,
                                                       "OptimalityTol" : 1e-6, 
                                                    #    "Threads": 1
                                                       })
        
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
        list_objs = []
        list_penas = []
        wait = 0
        print("eps_r, eps_s : ", eps_r, eps_s)
        plot_flag = kwargs.get("plot_convergence", False)
        if plot_flag : 
            import matplotlib.pyplot as plt
            plt.ion()
            fig1, ax1 = plt.subplots()
            ax1.set_title("ADMM convergence")
            ax1.set_xlabel("Iteration")
            ax1.set_ylabel("Residuals")
            ax1.set_yscale("log")
            ax1.grid()

            if kwargs.get("centralized_optimal") :
                opti_res = kwargs.get("centralized_optimal")
                centralized_obj = opti_res["aggregated_objs"]['Objective']
                fig2, ax2 = plt.subplots()
                ax2.set_title("ADMM objective vs centralized objective")
                ax2.set_xlabel("Iteration")
                ax2.set_ylabel("Distance to centralized objective")
                ax2.set_yscale("symlog")
                ax2.grid()
            
        while (r_k > eps_r or s_k > eps_s) and iter < max_iter :
            
            # Save argmin local 
            
            args = {"rho" : rho, "z_k" : z_k, "z2_k" : z2_k, "u_k" : self.U_exchange, "u2_k" : self.U_surplus}
            member_args.update(args)
            
            # if iter == 0 : 

            # Members part
            if parallel: # Problem with this on python is that all the objects needs to be built again, and this is taking a lot of time
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
                penas = 0
                objs = 0
                for i in self.current_members_id :
                    member = self.members[i]
                    member.update_params_admm(**member_args)
                    # member.build_model(**member_args)
                    
                    t_opti_start = time.time()
                    member.self_optimize(solver, options=solver_options)
                    t_optimizer1 += time.time() - t_opti_start
                    
                    # print("Power exchange for member ", i, " : ", [pyo.value(member.P_exchange[k]) for k in range(24)])
                    # print("Active members : ", member.mod_member.active_members.extract_values())
                    
                    objs += pyo.value(member.mod_member.obj_expr)
                    penas += pyo.value(member.mod_member.rho/2*(member.mod_member.sqr_pena_expr))
                    
                    for_x_k_1 = member.P_exchange_repr.extract_values()
                    for_surplus = member.P_surplus.extract_values()
                    # print(f"member {i}, surplus: {for_surplus}, exchange: {for_x_k_1}")
                    for t in self.time_set :
                        for j in self.current_members_id : 
                            self.mod.x_k_1[j, i, t].set_value(for_x_k_1[(j, t)])
                        self.mod.Surplus_k_1[i, t].set_value(for_surplus[t])
            
            self.mod.rho.set_value(rho)
            list_objs.append(objs)
            list_penas.append(penas)
            # self.mod.pprint()
            
            t_opti_start = time.time()
            self.optimize(solver, options=solver_options)
            t_optimizer2 += time.time() - t_opti_start

            
            Surplus_repr_values = self.Surplus_repr.extract_values()
            # print("Surplus_repr_values : ", Surplus_repr_values)
            Surplus_k_1_values = self.mod.Surplus_k_1.extract_values()
            P_exchange_values = self.P_exchange.extract_values()
            x_k_1_values = self.mod.x_k_1.extract_values()
            
            
            z_k.update(z2_k)
            dico_to_numpy(z_k, z_k_numpy)
            x_k_1_values.update(Surplus_k_1_values)
            dico_to_numpy(x_k_1_values, x_k_1_numpy)
            z_k_1_values = {**P_exchange_values, **Surplus_repr_values}
            dico_to_numpy(z_k_1_values, z_k_1_numpy)
            
            # print("z_k", z_k)
            # print("z_k_1", z_k_1_values)
            
            r_k = np.linalg.norm(x_k_1_numpy - z_k_1_numpy)
            s_k = np.linalg.norm(z_k_numpy - z_k_1_numpy)
            
            if len(z_k_1_numpy[abs(z_k_1_numpy) >= 1]) >0 : 
                max_val_sup_0 = (abs(x_k_1_numpy - z_k_1_numpy)[abs(z_k_1_numpy) >= 1]/z_k_1_numpy[abs(z_k_1_numpy) >= 1]).max()
                max_ecart = (abs(x_k_1_numpy - z_k_1_numpy)).max()
                print("ecart max grandes valeures", max_val_sup_0, "ecart max petite valeures",max_ecart, "average z_k_1_numpy", z_k_1_numpy.mean())
                print("z_k_numpy - z_k_1_numpy", (z_k_numpy - z_k_1_numpy).max())

            U_numpy = U_numpy + x_k_1_numpy - z_k_1_numpy

            z_k = P_exchange_values
            z2_k = Surplus_repr_values
            
            # Method to update rho for better convergence
            old_rho = rho
            if wait > kwargs.get("wait_iter", 20) and wait < 100 : 
                # if wait > 
                rho*= 1.2
                
                # if r_k > mu*s_k :
                #     rho *= tau_incr
                # elif s_k > mu*r_k :
                #     rho /= tau_decr
            wait += 1
            
            if rho != old_rho :
                U_numpy = U_numpy * old_rho/rho
                
            self.U_exchange.store_values({(i, j, t) : U_numpy[i*len1 + j*len2 + t] for i in self.current_members_id for j in self.current_members_id for t in self.time_set})
            self.U_surplus.store_values({(i, t) : U_numpy[len3 + i*len2 + t] for i in self.current_members_id for t in self.time_set})

            if kwargs.get("debug_admm", False) : 
                self.debug_model()
            iter += 1
            # print("Surplus : ", Surplus)
            print("\niter, r_k, s_k : ", iter, r_k, s_k)
            print("rho : ", rho)
            self.aggregate_distributed_information()
            objs_admm_false = self.results['aggregated_objs'].copy()
            print(f"{objs_admm_false=}")
            if plot_flag :
                ax1.scatter(iter, r_k, color='blue', label='r_k' if iter == 1 else "")
                ax1.scatter(iter, s_k, color='orange', label='s_k' if iter == 1 else "")
                ax1.legend()
                
                if kwargs.get("centralized_optimal") :
                    centralized_objs = kwargs.get("centralized_optimal")["aggregated_objs"]
                    self.aggregate_distributed_information()
                    objs_admm_false = self.results['aggregated_objs'].copy()
                    # print(f"{objs_admm_false=}")
                    self.repair_admm_solution(solver, **kwargs.get("solver_options", {}))
                    objs_admm = self.results['aggregated_objs']
                    for objective, centralized_obj in centralized_objs.items():
                        if objective not in objs_admm or objective not in objs_admm_false:
                            continue
                        obj_admm = objs_admm[objective]
                        obj_admm_false = objs_admm_false[objective]
                        if centralized_obj == 0:
                            distance_to_centralized = float('inf')  # Avoid division by zero
                            distance_to_centralized_false = float('inf')
                        else:
                            distance_to_centralized = (obj_admm - centralized_obj)/centralized_obj
                            distance_to_centralized_false = (obj_admm_false - centralized_obj)/centralized_obj
                        ax2.scatter(iter, distance_to_centralized,
                                    label=f'{objective} (repaired)' if iter == 1 else "", marker='+')
                        ax2.scatter(iter, distance_to_centralized_false,
                                    label=f'{objective} (false)' if iter == 1 else "", marker='x')
                    ax2.legend()
                    # print("Distance to centralized objectives: ", {
                    #     objective: (objs_admm[objective] - centralized_obj) / centralized_obj
                    #     for objective, centralized_obj in centralized_objs.items()
                    #     if objective in objs_admm
                    # })
                plt.pause(1)
            
            # print("Z_k : ", z_k)
            # print("penas : ", penas, "objs : ", objs, "var : ", np.var(list_objs[-10:]))
            # print("pena_commu : ", pyo.value(self.mod.obj))
            
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
    
    def calc_gains(self, solver, **options) :
        self.current_members_id = self.members_id[:]
        
        self.kwargs["solver_options"] = self.kwargs.get("solver_options", {})
        self.kwargs["solver_options"].update(options)
        solver_method = self.kwargs.get("solver_method", "centralized")
        results = self.full_optimization(solver, solver_method, **self.kwargs)
        objs = results["aggregated_objs"]
        community_obj = objs['Objective']
        community_price = objs['price']
        # print(f"Community objective value: {community_obj}")
        if solver_method.startswith("rolling") : 
            method = "rolling_selves"
        else : 
            method = "selves"
        if solver_method.endswith("admm") : 
            method += "_admm"
        # print("current_members_id", self.current_members_id)
        print(method)
        results = self.full_optimization(solver, method, **self.kwargs)
        # print("after self optimize, current_members_id", self.current_members_id)
        objs = results["aggregated_objs"]
        members_obj = [results[f"members_{i}"]['Objective'] for i in self.current_members_id]
        members_price = objs['price']
        
        self.members_obj = members_obj
        self.members_price = members_price
        self.members_details = objs
        self.community_obj = community_obj
        self.community_price = community_price
        self.tot_members_obj = sum(members_obj)
        self.tot_obj_gains = self.tot_members_obj - community_obj
        self.price_gains = members_price - community_price
        
        print(f"Community objective gain: {self.tot_obj_gains}")                    
        return
        
    def distribute_gains(self, method="proportional", compute_again_coalitions=False, combination_args={}) : 
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
                print(f"Member {i} gain prop: {gain}, cost : {cost}, prop : {prop}")
                
        elif method == "equal" :
            gain = total_gains/len(self.members_id)
            self.members_gains["equal"] = {}
            for i in self.members_id : 
                self.members_gains["equal"][i] = (gain, gain/total_gains if total_gains != 0 else 0)
                print(f"Member {i} gain equal : {gain}")
                
        elif method == "shapley" or method == "nucleolus": 
            n = len(self.members_id)
            if not self.combinations or compute_again_coalitions :
                combinations = choose_combination(n, self.members_id, **combination_args)
                combinations = self.compute_combinations(combinations)
                self.combinations = combinations
            if method == "shapley" :
                self.members_gains["shapley"] = {}
                for m in self.members_id : 
                    gain = self.marginal_contribution_sum(m, self.combinations)
                    self.members_gains["shapley"][m] = (gain, gain/total_gains if total_gains != 0 else 0)
            elif method == "nucleolus" :
                self.members_gains["nucleolus"] = {}
                vs = [[comb, self.combinations[comb]] for comb in self.combinations]
                nucleolus_values = nucleolus(vs,  n)
                for m in self.members_id :
                    gain = nucleolus_values[m]
                    self.members_gains["nucleolus"][m] = (gain, gain/total_gains if total_gains != 0 else 0)
            
        return
    
    def compute_combinations(self, combinations) :
        # Si vraiment trop long, faudra réécrire en faisant les choses dans le bon ordre 
        # pour ne pas faire 25 boucles différentes.
        
        method_commu = self.kwargs.get("solver_method", "centralized")
        method_selves = "rolling_selves" if method_commu.startswith("rolling") else "selves"
        if method_commu.endswith("admm") : 
            method_selves += "_admm"
        for comb in combinations :
            # print("combinaison", comb)
            self.current_members_id = list(comb)
            kwargs = self.kwargs 
            # self.build_model(**kwargs)
            solver = kwargs.get("solver", "gurobi")
            options = kwargs.get("solver_options", {})
            results = self.full_optimization(solver, method_commu, **self.kwargs, custom_active_id=comb)
            
            community_obj = results["aggregated_objs"]['Objective']
            
            members_details = self.full_optimization(solver, method_selves, **self.kwargs, custom_active_id=comb)
            tot_members_obj = members_details["aggregated_objs"]['Objective']
            
            # print("methods : ", method_commu, method_selves)
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
                
    def aggregate_distributed_information(self, privacy=0, from_memory=False) : 
        powers = {"devices" : {}}
        for i in self.current_members_id :
            member_power = self.members[i].send_power_information(privacy=privacy, from_memory=from_memory)
            self.results[f'members_{i}'] = {}
            for key, value in member_power.items() :
                if key != "devices" :             
                    self.results[f'members_{i}'][key] = value
                    if key not in powers :
                        powers[key] = value[:]
                    else :
                        for k in range(len(value)) : 
                            powers[key][k] += value[k]
                            
                else : 
                    for dev in value : 
                        self.results[f'members_{i}'][dev] = value[dev][:]
                        if dev not in powers["devices"] :
                            powers["devices"][dev] = value[dev][:]
                        else : 
                            for k in range(len(value[dev])) : 
                                powers["devices"][dev][k] += value[dev][k]
                        
                        
        objs = {}
        for i in self.current_members_id :
            member_obj = self.members[i].send_obj_information(from_memory=from_memory)
            for key, value in member_obj.items() :
                self.results[f'members_{i}'][key] = value
                if key not in objs :
                    objs[key] = value
                else :
                    objs[key] += value

        self.results['aggregated_powers'] = powers
        self.results['aggregated_objs'] = objs
        
        self.results['power_exchange_commu'] = [[[pyo.value(self.P_exchange[i, j, t]) for t in self.time_set] for j in self.current_members_id] for i in self.current_members_id]
    
    def repair_admm_solution(self, solver, **solver_options) : 
        """
        Repair the solution obtained by ADMM to make it feasible for the original problem. 
        This is done by fixing sent power proportionnally to what the community thought the members would send.
        The correction is supposed to be vert small, some percent at most.
        """
        
        # Searching for the real values
        self.aggregate_distributed_information()
            
        ids = set()
        true_surplus = {}
        for key in self.results : 
            if key.startswith("members_") : 
                member_id = int(key.split("_")[1])
                ids.add(member_id)
                true_surplus[member_id] = []
                for t in self.time_set : 
                    true_value = self.results[key]['P_exchange'][t] - self.results[key]['P_surplus'][t]
                    if true_value < 0 :
                        true_surplus[member_id].append(-true_value)
                    else :
                        true_surplus[member_id].append(0)
                        
        numpy_exchange = np.array(self.results['power_exchange_commu'])
        new_exchange = {}
        for i in ids : 
            sent_t = numpy_exchange[i, :, :].sum(axis=0)
            rec_t = numpy_exchange[:, i, :].sum(axis=0)
            ex_t = sent_t - rec_t
            for t in self.time_set :
                for j in self.current_members_id :
                    if ex_t[t] <= 1e-3 : 
                        new_exchange[i, j, t] = true_surplus[i][t]/len(ids)
                    new_exchange[i, j, t] = true_surplus[i][t]/ex_t[t]*numpy_exchange[i, j, t]
        
        # Update the model with the new values, fixing the values and optimize again to get the final solution.
        for i in ids : 
            member = self.members[i]
            P_exchange = {(j, t) : new_exchange[j, i, t] for j in self.current_members_id for t in self.time_set}
            P_surplus = {t : true_surplus[i][t] for t in self.time_set}
            member.admm_repair(P_exchange, P_surplus, solver, **solver_options)
            
        self.aggregate_distributed_information()
        return
            
                
    def heuristic_optimization(self, solver, **kwargs) :
        # Step 1 : optimize with exchanges fixed at 0
        self.P_exchange.fix(0)
        
        method = kwargs.get("method", "centralized")
        if method == "centralized" :
            method_selves = "selves"
            global_method = "centralized"
        if method == "admm" :
            method_selves = "selves_admm"
            init_function = "random"
            new_rho = 0.1
        new_kwargs = kwargs.copy()
        new_kwargs["init_function"] = init_function
        new_kwargs["rho"] = new_rho
        new_kwargs['eps_r'] = 1e-2
        new_kwargs['eps_s'] = 1e-2
        del new_kwargs["plot_convergence"]
        self.full_optimization(solver, method_selves, **new_kwargs)
        # self.optimize(solver, **kwargs.get("solver_options", {}))
        P_surplus = {}
        P_need = {}
        needers = [set() for t in self.time_set]
        givers = [set() for t in self.time_set]
        for i in self.current_members_id :
            member = self.members[i]
            P_m = member.send_heuristic_values()
            # print(i, "P_m", P_m)
            P_surplus[i] = P_m["P_surplus"]
            P_need[i] = P_m["P_need"]
        
        for t in self.time_set :
            for i in self.current_members_id :
                if P_need[i][t] > kwargs.get("heuristic_tol", 1e-3) : 
                    needers[t].add(i)
                if P_surplus[i][t] > kwargs.get("heuristic_tol", 1e-3) : 
                    givers[t].add(i)
        # print("Needers : ", needers, "Givers : ", givers)
        # Step 2 : provide the exchange energy needed.
        new_P_exchange = {(i, j, t) : 0 for i in self.current_members_id for j in self.current_members_id for t in self.time_set}
        
        full_surplus = [sum(P_surplus[i][t] for i in self.current_members_id) for t in self.time_set]
        full_need = [sum(P_need[i][t] for i in self.current_members_id) for t in self.time_set]
        for t in self.time_set :
            to_give = full_surplus[t]/full_need[t] if full_need[t] > 0 else 0
            # print("to_give t", to_give, t)
            if to_give < 1 : 
                # Provide the necessary exchange energy, same value for each member, proportional to their need.
                for i in needers[t] : 
                    p_need = P_need[i][t]*to_give
                    # print(i, "p_need", p_need)
                    while p_need > 0 and givers[t] :
                        j = givers[t].pop()
                        # print(j, "p_need", p_need)
                        p_give = P_surplus[j][t]
                        if p_give >= p_need : 
                            new_P_exchange[j, i, t] = p_need
                            P_surplus[j][t] -= p_need
                            p_need = 0
                        else : 
                            new_P_exchange[j, i, t] = p_give
                            P_surplus[j][t] = 0
                            p_need -= p_give
                            
            else : 
                # Provide the necessary exchange energy, same value for each member, proportional to their surplus.
                for j in givers[t] :   
                    p_give = P_surplus[j][t]/to_give
                    # print(j, "p_give", p_give)
                    while p_give > 0 and needers[t] :
                        i = needers[t].pop()
                        p_need = P_need[i][t]
                        if p_need >= p_give : 
                            new_P_exchange[j, i, t] = p_give
                            P_need[i][t] -= p_give
                            p_give = 0
                        else : 
                            new_P_exchange[j, i, t] = p_need
                            P_need[i][t] = 0
                            p_give -= p_need
        # print("new_P_exchange : ", new_P_exchange)
        # self.P_exchange.unfix()
        self.P_exchange.set_values(new_P_exchange)
        
        self.P_exchange.unfix()
        for i in self.current_members_id :
            member = self.members[i]
            member.P_surplus.unfix()
        if kwargs.get("for_initialization", False) : 
            return new_P_exchange
        
        return self.optimize(solver, **kwargs.get("solver_options", {}))
                        
    
    def full_optimization(self, solver, solving_method_, **kwargs) : 
        if kwargs.get("current_members_id") is not None:
            self.current_members_id = kwargs.get("current_members_id")
        # print("Current members id : ", kwargs.get('custom_active_id'), self.current_members_id)
        self.update_model(custom_active_id=kwargs.get('custom_active_id'), custom_independant_id=kwargs.get('custom_active_id')) 
        if "admm" in solving_method_ : 
            for m in self.members : 
                m.update_model_admm(custom_active_id=kwargs.get('custom_active_id'))
        if solving_method_ == "rolling_centralized" : 
            res = minimal_rolling_opti(self, "centralized", solver, **kwargs)
        if solving_method_ == "rolling_admm" :
            res = minimal_rolling_opti(self, "admm", solver, **kwargs)
        if solving_method_ == "rolling_selves" : 
            res = minimal_rolling_opti(self, "selves", solver, **kwargs)
        if solving_method_ == "rolling_selves_admm" : 
            res = minimal_rolling_opti(self, "admm_selves", solver, **kwargs)
        if solving_method_ == "rolling_heuristic" : 
            res = minimal_rolling_opti(self, "heuristic", solver, **kwargs)
        if solving_method_ == "centralized" : 
            self.optimize(solver, **kwargs.get("solver_options", {}))
            self.aggregate_distributed_information()
            res = self.results.copy()
        if solving_method_ == "admm" :
            self.optimize_admm(solver, **kwargs)
            # self.aggregate_distributed_information()
            self.repair_admm_solution(solver, **kwargs.get("solver_options", {}))
            res = self.results.copy()
        if solving_method_ == "selves" : 
            self.update_model(custom_active_id=[], custom_independant_id=kwargs.get('custom_active_id'))
            self.optimize(solver, **kwargs.get("solver_options", {}))
            self.aggregate_distributed_information()
            res = self.results.copy()
        if solving_method_ == "selves_admm" : 
            self.update_model(custom_active_id=[], custom_independant_id=kwargs.get('custom_active_id'))
            for m in self.members : 
                m.update_model_admm(custom_active_id=[])
            self.optimize_admm(solver, **kwargs)
            self.aggregate_distributed_information()
            res = self.results.copy()
        if solving_method_ == "heuristic" :
            self.heuristic_optimization(solver, **kwargs)
            self.aggregate_distributed_information()
            res = self.results.copy()
        return res
    
    def debug_model(self, folder_path=os.path.join(results_path, "debug")) : 
        debug_community(self, folder_path=folder_path)
    
    def plot_power_curves(self, **kwargs) :
        plot_power_curves(**kwargs)
        
    def plot_hexagon(self, **kwargs) :
        plot_hexagon_objective(**kwargs)
        