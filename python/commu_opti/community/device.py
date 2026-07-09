from . import pyo
from .constraint_functions_devices import *
import time
from ..data.generate_data_V2 import heating_power_model, clim_power_model
class device :
    def __init__(self, power_range, time_use, time_range, **kwargs) : 
        """Describe behaviour of any device in the community other than battery and maybe EV

        Args:
            power_range (_type_): list of power range [min, max]
            time_use (_type_): list of [t0, tend] in hour (if week t0 can be > 24)
            time_range (_type_): list of [-trange, +trange] ie [-2, 2] if it can be 2 hours later or before
            nb_hour (_type_): _description_
        """
        
        
        # input definition
        self.name = kwargs.get("name", "device")
        self.p_range = power_range
        self.t_use = time_use 
        self.t_range = time_range 
        self.total_time = kwargs.get('total_time', 24)
        self.deltat = kwargs.get('deltat', 1) # hour
        if len(self.p_range) >= self.total_time // self.deltat : 
            self.p_range = self.p_range[:self.total_time // self.deltat]
            self.t_use = self.t_use[:self.total_time // self.deltat]
            self.t_range = self.t_range[:self.total_time // self.deltat]
        self.dico_used_time = {}
        try : 
            assert(len(self.p_range) == len(self.t_use))
            assert(len(self.p_range) == len(self.t_range))
        except : 
            print("Warning : wrong size in the list when initializing device")
        
        time=0
        c = 0
        # print(self.t_use)
        while time < self.total_time and c < len(self.t_use): 
            # print(c)
            t0, tend = self.t_use[c]
            tmin = max(0, t0 + self.t_range[c][0])
            tmax = min(self.total_time, tend + self.t_range[c][1]+1)
            if time == t0 : 
                for t in range(tmin, tmax):
                    self.dico_used_time[t] = c
                    time+=1
                c += 1
            else : 
                time+=1
        
        # ouput definition
        mod = pyo.ConcreteModel()
        self.mod = mod
        self.time_total_set = pyo.RangeSet(0, self.total_time - 1)
        self.t_set = pyo.RangeSet(0, len(self.p_range) - 1)  # set of time interval
        mod.time_total_set = self.time_total_set
        mod.t_set = self.t_set
        
        
        self.mod.p_range = pyo.Param(self.t_set, range(2), initialize={(k, i) : self.p_range[k][i] for k in self.t_set for i in range(2)}, mutable=True)
        
        self.Pcons = pyo.Var(self.time_total_set, within=pyo.Reals, initialize=[0 for t in self.time_total_set])
        self.mod.Pcons = self.Pcons
        
        self.power_score = 0
        self.time_score = 0 
        
        # Memory will be used if needed during rolling horizon
        self.memory = {}
        


 

        
    def generate_power_constraint(self) : 
        # excesses 
        self.mod.allocated_power = pyo.Var(self.t_set, within=pyo.Reals, initialize=0)
        self.mod.p_excess_l = pyo.Var(self.t_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.t_set])
        self.mod.p_excess_u = pyo.Var(self.t_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.t_set])
        # For now we fix the excess to 0, we will see later if we add a penalization for it or not.
        for k in self.mod.t_set : 
            self.mod.p_excess_l[k].fix(0)
            self.mod.p_excess_u[k].fix(0)
        self.mod.p_con_l = pyo.Constraint(self.mod.t_set, rule=power_constraint_lower)
        self.mod.p_con_u = pyo.Constraint(self.mod.t_set, rule=power_constraint_upper)
        
        
    def generate_bat_constraint(self, E_end=None) : 
        mod = self.mod
        # Initialization of the parameters
        
        mod.E0 = pyo.Param(range(len(self.E0)), initialize=self.E0, within=pyo.Reals, mutable=True)
        mod.charge_eff = pyo.Param(initialize=self.charge_eff, within=pyo.NonNegativeReals, mutable=True)
        mod.dcharge_eff = pyo.Param(initialize=self.dcharge_eff, within=pyo.NonNegativeReals, mutable=True)
        mod.E_range = pyo.Expression(range(2), initialize={0 : self.E_range[0], 1 : self.E_range[1]})
        mod.p_range_bat = pyo.Param(range(2), initialize=self.p_range_bat, within=pyo.Reals, mutable=True)
        
        if self.E_min is not None : 
            mod.E_min = pyo.Param(range(len(self.E_min)), initialize=self.E_min, within=pyo.Reals, mutable=True)
            
        mod.soc_con = pyo.Constraint(self.mod.time_total_set, rule=soc)
        mod.soc_max_con = pyo.Constraint(self.mod.time_total_set, rule=soc_max)
        mod.soc_min_con = pyo.Constraint(self.mod.time_total_set, rule=soc_min)
        mod.P_plus_max_con = pyo.Constraint(self.mod.time_total_set, rule=P_plus_max)
        mod.P_minus_max_con = pyo.Constraint(self.mod.time_total_set, rule=P_minus_max)

        mod.pow_con = pyo.Constraint(self.mod.time_total_set, rule=power_constraint_bat)
            
        # if E_end is None : 
        #     mod.E_end = pyo.Param(initialize=self.E0[0], within=pyo.Reals, mutable=True)
        # else : 
        #     mod.E_end = pyo.Param(initialize=E_end, within=pyo.Reals, mutable=True)
        
        mod.comfort_charge = pyo.Var(self.mod.time_total_set, within=pyo.NonNegativeReals, initialize=0)
        # if self.E_min : 
        mod.end_con = pyo.Constraint(self.mod.time_total_set, rule=end_constraint) # Need to fix E_min_t[-1] to E_end
        # else :   
        #     mod.end_con = pyo.Constraint(rule=soc_end)
            
class white_good(device) : 
    def __init__(self, start_pref, cycle_length, time_range, power_needed, **kwargs) : 
        """Define a device with a fixed cycle

        Args:
            start_pref (int): time index of preference for each cycle start
            cycle_length (int): length of each cycle
            time_range (list): list of time ranges
            power_needed (list): list of power needed at each time step
            
        To do : add another list for forbidden zone to allow discountinuous time range 
        """
        power_range = [[power_needed[k], power_needed[k]] for k in range(len(start_pref))]
        cycle_length = [int(cycle_length[k]/kwargs.get("deltat", 1)) + 1 
                        if int(cycle_length[k]/kwargs.get("deltat", 1)) != cycle_length[k]/kwargs.get("deltat", 1) 
                        else int(cycle_length[k]/kwargs.get("deltat", 1)) 
                        for k in range(len(cycle_length))
                        ]
        
        # print("cycle_length", cycle_length, "start_pref", start_pref)
        self.start_pref = start_pref
        self.time_range = time_range
        self.cycle_length = cycle_length
        self.power_needed = power_needed
        time_use = [[start_pref[k], start_pref[k] + cycle_length[k]] for k in range(len(start_pref))]
        self.n_set = len(start_pref)
        self.max_set = 4
        
        self.memory['original'] = {
            "start_pref" : start_pref,
            "cycle_length" : cycle_length,
            "time_range" : time_range,
            "power_needed" : power_needed
        }
        # print("time_use", time_use)
        super().__init__(power_range, time_use, time_range, **kwargs)
        for times in time_use : 
            if times[1] > self.total_time : 
                print("Warning : cycle length too long for the total time, it will be reduced to fit the total time")
                times[1] = self.total_time
        self.t_min, self.t_max, self.cycle_length = [], [], []
        
        self.mod.power_previous_cycle = pyo.Param(self.mod.time_total_set, initialize={k : 0 for k in self.mod.time_total_set}, within=pyo.Reals, mutable=True)
        self.generate_spec_constraint()
        
    def generate_spec_constraint(self) :
        
        # No white goods can be used more than 4 times (limit the computation time)
        self.mod.max_set = pyo.RangeSet(0, self.max_set-1)
        
        # We make the parameters as large as possible to be able to change them in the future without changing the model.
        t_min = [max(0, self.t_use[k][0] + self.t_range[k][0]) if k in self.mod.t_set else 0 for k in self.mod.max_set]
        t_max = [min(self.total_time, self.t_use[k][1] + self.t_range[k][1]+1) if k in self.mod.t_set else self.total_time for k in self.mod.max_set]
        cycle_length = [self.t_use[k][1] - self.t_use[k][0] - 1 if k in self.mod.t_set else 0 for k in self.mod.max_set]
        self.mod.used_time = pyo.Param(self.mod.max_set, initialize={k : 1 if k in self.mod.t_set else 0 for k in self.mod.max_set}, within=pyo.Boolean, mutable=True)
        
        self.mod.t_wanted = pyo.Param(self.mod.max_set, initialize={k : self.t_use[k][0] if k in self.mod.t_set else 0 for k in self.mod.max_set}, within=pyo.NonNegativeReals, mutable=True)

        available_time = pyo.Param(self.mod.time_total_set, self.mod.time_total_set, within=pyo.Boolean, initialize=0, mutable=True)
        available_time_set = pyo.Param(self.mod.max_set, self.mod.time_total_set, within=pyo.Boolean, initialize=0, mutable=True)
        
        self.t_min, self.t_max, self.cycle_length = t_min, t_max, cycle_length
        self.mod.available_time, self.mod.available_time_set = available_time, available_time_set
        
        t_set = 0
        for c in self.mod.t_set :
            for t in self.mod.time_total_set : 
                interval_min = max(t-cycle_length[t_set], t_min[t_set])
                interval_max = min(t, t_max[t_set]-cycle_length[t_set])
                for t2 in range(interval_min, interval_max+1) :
                    available_time[t, t2].set_value(1)
            for t in range(t_min[t_set], t_max[t_set]-cycle_length[t_set]) : 
                available_time_set[t_set, t].set_value(1)
            t_set+=1
        
        self.mod.double_set = pyo.RangeSet(0, 2*self.total_time-1)
        self.mod.p_range_wg = pyo.Param(
            self.mod.max_set, self.mod.double_set, 
            initialize={(k, t) : self.power_needed[k] if k < self.n_set and t <= self.cycle_length[k] else 0 for k in self.mod.max_set for t in self.mod.double_set},
            mutable=True) # 2*range for having 0 on negative indexes.
        
        bin_t0 = pyo.Var(self.mod.max_set, self.mod.time_total_set, within=pyo.Boolean, initialize=0)
        starting_time_plus = pyo.Var(self.mod.max_set, within=pyo.NonNegativeReals, initialize=0)
        starting_time_minus = pyo.Var(self.mod.max_set, within=pyo.NonNegativeReals, initialize=0)
        
        pow_con = pyo.Constraint(self.mod.time_total_set, rule=rule_pow_wg)
        
        self.mod.bin_t0, self.mod.starting_time_plus, self.mod.starting_time_minus = bin_t0, starting_time_plus, starting_time_minus
        
        self.mod.pow_con = pow_con
        
        
        time_con = pyo.Constraint(self.mod.max_set, rule=time_constraint)
        time_con2 = pyo.Constraint(self.mod.max_set, rule=time_constraint2)
        starting_time_con_plus = pyo.Constraint(self.mod.max_set, rule=starttime_con_plus)
        starting_time_con_minus = pyo.Constraint(self.mod.max_set, rule=starttime_con_minus)
        self.mod.t_confort_lvl = pyo.Expression(expr=sum(starting_time_plus[t] + starting_time_minus[t] for t in self.mod.max_set))
        
        self.mod.time_con, self.mod.starting_time_con_plus, self.mod.starting_time_con_minus = time_con, starting_time_con_plus, starting_time_con_minus
        self.mod.time_con2 = time_con2
        
        for k in self.mod.max_set : 
            if k not in self.mod.t_set : 
                starting_time_plus[k].fix(0)
                starting_time_minus[k].fix(0)
                bin_t0[k, :].fix(0)
                
                time_con[k].deactivate()
                starting_time_con_plus[k].deactivate()
                starting_time_con_minus[k].deactivate()
            
        
    def update_time_param(self, **kwargs) : 
        """
        Update the time parameters of the white good, in case we want to change them during the optimization process
        to update : 
        t_min, t_max, cycle_length, available_time, available_time_set, t_wanted, used_time
        """
        
        # print(f"\n Before any update, {self.start_pref=}, {self.cycle_length=}, {self.time_range=}, {self.power_needed=}")
        
        
        n_set = len(self.start_pref)
        if not kwargs.get("keep_id_0", True) : 
            self.start_pref.pop(0)
            self.time_range.pop(0)
            self.power_needed.pop(0)
            self.cycle_length = [self.cycle_length[k+1] for k in range(self.max_set-1)] + [0]
            n_set -= 1
        
        if kwargs.get("other_changes") : 
            if kwargs["other_changes"].get("start_pref") :
                self.start_pref = kwargs["other_changes"]["start_pref"]
            if kwargs["other_changes"].get("cycle_length") :              
                self.cycle_length = kwargs["other_changes"]["cycle_length"]
            if kwargs["other_changes"].get("time_range") :               
                self.time_range = kwargs["other_changes"]["time_range"]
            if kwargs["other_changes"].get("power_needed") :                
                self.power_needed = kwargs["other_changes"]["power_needed"]
            
        if kwargs.get("to_add") :             
            self.start_pref.append(kwargs["to_add"]["start_pref"])
            self.cycle_length[n_set] = kwargs["to_add"]["cycle_length"]
            self.time_range.append(kwargs["to_add"]["time_range"])
            self.power_needed.append(kwargs["to_add"]["power_needed"])
            n_set += 1
            
        if kwargs.get("last_to_change") :             
            for key in kwargs["last"] : 
                if key == "start_pref" : 
                    # print(self.start_pref, kwargs["last"][key])
                    self.start_pref[-1] = kwargs["last"][key]
                elif key == "cycle_length" : 
                    self.cycle_length[n_set-1] = kwargs["last"][key]
                elif key == "time_range" : 
                    self.time_range[-1] = kwargs["last"][key]
                elif key == "power_needed" : 
                    self.power_needed[-1] = kwargs["last"][key]

        self.n_set = n_set
        # print(f"\nUpdate {self.start_pref=}, {self.cycle_length=}, {self.time_range=}, {self.power_needed=}")
        time_use = [[self.start_pref[k], self.start_pref[k] + self.cycle_length[k]] for k in range(len(self.start_pref))]
        index_window = kwargs.get("time_index_window", [0, 24])

        # print(time_use, index_window)
        
        m = self.mod
        used_set = set(range(len(self.start_pref)))
        self.t_min = [max(index_window[0], time_use[k][0] + self.time_range[k][0]) if k in used_set else index_window[0] for k in self.mod.max_set]
        self.t_max = [min(index_window[1]+1, time_use[k][1] + self.time_range[k][1]+1) if k in used_set else index_window[1]+1 for k in self.mod.max_set]
        # print("tmin", self.t_min, "tmax", self.t_max, "cycle_length", self.cycle_length, "time_range", self.time_range)
        # self.cycle_length = [self.cycle_length[k] if k in used_set else 0 for k in self.mod.time_total_set]

        m.t_wanted.store_values({k : max(time_use[k][0], index_window[0]) - index_window[0] if k in used_set else 0 for k in m.max_set})
        m.used_time.store_values({k : 1 if k in used_set else 0 for k in m.max_set})
                
        self.mod.p_range_wg.store_values({(k, t) : self.power_needed[k] if k in used_set and t <= self.cycle_length[k] else 0 for k in m.max_set for t in m.double_set})
        
        available_time_set_dico = {(t_set, t) : 0 for t_set in m.max_set for t in m.time_total_set}
        
        for t_set in m.time_total_set :
            if t_set in m.t_set :
                for t in range(self.t_min[t_set], self.t_max[t_set]-self.cycle_length[t_set]) : 
                    available_time_set_dico[(t_set, t - index_window[0])] = 1
        
        m.available_time_set.store_values(available_time_set_dico)
        
        m.used_time.store_values({k : 1 if k in used_set else 0 for k in self.mod.max_set})
                        
        # print(m.available_time_set.pprint())
        # print(m.used_time.pprint())
        return
    
    def update_params(self, **new_params) : 
        self.update_time_param(**new_params)
        # print("Is previous_cycle in new_params ?", "previous_cycle" in new_params)
        if "previous_cycle" in new_params : 
            # print(f"Update previous cycle for {self.name}, {new_params['previous_cycle']=}")
            self.mod.power_previous_cycle.store_values({k : new_params["previous_cycle"][k] for k in self.mod.time_total_set})

        # print(self.mod.pprint())
        
class fixed(device) :
    def __init__(self, power_profile, **kwargs) : 
        """Fixed profile devices, act as a parameter, so one very simple constraint
        to fix the power at each time step to the value of the profile

        Args:
            power_profile (list): list of power at each time step
        """
        total_time = len(power_profile)
        power_range = [[power_profile[k], power_profile[k]] for k in range(total_time)]
        self.power_profile = power_profile[:]
        self.memory['original'] = {
            "power_profile" : power_profile[:]
        }
        time_use = [[k, k+1] for k in range(total_time)]
        time_range = [[0, 0] for k in range(len(time_use))]
        super().__init__(power_range, time_use, time_range, **kwargs)
        total_t_index = pyo.RangeSet(0, self.total_time//self.deltat - 1)
        self.mod.power_profile = pyo.Param(total_t_index, initialize={k : power_profile[k] for k in total_t_index}, within=pyo.Reals, mutable=True)
        self.mod.pow_con = pyo.Constraint(total_t_index, rule=rule_fixed)
        return
    
    def update_params(self, **new_params) : 
        if new_params.get("power_profile") :
            self.mod.power_profile.store_values({k : new_params["power_profile"][k] for k in self.mod.time_total_set})
        else : 
            start, end = new_params["time_index_window"]
            self.mod.power_profile.store_values({k - start : self.power_profile[k] for k in range(start, end+1)})
            
class PV(device) : 
    def __init__(self, irradiance_profile, **kwargs) :
        """PV devices model. If no surface is given in kwargs, then the surface will remain as a variable.
        The constraint is about computing Pcons using the efficiency of the solar panel 
        and the surface using the irradiance profile.
        
        This model may be not enough if we want to do some robus optimization process.

        Args:
            irradiance_profile (list): irradiance profile for each time step, in W/m2
        """
         
        # One power value per hour
        total_time = len(irradiance_profile)
        eff = kwargs.get("eff", 0.2)
        surface = kwargs.get("surface", None)
        power_range = [[0, 0] for k in range(total_time)] # Not useful, just for size and fixing excess to 0.
        self.irradiance_profile = irradiance_profile[:]
        time_use = [[k, k+1] for k in range(total_time)]
        time_range = [[0, 0] for k in range(len(time_use))]
        super().__init__(power_range, time_use, time_range, **kwargs)
        
        time_set = self.mod.time_total_set
        self.mod.eff = pyo.Param(initialize=eff, within=pyo.NonNegativeReals, mutable=True)
        self.mod.irradiance_profile = pyo.Param(time_set, initialize={k : irradiance_profile[k] for k in time_set}, within=pyo.Reals, mutable=True)
        if not surface :
            self.PV_surface = pyo.Var(initialize=0, within=pyo.NonNegativeReals, bounds=(0, None))
            self.mod.PV_surface = self.PV_surface
            
            self.mod.pow_con = pyo.Constraint(time_set, rule=rule_PV)
        else :
            self.PV_surface = pyo.Param(initialize=surface, within=pyo.NonNegativeReals)
            self.mod.PV_surface = self.PV_surface
            self.mod.pow_con = pyo.Constraint(time_set, rule=rule_PV)
        return
    
    def update_params(self, **kwargs) : 
        if "irradiance_profile" in kwargs :
            # print(f"Update PV device {self.name} irradiance profile", kwargs["irradiance_profile"][:24-kwargs['current_time_index']], 'surface', self.PV_surface.value, "eff", self.mod.eff.value)
            self.mod.irradiance_profile.store_values({k : kwargs["irradiance_profile"][k] for k in self.mod.time_total_set})
        else : 
            start, end = kwargs["time_index_window"]
            self.mod.irradiance_profile.store_values({k - start : self.irradiance_profile[k] for k in range(start, end+1)})
    
class flex(device) : 
    def __init__(self, power_range, **kwargs) : 
        """flexible devices in the sense that they can be freely commanded within a certain range.
    
        Though we associate to them a comfort price for not being at the maximum output on the range.

        Args:
            power_range (list): list of [min, max] power at each time step
            total_time (int): total time of the simulation
        """
        total_time = kwargs.get("total_time", 24)
        self.total_time = total_time
        time_use = [[k, k+1] for k in range(total_time)]
        time_range = [[0, 0] for k in range(total_time)]
        if kwargs.get("heating_params") :
            self.heating_params = kwargs.get("heating_params")
        super().__init__(power_range, time_use, time_range, **kwargs)
        self.original_power_range = power_range[:]
        self.memory['comfort_temp'] = [power_range[0][1]]
        self.memory['actual_temp'] = []
        self.generate_power_constraint()
        self.generate_spec_constraint()

    def generate_spec_constraint(self) : 
        self.mod.pow_con = pyo.Constraint(self.mod.t_set, rule=rule_flex)
        self.mod.p_confort_lvl = pyo.Expression(self.t_set, rule=confort_rule_flex)
        
    def update_params(self, **kwargs) :
        # print(kwargs)
        if hasattr(self, "heating_params") and kwargs.get("weather") and kwargs.get("presence_profile") : 
            # print("\nGoes here")
            T_wanted = self.heating_params['T_wanted']
            T_min = self.heating_params['T_min']
            R1 = self.heating_params['R1']
            R2 = self.heating_params['R2']
            C = self.heating_params['C']
            typ = self.heating_params['type']
            efficiency = self.heating_params['efficiency']
            options = self.heating_params.get("options", {})
            weather = kwargs["weather"]
            presence_profile = kwargs["presence_profile"]
            total_time = self.total_time
            deltat = self.deltat

            # print("weather", weather)
            # print("presence_profile", presence_profile, len(presence_profile), "total_time", total_time)
            # print(presence_profile)
            power_confort_forecast, carnot_confort = heating_power_model(T_wanted, weather, presence_profile, R1, R2, C, total_time, deltat, typ, **options)
            power_min_forecast, carnot_min = heating_power_model(T_min, weather, presence_profile, R1, R2, C, total_time, deltat, typ, **options)
            
            
            p_range_forecast = [(min(power_min_forecast[i], power_confort_forecast[i])/(efficiency*carnot_min[i]), 
                                max(power_min_forecast[i], power_confort_forecast[i])/(efficiency*carnot_confort[i])) 
                                for i in range(total_time)]
            # print("p_range_forecast", p_range_forecast)
            self.mod.p_range.store_values({(k, i) : p_range_forecast[k][i] for k in self.mod.t_set for i in range(2)})
            
            self.memory['comfort_temp'].append(p_range_forecast[0][1]) # Version efficace one at a time]
            # self.memory['comfort_temp'] = self.memory['comfort_temp'][:kwargs.get("current_time_index", 0)] + [p_range_forecast[k][1] for k in range(p_range_forecast)]
            
        elif hasattr(self, "clim_params") and kwargs.get("weather") and kwargs.get("presence_profile") : 
            T_activation = self.clim_params['T_activation']
            T_minus = self.clim_params['T_minus']
            R1 = self.clim_params['R1']
            R2 = self.clim_params['R2']
            C = self.clim_params['C']
            efficiency = self.clim_params['efficiency']
            options = self.clim_params.get("options", {})
            weather = kwargs["weather"]
            presence_profile = kwargs["presence_profile"]
            total_time = self.total_time
            deltat = self.deltat
            flux_forecast, T_in_forecast, carnot_forecast = clim_power_model(T_activation, T_minus, R1, R2, C, weather, presence_profile, total_time, deltat, **options)
            p_range = [(0, flux_forecast[i]/(efficiency*carnot_forecast[i])) for i in range(total_time)]
            self.mod.p_range.store_values({(k, i) : p_range[k][i] for k in self.mod.t_set for i in range(2)})
            
            self.memory['comfort_temp'].append(p_range[0][1])
            
        else : 
            if "p_range" in kwargs : 
                self.mod.p_range.store_values({(k, i) : kwargs["p_range"][k][i] for k in self.mod.t_set for i in range(2)})
            else : 
                start, end = kwargs["time_index_window"]
                self.mod.p_range.store_values({(k - start, i) : self.original_power_range[k][i] for k in range(start, end+1) for i in range(2)})
        
        
class AoN(device) : 
    def __init__(self, power_needed, energy_needed, **kwargs) :
        """
        On or off activation with constraint on total energy consumption.For the water heater for example.
        """
        total_time = kwargs.get("total_time", 24)
        self.total_time = total_time
        time_use = [[k, k+1] for k in range(total_time)]
        time_range = [[0, total_time] for k in range(total_time)]
        power_range = [[power_needed, power_needed] for k in range(total_time)]
        self.energy_needed = energy_needed
        self.power_needed = power_needed
        super().__init__(power_range, time_use, time_range, **kwargs)
        self.mod.power_needed = pyo.Param(initialize=power_needed, within=pyo.NonNegativeReals, mutable=True)
        self.mod.energy_needed = pyo.Param(initialize=energy_needed, within=pyo.NonNegativeReals, mutable=True)
        self.mod.max_factor = pyo.Param(initialize=kwargs.get('max_factor', 1), within=pyo.NonNegativeReals, mutable=True)
        
        self.mod.time_midnight = pyo.Param(initialize=total_time-1, mutable=True, within=pyo.NonNegativeReals)
        self.mod.current_day = pyo.Param(self.mod.time_total_set, initialize={k: 1 if k <= self.mod.time_midnight.value else 0 for k in self.mod.time_total_set}, mutable=True)
        self.mod.energy_needed_day = pyo.Param(initialize=energy_needed, within=pyo.NonNegativeReals, mutable=True)
        self.generate_spec_constraint()
        
    def generate_spec_constraint(self) : 
        """
        Ici on a un vecteur de binaires pour quand ça s'active ou pas.
        """
        m = self.mod
        m.on_off = pyo.Var(m.t_set, within=pyo.Boolean, initialize=[0 for k in m.t_set])
        # m.sum_on_off_con_min = pyo.Constraint(expr=(sum(m.on_off[k] for k in m.t_set)*m.power_needed*self.deltat 
        #                                                >= 
        #                                                m.energy_needed))
        # m.sum_on_off_con_max = pyo.Constraint(expr=(sum(m.on_off[k] for k in m.t_set)*m.power_needed*self.deltat 
        #                                                <= 
        #                                                m.max_factor*m.power_needed*self.deltat + m.energy_needed)) # Maybe m.power_needed*self.deltat is too much

        m.sum_on_off_con_min_day = pyo.Constraint(expr=(sum(m.on_off[k]*m.current_day[k] for k in m.t_set)*m.power_needed*self.deltat 
                                                       >= 
                                                       m.energy_needed_day))
        m.sum_on_off_con_max_day = pyo.Constraint(expr=(sum(m.on_off[k]*m.current_day[k] for k in m.t_set)*m.power_needed*self.deltat 
                                                       <= 
                                                       m.max_factor*m.power_needed*self.deltat + m.energy_needed_day))
        
        m.pow_con = pyo.Constraint(m.t_set, rule=rule_AoN)
        
        return
    
    def update_params(self, **new_params) : 
        if "power_needed" in new_params : 
            self.mod.power_needed.set_value(new_params["power_needed"])
        if "energy_needed" in new_params : 
            self.mod.energy_needed_day.set_value(new_params["energy_needed"])
        if "max_factor" in new_params : 
            self.mod.max_factor.set_value(new_params["max_factor"])
        if "time_midnight" in new_params : 
            self.mod.time_midnight.set_value(new_params["time_midnight"])
            # print("time_midnight", self.mod.time_midnight.value)
            self.mod.current_day.store_values({k: 1 if k <= self.mod.time_midnight.value - 1 else 0 for k in self.mod.time_total_set})
        # print("current_day", self.mod.current_day.extract_values())
        
class battery(device) : 
    def __init__(self, p_range, E_range, **kwargs) : 
        """Battery device model, see the device class for the constraints
        If E_range is None, then the energy will be a variable and the power too.
        In this case, the C rate can be defined.

        Args:
            p_range (list or tuple): max and min power for the battery
            E_range (list or tuple): min and max energy for the battery, put None if you want it to be a variable 
        """
        total_time = kwargs.get("total_time", 24)
        self.total_time = total_time
        t_use = [[k, k+1] for k in range(total_time)]
        power_range = [p_range for k in range(len(t_use))]
        time_range = [[0, 0] for k in range(len(t_use))]
        super().__init__(power_range, t_use, time_range, **kwargs)
        if not E_range : 
            self.capacity = pyo.Var(initialize=0, within=pyo.NonNegativeReals)
            self.E_range = (kwargs.get('min_rate', 0.1) * self.capacity, kwargs.get('max_rate', 0.9) * self.capacity)
            self.mod.capacity = self.capacity
            p_range_rate = kwargs.get('p_range_rate', 0.5)
            self.p_range_bat = (-p_range_rate*self.capacity, p_range_rate*self.capacity)
        else : 
            self.E_range = E_range # [Emin, Emax]
            self.p_range_bat = p_range
            self.capacity = pyo.Param(initialize=self.E_range[1]/0.9, within=pyo.NonNegativeReals)
            self.mod.capacity = self.capacity
        
        # + custom constraints soc : E_min <= E <= E_max + suivie E(t) = E(t - 1) + P delta t
        self.charge_eff = kwargs.get('charge_eff', 0.95)
        self.dcharge_eff = kwargs.get('dcharge_eff', 0.95)
        self.E0 = [kwargs.get('E0', 0.5 * (self.E_range[0] + self.E_range[1]))]
        self.E = pyo.Var(self.t_set, within=pyo.NonNegativeReals, initialize=0)
        self.P_plus = pyo.Var(self.t_set, within=pyo.NonNegativeReals, initialize=0)
        self.P_minus = pyo.Var(self.t_set, within=pyo.NonNegativeReals, initialize=0)

        self.memory['original'] = {"E0": self.E0[0]}

        self.mod.active_time = pyo.Param(self.mod.time_total_set, initialize={k : 1 for k in self.mod.time_total_set}, within=pyo.Boolean, mutable=True)
        self.mod.E_return = pyo.Param(self.mod.time_total_set, initialize={k : self.E0[0] if k == 0 else 0 for k in self.mod.time_total_set}, within=pyo.Reals, mutable=True)
        self.mod.E_min_t = pyo.Param(self.mod.time_total_set, initialize={k : kwargs.get('E_end', self.E0[0]) if k == self.time_total_set[-1] else 0 for k in self.mod.time_total_set}, within=pyo.Reals, mutable=True)
        
        self.mod.E = self.E 
        self.mod.P_plus = self.P_plus
        self.mod.P_minus = self.P_minus
        self.E_min = None
        self.generate_bat_constraint()
        
    def update_params(self, **new_params) :
        if "E0" in new_params : 
            self.mod.E_return[0].set_value(new_params["E0"])
        if new_params.get("update_day_bat") : 
            if new_params["time_midnight"] > 0 : 
                self.mod.E_min_t[new_params["time_midnight"]].set_value(self.mod.E_min_t[new_params["time_midnight"]-1].value)
                self.mod.E_min_t[new_params["time_midnight"]-1].set_value(0)
        if "E_end" in new_params : 
            self.mod.E_min_t[self.total_time-1].set_value(new_params["E_end"])
            # self.mod.E_end.set_value(new_params["E_end"])

class EV(device) : 
    def __init__(self, p_range, E_range, time_home, E0s, E_min, E_end, **kwargs) : 
        """EV device model, it works the same as the battery model but adding the fact that the EV is not always at home.

        Args:
            p_range (list or tuple): max and min power for the EV
            E_range (list or tuple): min and max energy for the EV
            time_home (list): list of time intervals when the EV is home
            E0s (list): First value = value at the beginning of the simulation, 
                then values of energy used while being away, that can be used to compute the next E0.
            E_min (list): list of minimum energies for the EV before depart
            E_end (list): list of final energies for the EV after coming back from the trip.
        """
        total_time = kwargs.get("total_time", 24)
        t_use = [[k, k+1] for k in range(total_time)]
        power_range = [p_range for k in range(total_time)]
        time_range = [[0, 0] for k in range(total_time)]
        super().__init__(power_range, t_use, time_range, **kwargs)
        self.E_min = E_min
        self.E_range = E_range
        self.capacity = pyo.Param(initialize=self.E_range[1]/0.9, within=pyo.NonNegativeReals)
        self.E_end = E_end
        self.p_range_bat = p_range
        
        
        self.memory['original'] = {
            "E0s" : E0s[:],
            "E_min" : E_min[:],
            "E_end" : E_end, 
            "time_home" : time_home[:]
        }
        self.charge_eff = kwargs.get('charge_eff', 0.92)
        self.dcharge_eff = kwargs.get('dcharge_eff', 0.92)
        self.E0 = E0s
        self.E = pyo.Var(self.t_set, within=pyo.Reals, bounds=(self.E_range[0], self.E_range[1]), initialize=(self.E_range[0] + self.E_range[1])/2)
        self.P_plus = pyo.Var(self.t_set, within=pyo.NonNegativeReals, bounds=(0, p_range[1]))
        self.P_minus = pyo.Var(self.t_set, within=pyo.NonNegativeReals, bounds=(0, -p_range[0]))
        
        self.current_time = 0 # For rolling horizon
        self.time_home = time_home
        
        self.mod.active_time = pyo.Param(self.mod.time_total_set, initialize={k : 0 for k in self.mod.time_total_set}, within=pyo.Boolean, mutable=True)
        E_return, E_min_t = self.get_home_values(time_home, E0s, E_min)
        
        self.mod.E_return = pyo.Param(self.mod.time_total_set, initialize={k : E_return[k] for k in self.mod.time_total_set}, within=pyo.Reals, mutable=True)
        self.mod.E_min_t = pyo.Param(self.mod.time_total_set, initialize={k : E_min_t[k] for k in self.mod.time_total_set}, within=pyo.Reals, mutable=True)
        self.mod.E_min_t[self.total_time-1].set_value(max(self.mod.E_min_t[self.total_time-1].value, E_end))
        
        self.mod.E = self.E 
        self.mod.P_plus = self.P_plus
        self.mod.P_minus = self.P_minus
        self.mod.capacity = self.capacity
        self.generate_bat_constraint(E_end=E_end)
        
    def get_home_values(self, time_home, E0s, Emin) : 
        home_set = set()
        to_store = {}
        end_set = set()
        time = 0
        c = 0
        if not time_home : 
            self.mod.active_time.store_values({k : 0 for k in self.mod.time_total_set})
            return [0 for k in self.mod.time_total_set], [0 for k in self.mod.time_total_set]
        while c < len(time_home) and time < self.total_time : 
            t0, tend = time_home[c]
            t0, tend = max(t0 - self.current_time, 0), tend - self.current_time
            if time == t0 : 
                end_set.add(tend)
                for t in range(t0, min(tend, self.total_time)) :
                    home_set.add(t)
                    time+=1
                c += 1
            else : 
                time+=1
        
        self.mod.active_time.store_values({k : 1 if k in home_set else 0 for k in self.mod.time_total_set})
        # print("active_time", {k : 1 if k in home_set else 0 for k in self.mod.time_total_set})
        
        E_return = []
        c = 0
        for t in self.mod.time_total_set : 
            if t==0 : 
                E_return.append(E0s[c])
                c += 1
            else :
                if self.mod.active_time[t].value - self.mod.active_time[t-1].value == 1 : 
                    E_return.append(E0s[c])
                    c += 1
                else :
                    E_return.append(0)
        
        E_min_t = []
        c = 0
        for t in self.mod.time_total_set :
            if t in end_set :
                E_min_t.append(Emin[c])
                c += 1
            else :
                E_min_t.append(0)
        
        return E_return, E_min_t
        
    def update_params(self, **new_params) :
        if "time_home" in new_params : 
            time_home, E0s, E_min = new_params["time_home"], new_params["E0s"], new_params["E_min"]
            self.E0 = E0s
            self.current_time = new_params.get("current_time_index", 0)
            E_return, E_min_t = self.get_home_values(time_home, E0s, E_min)
            self.mod.E_return.store_values({k : E_return[k] for k in self.mod.time_total_set})
            self.mod.E_min_t.store_values({k : E_min_t[k] for k in self.mod.time_total_set})
        if "E0" in new_params : 
            self.mod.E_return[0].set_value(new_params["E0"])
        if "E_end" in new_params : 
            # self.mod.E_end.set_value(new_params["E_end"])
            self.mod.E_min_t[self.total_time-1].set_value(max(self.mod.E_min_t[self.total_time-1].value, new_params["E_end"]))
        
        
if __name__ == '__main__' :
    # Test device initialization
    power_range = [[10, 20], [-10, 10]]
    time_use = [[1, 2], [3, 4]]
    time_range = [[-1, 1], [-2, 2]]
    dev = device(power_range, time_use, time_range)
    dev.mod.p_con_l.pprint()
    dev.mod.p_con_u.pprint()
    dev.mod.t_con_l.pprint()
    dev.mod.t_con_u.pprint()
    
    # Faudra tester un peu plus tout le reste mais on verra plus tard parce que flemme
    
    