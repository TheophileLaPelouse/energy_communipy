from . import pyo
from .utils import calc_auto, calc_eco, calc_enviro, calc_pena_pow, calc_confort, calc_eco_total, calc_invest_cost
from ..opti.solving import solve_model
from ..plotting.plot_functions import plot_power_curves
from .constraint_functions_members import *
import time

class member : 
    def __init__(self, devices, socio, id_, **kwargs) :
        method = kwargs.get("method", "centralized")   
        self.name = kwargs.get("name", f"member_{id_}")      
        self.socio = socio 
        self.socio_commu = self.socio 
        self.ref_values = kwargs.get("ref_values", [1 for k in range(len(socio)+1)])
        self.id = id_
        self.commu = None
        self.full_commu = None
        self.agent = None
        self.kwargs = kwargs
        self.deltat = kwargs.get("deltat", 1)
        self.total_time = kwargs.get("total_time", 24)
        
        self.scale = kwargs.get("scale", 1)
        
        self.mod_member = pyo.ConcreteModel()
        self.time_index = pyo.RangeSet(0, self.total_time - 1)
        
        self.P_disponible = kwargs.get("irradiance_profile", [0 for t in range(self.total_time)])
        self.P_prod = None
        self.P_cons = None 
        self.P_bat = None
        self.P_exchange = None
        self.PV_surface = None
        self.PV_present = False
        self.bat_present = False
        self.bat_cap = None        
        self.devices = devices 
        self.devices_name = [device.name for device in devices]
        
        self.P_exchange_repr = None # Only used for admm
        # print("START BUILDING")
        
        self.def_irradiance = kwargs.get("def_irradiance", False)
        
        if not method == "centralized" : 
            self.build_model(**kwargs)
            
        calc_ref = kwargs.get("calc_ref", True)
        if calc_ref :
            # print("C'est ICI")
            self.calc_ref_values(**kwargs)
            # print("Ou c'est après")
            self.build_model(**kwargs)
        # print("BUILDING MEMBER DONE")
    
    def add_to_community(self, commu, id_, method=None) :
        if hasattr(self.mod_member, 'commu'):
            self.mod_member.commu.set_value(1)
        if method == "admm" : 
            self.commu = {
                "members_id" : commu.members_id[:],
                "member_set" : set(commu.member_set),
                "current_members_id" : commu.current_members_id[:],
            }
            self.full_commu = self.commu.copy()
        
        else : 
            self.commu = commu  
            self.full_commu = commu
        self.socio_commu = commu.socio  
        self.id=id_
    
    def calc_profile(self, deltat=1) : 
        """
        Take all the devices and compute the consumed power, the produced power, the power exchange to batteries.
        """
       
        self.P_cons = pyo.Expression(self.time_index, rule=rule_pcons)
        self.P_bat = pyo.Expression(self.time_index, rule=rule_pbat)
        self.PV_surface = pyo.Expression(rule=rule_PV_surface)
        self.bat_cap = pyo.Expression(rule=bat_cap_rule)
        self.P_prod = pyo.Expression(self.time_index, rule=rule_p_prod)
        self.mod_member.P_cons = self.P_cons 
        self.mod_member.P_bat = self.P_bat
        self.mod_member.PV_surface = self.PV_surface
        self.mod_member.bat_cap = self.bat_cap
        self.mod_member.P_prod = self.P_prod
        
        self.mod_member.p_confort = pyo.Expression(self.time_index, rule=rule_p_confort)
        self.mod_member.t_confort = pyo.Expression(rule=rule_t_confort)
        
        
    def fetch_P_exchange(self, **kwargs) :
        """
        Fetch the power coming from the grid   
        """
        method = kwargs.get("method", "centralized")
        if method == "centralized" : 
            
            self.P_exchange = pyo.Expression(self.time_index, rule=simple_power_exchange_sum_centralized)
            self.mod_member.P_exchange = self.P_exchange
            
        elif method=="admm" : 
            if self.commu is None : 
                members_id = [self.id]
                current_members_id = [self.id]
            else : 
                members_id = self.commu["members_id"]
                current_members_id = self.commu["current_members_id"]
                
            self.mod_member.member_set = pyo.Set(initialize=members_id)
            self.mod_member.active_members = pyo.Param(members_id, initialize={i : 1 if i in current_members_id else 0 for i in members_id}, mutable=True)
            self.P_exchange_repr = pyo.Var(self.mod_member.member_set, self.time_index, within=pyo.NonNegativeReals, initialize=0)
            self.mod_member.P_exchange_repr = self.P_exchange_repr

            self.P_exchange = pyo.Expression(self.time_index, rule=simple_power_exchange_sum_admm)
            self.mod_member.P_exchange = self.P_exchange
            
    def build_objective(self, **kwargs) :
        method = kwargs.get("method", "centralized")
        if method == "centralized" :
            self.mod_member.obj = pyo.Objective(expr=self.mod_member.obj_expr, sense=pyo.minimize)
            
        elif method == "admm" :
            id_ = self.id
            m = self.mod_member
            
            if not hasattr(m, "rho") : 
                rho = pyo.Param(initialize=1, mutable=True)
                z_k = pyo.Param(m.member_set, m.member_set, self.time_index, initialize=0, mutable=True)
                u_k = pyo.Param(m.member_set, m.member_set, self.time_index, initialize=0, mutable=True)
                z2_k = pyo.Param(m.member_set, self.time_index, initialize=0, mutable=True)
                u2_k = pyo.Param(m.member_set, self.time_index, initialize=0, mutable=True)
            
                m.rho = rho
                m.z_k = z_k
                m.u_k = u_k
                m.z2_k = z2_k
                m.u2_k = u2_k
            
            m.sqr_pena_expr = pyo.Expression(expr=sum((m.P_exchange_repr[i, t] - m.z_k[i, id_, t] + m.u_k[i, id_, t])**2*m.active_members[i] 
                                                    for t in self.time_index 
                                                    for i in m.member_set)
                                                    + sum((self.P_surplus[t] - m.z2_k[id_, t] + m.u2_k[id_, t])**2 
                                                          for t in self.time_index)
                                                    )
            m.obj = pyo.Objective(expr=m.obj_expr + m.rho/2*m.sqr_pena_expr, sense=pyo.minimize)

    def update_params_admm(self, **kwargs) :
        self.mod_member.rho.set_value(kwargs.get("rho", 1))
        self.mod_member.z_k.store_values(kwargs.get("z_k"))
        self.mod_member.u_k.store_values(kwargs.get("u_k"))
        self.mod_member.z2_k.store_values(kwargs.get("z2_k"))
        self.mod_member.u2_k.store_values(kwargs.get("u2_k"))
        

    def build_model(self, **kwargs) :
        """
        Aggregate the devices model. And define the power balance contraints. 
        P_surplus is the power going to the grid, 
        P_self is the power used for self consumption that is not coming from or to the grid.
        """ 
        
        self.clear_model()
        
        self.mod_member.time_index = self.time_index
        self.mod_member.commu = pyo.Param(initialize=(int(self.commu is None) + 1)%2, within=pyo.Binary, mutable=True)
        self.mod_member.id = pyo.Param(initialize=self.id, mutable=True)
        
        for k in range(len(self.devices)) : 
            if self.devices[k].__class__.__name__ == "PV" and self.def_irradiance : 
                self.devices[k].update_irradiance(self.P_disponible)
                self.PV_present = True
            if self.devices[k].__class__.__name__ == "battery" :
                self.bat_present = True
            
            setattr(self.mod_member, f"device{k}", self.devices[k].mod)
            
        self.mod_member.device_set = pyo.RangeSet(0, len(self.devices)-1)
            
        
        # print("ADDING DEVICES DONE")
        
        self.fetch_P_exchange(**kwargs)
                
        # print("FETCH EXCHANGES DONE")
        
        self.calc_profile()
        
        # print("CALC PROFILE")
        
        self.P_surplus = pyo.Var(self.time_index, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_index])
        self.P_self = pyo.Var(self.time_index, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_index])
        self.mod_member.P_surplus = self.P_surplus
        self.mod_member.P_self = self.P_self
        
        if self.commu is None : 
            for t in self.time_index :
                self.P_surplus[t].fix(0)
                
        self.P_grid_plus = pyo.Var(self.time_index, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_index])
        self.P_grid_minus = pyo.Var(self.time_index, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_index])
        self.mod_member.P_grid_plus = self.P_grid_plus
        self.mod_member.P_grid_minus = self.P_grid_minus
        
        # print("bat_exchange", kwargs.get("bat_exchange", False))
        if kwargs.get("bat_exchange", False) : 
            self.charging = pyo.Var(self.time_index, within=pyo.Boolean, initialize=[0 for t in self.time_index])
            self.P_bat_plus = pyo.Var(self.time_index, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_index])
            self.P_bat_minus = pyo.Var(self.time_index, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_index])
            self.mod_member.charging = self.charging
            self.mod_member.P_bat_plus = self.P_bat_plus
            self.mod_member.P_bat_minus = self.P_bat_minus
            
            self.P_bat_p = pyo.Expression(self.time_index, rule=lambda m, t : self.P_bat_plus[t]*self.charging[t])
            self.P_bat_m = pyo.Expression(self.time_index, rule=lambda m, t : self.P_bat_minus[t]*(1 - self.charging[t]))
            self.mod_member.P_bat_p = self.P_bat_p
            self.mod_member.P_bat_m = self.P_bat_m
            
            self.mod_member.P_bat_con = pyo.Constraint(self.time_index, rule=P_bat_con_false)
            self.mod_member.P_prod_con = pyo.Constraint(self.time_index, rule=P_prod_constraint_false)
            self.mod_member.P_grid_con = pyo.Constraint(self.time_index, rule=P_grid_constraint_false)

            self.P_self_prod = pyo.Expression(self.time_index, rule=P_self_prod_con_false)
            self.mod_member.P_self_prod = self.P_self_prod
            
        else : 

            self.P_self_prod = pyo.Expression(self.time_index, rule=P_self_prod_con_true)  
            self.mod_member.P_self_prod = self.P_self_prod
            
            self.mod_member.P_prod_con = pyo.Constraint(self.time_index, rule=P_prod_constraint_true)
            self.mod_member.P_grid_con = pyo.Constraint(self.time_index, rule=P_grid_constraint_true)
        # Warning : works onlly if selling price lower than buying price
        
        # print("PGRID + and - DEFINED")
        
        functions = kwargs.get("functions", []) # format = [f(pcons, pbat, pexchange pgrid), ...]
        eco_args = kwargs.get("eco", {})
        eco_args["deltat"] = self.deltat
        eco_args["total_time"] = self.total_time
        eco_args["ref"] = self.ref_values[0]
        
        enviro_args = kwargs.get("enviro", {})
        enviro_args["ref"] = self.ref_values[1]
        
        auto_args = kwargs.get("auto", {})
        auto_args["ref"] = self.ref_values[2]
        
        confort_args = kwargs.get("confort", {})
        confort_args["ref"] = self.ref_values[3]
        
        self.mod_member.obj_expr = pyo.Expression(expr=calc_eco_total(self.P_grid_plus, self.P_grid_minus, self.P_exchange, self.PV_surface, self.PV_present, self.bat_cap, self.bat_present, **eco_args)*self.socio_commu[0]
                                     + calc_enviro(self.P_grid_plus, self.P_exchange,self.P_self, **enviro_args)*self.socio_commu[1]
                                     + calc_auto(self.P_grid_plus, **auto_args)*self.socio_commu[2]
                                     + calc_confort(self.mod_member.p_confort, self.mod_member.t_confort, **confort_args)*self.socio_commu[3]
                                     + sum(f(self.P_cons, self.P_bat, self.P_exchange, self.P_grid_plus, self.P_grid_minus) for f in functions)/self.ref_values[-1]
                                    #  + calc_pena_pow(self.mod_member.p_excess_l, self.mod_member.p_excess_u, **pena_args)
                                     )
        
        self.build_objective(**kwargs)
        
        # self.mod_member.obj = pyo.Objective(expr=self.mod_member.obj_expr, sense=pyo.minimize)
        
        self.price = pyo.Expression(expr=calc_eco_total(self.P_grid_plus, self.P_grid_minus, self.P_exchange, self.PV_surface, self.PV_present, self.bat_cap, self.bat_present, **eco_args))
        self.price_operation = pyo.Expression(expr=calc_eco(self.P_grid_plus, self.P_grid_minus, self.P_exchange, **eco_args))
        self.price_invest = pyo.Expression(expr=calc_invest_cost(self.PV_surface, self.PV_present, self.bat_cap, self.bat_present, **eco_args))
        self.enviro = pyo.Expression(expr=calc_enviro(self.P_grid_plus, self.P_exchange,self.P_self, **enviro_args))
        self.auto = pyo.Expression(expr=calc_auto(self.P_grid_plus, **auto_args))
        self.confort = pyo.Expression(expr=calc_confort(self.mod_member.p_confort, self.mod_member.t_confort, **confort_args))
        
        self.mod_member.price = self.price
        self.mod_member.price_operation = self.price_operation
        self.mod_member.price_invest = self.price_invest
        self.mod_member.enviro = self.enviro
        self.mod_member.auto = self.auto
        self.mod_member.confort = self.confort
        
        
        return
    
    def clear_model(self):
        # Remove all variables from the model while keeping other components like devices
        vars_to_remove = [attr for attr in dir(self.mod_member) if isinstance(getattr(self.mod_member, attr), (pyo.Var, pyo.Expression, pyo.Constraint, pyo.Objective, pyo.Set, pyo.RangeSet, pyo.Param))]
        for var in vars_to_remove:
            delattr(self.mod_member, var)
        
        
    def calc_ref_values(self, **kwargs) : 
        """
        Run the optimization with some default values to get reference values for normalization of the different criteria
        """
        self.commu = None
        self.ref_values = [1 for k in range(4)]
        
        self.build_model(**kwargs)
        self.fix_device_values()
        
        solver = kwargs.get("ref_solver", "gurobi")
        lp_ref = kwargs.get("ref_lp", False)
        if lp_ref :
            self.mod_member.write('member.lp', io_options={'symbolic_solver_labels': True})
        results = solve_model(self.mod_member, solver, **kwargs.get("ref_options", {}))
        
        self.ref_values = [pyo.value(self.price), pyo.value(self.enviro), pyo.value(self.auto), pyo.value(self.confort)]
        
        flag = str(results['Solver'][0]['Status']) == 'ok'
        from_community = kwargs.get("from_community", False)
        if not from_community :
            for k in range(len(self.ref_values)) :
                if self.ref_values[k] == 0 and k != 3 : 
                    print("WARNING : REF VALUE IS 0, PROBLEM IN NORMALIZATION, REF VALUES : ", self.ref_values)
                    self.ref_values = [1 for val in self.ref_values]
                    print("REF VALUES SET TO 1")
                    break
                if self.ref_values[k] == 0 and k == 3 : 
                    self.ref_values[k] = 1 # Confort is not studied in this case 
        
        if not kwargs.get("no_clear_ref", False) :
            self.unfix_device_values()
            self.clear_model()
            self.commu = self.full_commu
            if self.commu is not None : 
                self.mod_member.commu.set_value(1)
        return flag
                    
    def fix_device_values(self) : 
        # Fix the variables 
        t0=time.time()
        for d in self.devices : 
            # if white goods
            if hasattr(d.mod, "t_confort_lvl") : 
                k = 0
                while k < self.total_time and d.mod.used_time[k].value == 1 : 
                    u = 0
                    while u < self.total_time and d.mod.available_time_set[k, u].value == 0 : 
                        u+=1
                    div = (d.mod.t_wanted[k].value + u)/2
                    starting_time = int(div)
                    if starting_time != div and div!=0 : 
                        starting_time += 1 
                    diff = starting_time - d.mod.t_wanted[k].value
                    if diff == 0 : 
                        while u < self.total_time and d.mod.available_time_set[k, u].value == 1 : 
                            u+=1
                        u -= 1
                        div = (d.mod.t_wanted[k].value + u)/2
                        starting_time = int(div)
                        if starting_time != div and div!=0 : 
                            starting_time += 1
                        diff = starting_time - d.mod.t_wanted[k].value
                    if diff >= 0 :
                        d.mod.starting_time_plus[k].fix(diff)
                        d.mod.starting_time_minus[k].fix(0)
                    else :
                        d.mod.starting_time_plus[k].fix(0)
                        d.mod.starting_time_minus[k].fix(-diff)
                    k += 1
                        
            elif hasattr(d.mod, "E") : 
                # A lot of constraint particularly for EV, so fix Pcons to 0 and then deactivate constraints
                for t in d.mod.t_set :
                    getattr(d.mod, "Pcons")[t].fix(0)
                for c in d.mod.component_objects(pyo.Constraint, active=True) :
                    c.deactivate()
            elif d.__class__.__name__ == "AoN" : 
                nb_activation_needed = int(d.energy_needed/d.power_needed) + int(d.energy_needed%d.power_needed != 0)
                spread_indices = set()
                for i in range(nb_activation_needed) : 
                    spread_indices.add(round(i*(self.total_time-1)/(nb_activation_needed-1)))
                for t in range(self.total_time) : 
                    if t in spread_indices : 
                        d.mod.on_off[t].fix(1)
                    else : 
                        d.mod.on_off[t].fix(0)
            else : 
                for t in d.mod.t_set : 
                    getattr(d.mod, "allocated_power")[t].fix((d.p_range[t][1] + d.p_range[t][0])/2)
        # print("How much time for fixing :", time.time() - t0)
                    
    def unfix_device_values(self) :
        # Unfix the variables
        for d in self.devices : 
            # if white goods
            if hasattr(d.mod, "t_confort_lvl") : 
                k = 0
                while k < self.total_time and d.mod.used_time[k].value == 1 :
                    if d.mod.starting_time_plus[k].fixed :
                        d.mod.starting_time_plus.unfix()
                        d.mod.starting_time_minus.unfix()
                    k+=1
                
            elif hasattr(d.mod, "E") : 
                # A lot of constraint particularly for EV, so fix Pcons to 0 and then deactivate constraints
                for t in d.mod.t_set :
                    getattr(d.mod, "Pcons")[t].unfix()
                for c in d.mod.component_objects(pyo.Constraint) :
                    c.activate()
            else : 
                for t in d.mod.t_set : 
                    getattr(d.mod, "allocated_power")[t].unfix()
                    
    # def scale_power_model(self, scale) : 
    #     """
    #     Scale the power of the model by a factor. Useful for improving the performance of the optimization.
    #     """
    #     Powers_to_scale = ['P_bat','P_cons','P_prod','bat_cap'] # Others are defined regarding these ones
    #     for power in Powers_to_scale :
    #         if hasattr(self.mod_member, power) : 
                
        
        
                    
    def send_power_information(self, privacy=0) : 
        """
        Send the power information to the community. Privacy is a parameter varying between 0 and some integers.
        The higher the number, the less information is shared. For now only 0 is implemented
        """
        powers = {
            "P_cons": [pyo.value(self.P_cons[t]) for t in self.time_index],
            "P_prod": [pyo.value(self.P_prod[t]) for t in self.time_index],
            "P_bat": [pyo.value(self.P_bat[t]) for t in self.time_index],
            "P_exchange": [pyo.value(self.P_exchange[t]) for t in self.time_index],
            "P_surplus": [pyo.value(self.P_surplus[t]) for t in self.time_index],
            "P_self": [pyo.value(self.P_self[t]) for t in self.time_index], 
            "P_grid": [pyo.value(self.P_grid_plus[t] - self.P_grid_minus[t]) for t in self.time_index],
        }
        # In the future could send a json for working as an agent.
        return powers
    
    def send_obj_information(self, keys_not_to_send=None) : 
        objs = {
            "Objective" : pyo.value(self.mod_member.obj),
            "price" : pyo.value(self.price),
            "price_operation" : pyo.value(self.price_operation),
            "price_invest" : pyo.value(self.price_invest),
            "enviro" : pyo.value(self.enviro),
            "auto" : pyo.value(self.auto),
            "confort" : pyo.value(self.confort)
        }
        if keys_not_to_send is not None :
            for key in keys_not_to_send :
                objs.pop(key, None)
        return objs
                    
    def drop_device(self, k) :
        if k < 0 : 
            k = len(self.devices) + k  
        dev = self.devices.pop(k)
        delattr(self.mod_member, f"device{k}")
        self.clear_model()
        return dev

    def create_agent(self) :
        return
    
    def self_optimize(self, solver, **options) :   
        results = solve_model(self.mod_member, solver, **options)
        return results
    
    def plot_power_curves(self, **kwargs) :
        plot_power_curves(self.total_time, self.deltat, **kwargs)