from numpy import mod
from . import pyo
from .utils import calc_auto, calc_eco, calc_enviro, calc_pena_pow, calc_confort, calc_eco_total, calc_invest_cost
from ..opti.solving import solve_model
from ..plotting.plot_functions import plot_power_curves

class member : 
    def __init__(self, devices, socio, id_, **kwargs) :
        
        method =kwargs.get("method", "centralized")   
        self.name = kwargs.get("name", f"member_{id_}")      
        self.socio = socio 
        self.socio_commu = self.socio 
        self.ref_values = kwargs.get("ref_values", [1 for k in range(len(socio)+1)])
        self.id = id_
        self.commu = None
        self.mod_member = pyo.ConcreteModel()
        self.agent = None
        self.kwargs = kwargs
        self.deltat = kwargs.get("deltat", 1)
        self.total_time = kwargs.get("total_time", 24)
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
    
    def add_to_community(self, commu, id_) :
        self.commu = commu  
        self.socio_commu = commu.socio  
        self.id=id_
    
    def calc_profile(self, deltat=1) : 
        """
        Take all the devices and compute the consumed power, the produced power, the power exchange to batteries.
        """
                
        def rule_pcons(m, t) : 
            Pcons = 0
            for d in self.devices : 
                if not (hasattr(d, "E") or d.__class__.__name__ == "PV") : 
                    Pcons += d.mod.Pcons[t]
            return Pcons
        def rule_pbat(m, t) :
            Pbat = 0
            for d in self.devices : 
                if hasattr(d, "E") : 
                    Pbat += d.mod.Pcons[t] 
            return Pbat
        
        def rule_p_prod(m, t) : 
            Pprod = 0
            for d in self.devices : 
                if d.__class__.__name__ == "PV": 
                    Pprod -= d.mod.Pcons[t]
            return Pprod
       
        def rule_p_confort(m, t) : 
            confort = 0
            for d in self.devices : 
                if hasattr(d.mod, "p_confort_lvl") : 
                    confort += d.mod.p_confort_lvl[t]
            return confort
        def rule_t_confort(m) : 
            confort = 0
            for d in self.devices : 
                if hasattr(d.mod, "t_confort_lvl") : 
                    confort += d.mod.t_confort_lvl
            return confort
        
        def rule_PV_surface(m) : 
            surface = 0
            for d in self.devices : 
                if d.__class__.__name__ == "PV" : 
                    surface += d.mod.PV_surface
            return surface
        
        def bat_cap_rule(m) : 
            cap = 0
            for d in self.devices : 
                if d.__class__.__name__ == "battery" : 
                    cap += d.capacity
            return cap
       
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
            def simple_power_exchange_sum(m, t) : 
                if self.commu is None : 
                    return 0
                else : 
                    s = sum(self.commu.P_exchange[k][self.id][t] for k in self.commu.current_members_id)
                
                if s is None : 
                    return 0
                else : 
                    return s
            self.P_exchange = pyo.Expression(self.time_index, rule=simple_power_exchange_sum)
            self.mod_member.P_exchange = self.P_exchange

    def build_model(self, **kwargs) :
        """
        Aggregate the devices model. And define the power balance contraints. 
        P_surplus is the power going to the grid, 
        P_self is the power used for self consumption that is not coming from or to the grid.
        """ 
        
        self.clear_model()
        
        self.time_index = pyo.RangeSet(0, self.total_time - 1)
        self.mod_member.time_index = self.time_index
        
        for k in range(len(self.devices)) : 
            if self.devices[k].__class__.__name__ == "PV" and self.def_irradiance : 
                self.devices[k].update_irradiance(self.P_disponible)
                self.PV_present = True
            if self.devices[k].__class__.__name__ == "battery" :
                self.bat_present = True
            
            setattr(self.mod_member, f"device{k}", self.devices[k].mod)
            
        
        # print("ADDING DEVICES DONE")
        
        self.fetch_P_exchange()
        
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
         
            def P_bat_con(mod, t) :
                return (mod.P_bat[t] == self.P_bat_p[t] - self.P_bat_m[t])
            self.mod_member.P_bat_con = pyo.Constraint(self.time_index, rule=P_bat_con)
            
            def P_prod_constraint(mod, t) : 
                return self.P_surplus[t] + self.P_self[t] == self.P_prod[t] + mod.P_bat_m[t]

            def P_grid_constraint(mod, t):
                return mod.P_grid_plus[t] - mod.P_grid_minus[t] == self.P_cons[t] + mod.P_bat_p[t] - self.P_exchange[t] - self.P_self[t]

            self.P_self_prod = pyo.Expression(self.time_index, rule=lambda m, t : m.P_self[t] - m.P_bat_m[t])
            self.mod_member.P_self_prod = self.P_self_prod
            
        else : 
            def P_prod_constraint(mod, t) : 
                return self.P_surplus[t] + self.P_self[t] == self.P_prod[t] 
            
            def P_grid_constraint(mod, t):
                return mod.P_grid_plus[t] - mod.P_grid_minus[t] == self.P_cons[t] + self.P_bat[t] - self.P_exchange[t] - self.P_self[t]

            self.P_self_prod = pyo.Expression(self.time_index, rule=lambda m, t : m.P_self[t])  
            self.mod_member.P_self_prod = self.P_self_prod
            
        self.mod_member.P_prod_con = pyo.Constraint(self.time_index, rule=P_prod_constraint)
        self.mod_member.P_grid_con = pyo.Constraint(self.time_index, rule=P_grid_constraint)
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
        self.mod_member.obj = pyo.Objective(expr=self.mod_member.obj_expr, sense=pyo.minimize)
        
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
        vars_to_remove = [attr for attr in dir(self.mod_member) if isinstance(getattr(self.mod_member, attr), (pyo.Var, pyo.Expression, pyo.Constraint, pyo.Objective, pyo.Set, pyo.RangeSet))]
        for var in vars_to_remove:
            delattr(self.mod_member, var)
        
        
    def calc_ref_values(self, **kwargs) : 
        """
        Run the optimization with some default values to get reference values for normalization of the different criteria
        """
        self.build_model(**kwargs)
        self.fix_device_values()
        
        solver = kwargs.get("ref_solver", "gurobi")
        lp_ref = kwargs.get("ref_lp", False)
        if lp_ref :
            self.mod_member.write('member.lp', io_options={'symbolic_solver_labels': True})
        results = solve_model(self.mod_member, solver, **kwargs.get("ref_options", {}))
        self.ref_values = [pyo.value(self.price), pyo.value(self.enviro), pyo.value(self.auto), pyo.value(self.confort)]
        # print("REF VALUES CALCULATED : ", self.ref_values)

        flag = str(results['Solver'][0]['Status']) == 'ok'
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
        return flag
                    
    def fix_device_values(self) : 
        # Fix the variables 
        for d in self.devices : 
            # if white goods
            if hasattr(d.mod, "t_confort_lvl") : 
                for instant in d.mod.t_set : 
                    div = (d.t_use[instant][0] + getattr(d.mod, f"set_t0_{instant}").at(1))/2
                    starting_time = int(div)
                    if starting_time != div and div!=0 : 
                        starting_time += 1 # Attention
                    diff = d.t_use[instant][0] - starting_time
                    # print("diff", diff)
                    if diff == 0 : 
                        div = (d.t_use[instant][0] + getattr(d.mod, f"set_t0_{instant}").at(-1))/2
                        starting_time = int(div)
                        if starting_time != div and div!=0 : 
                            starting_time += 1
                        diff = starting_time - d.t_use[instant][0]
                    # print("diff after diff == 0,", diff, getattr(d.mod, f"set_t0_{instant}").at(-1))
                    if diff >= 0 : 
                        getattr(d.mod, f"starting_time_plus_{instant}").fix(diff)
                        getattr(d.mod, f"starting_time_minus_{instant}").fix(0)
                    else :
                        getattr(d.mod, f"starting_time_plus_{instant}").fix(0)
                        getattr(d.mod, f"starting_time_minus_{instant}").fix(-diff)
                        
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
                    
    def unfix_device_values(self) :
        # Unfix the variables
        for d in self.devices : 
            # if white goods
            if hasattr(d.mod, "t_confort_lvl") : 
                for instant in d.mod.t_set : 
                    starting_time = int((d.t_use[instant][0] + getattr(d.mod, f"set_t0_{instant}").at(1))/2)
                    diff = d.t_use[instant][0] - starting_time
                    if diff == 0 : 
                        starting_time = int((d.t_use[instant][0] + getattr(d.mod, f"set_t0_{instant}").at(-1))/2)
                    diff = d.t_use[instant][0] - starting_time
                    if diff >= 0 : 
                        getattr(d.mod, f"starting_time_plus_{instant}").unfix()
                        getattr(d.mod, f"starting_time_minus_{instant}").unfix()
                    else :
                        getattr(d.mod, f"starting_time_plus_{instant}").unfix()
                        getattr(d.mod, f"starting_time_minus_{instant}").unfix()
                
            elif hasattr(d.mod, "E") : 
                # A lot of constraint particularly for EV, so fix Pcons to 0 and then deactivate constraints
                for t in d.mod.t_set :
                    getattr(d.mod, "Pcons")[t].unfix()
                for c in d.mod.component_objects(pyo.Constraint) :
                    c.activate()
            
            else : 
                for t in d.mod.t_set : 
                    getattr(d.mod, "allocated_power")[t].unfix()
                    
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