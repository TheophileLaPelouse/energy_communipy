from . import pyo
from .constraint_functions_devices import *

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
        self.allocated_power = pyo.Var(self.t_set, within=pyo.Reals)
        
        self.Pcons = pyo.Var(self.time_total_set, within=pyo.Reals, initialize=[0 for t in self.time_total_set])
        self.mod.Pcons = self.Pcons
        
        # excesses 
        self.p_excess_l = pyo.Var(self.t_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.t_set])
        self.p_excess_u = pyo.Var(self.t_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.t_set])
        
        # self.p_excess_l_all = pyo.Var(self.time_total_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_total_set])
        # self.p_excess_u_all = pyo.Var(self.time_total_set, within=pyo.NonNegativeReals, initialize=[0 for t in self.time_total_set])
        
        
        self.power_score = 0
        self.time_score = 0 


        mod.t_set = self.t_set
        mod.allocated_power = self.allocated_power
        mod.p_excess_l = self.p_excess_l
        mod.p_excess_u = self.p_excess_u
        # mod.p_excess_l_all = self.p_excess_l_all
        # mod.p_excess_u_all = self.p_excess_u_all
        
        # For now we fix the excess to 0, we will see later if we add a penalization for it or not.
        for k in self.mod.t_set : 
            mod.p_excess_l[k].fix(0)
            mod.p_excess_u[k].fix(0)
        
        self.variable = not(kwargs.get('is_param', False))
        if self.variable :
            self.generate_power_constraint()
        else : 
            for k in self.mod.t_set : 
                mod.allocated_power[k].fix(self.p_range[k][1])
                mod.opti_t_use[k, 0].fix(self.t_use[k][0])
                mod.opti_t_use[k, 1].fix(self.t_use[k][1])
                mod.p_excess_l[k].fix(0)
                mod.p_excess_u[k].fix(0)
 

        
    def generate_power_constraint(self) : 
        
        self.mod.p_con_l = pyo.Constraint(self.mod.t_set, rule=power_constraint_lower)
        self.mod.p_con_u = pyo.Constraint(self.mod.t_set, rule=power_constraint_upper)
        
        
    def generate_bat_constraint(self, E_end=None) : 
        mod = self.mod
        # Initialization of the state of charge  
        
        
            
        mod.soc_con = pyo.Constraint(self.mod.home_set, rule=soc)
        
        
        mod.soc_max_con = pyo.Constraint(self.mod.home_set, rule=soc_max)
        mod.soc_min_con = pyo.Constraint(self.mod.home_set, rule=soc_min)
        

        mod.P_plus_max_con = pyo.Constraint(self.mod.home_set, rule=P_plus_max)
        mod.P_minus_max_con = pyo.Constraint(self.mod.home_set, rule=P_minus_max)

        mod.pow_con = pyo.Constraint(self.mod.home_set, rule=power_constraint)
        
        mod.pow_con_not_home = pyo.Constraint(self.mod.not_home_set, rule=Pcons_0_constraint)
        
        if E_end is None : 
            E_end = self.E0[0]
        
        if not self.E_min : 
            mod.end_con = pyo.Constraint(rule=soc_end)
       
        else : 
            mod.start_con = pyo.Constraint(self.start_set, rule=start_constraint)
            mod.end_con = pyo.Constraint(self.end_set, rule=end_constraint)
            
            
        
        
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
        time_use = [[start_pref[k], start_pref[k] + cycle_length[k]] for k in range(len(start_pref))]
        # print("time_use", time_use)
        super().__init__(power_range, time_use, time_range, **kwargs)
        for times in time_use : 
            if times[1] > self.total_time : 
                print("Warning : cycle length too long for the total time, it will be reduced to fit the total time")
                times[1] = self.total_time
        self.generate_spec_constraint()
        
    def generate_spec_constraint(self) : 
        """
        For each cycle, we have a constraint, we will use 1 constraint for the power 
        and 2 others to count positively and negatively the time gap with the comfort value
        
        For the power : 
        S = [max(t - cycle_length, tmin), min(t, tmax - cycle_length)] ([tmin, tmax] being set_t0)
        sum bin_t0[t]*power_needed for t in S) == Pcons[t] (power_needed is constant during a cycle)
        
        For the comfort : 
        starting_time_plus >= sum bin_t0[t]*t for t in set_t0) - start_pref
        starting_time_minus >= start_pref - sum bin_t0[t]*t for t in set_t0)

        """
        set_P0 = pyo.RangeSet(0, self.total_time - 1)
        for instant in self.mod.t_set : 
            # print("\n INSTANT %d" % instant)
            t_min = max(0, self.t_use[instant][0] + self.t_range[instant][0])
            t_max = min(self.t_use[instant][1] + self.t_range[instant][1], self.total_time-1)
            cycle_length = self.t_use[instant][1] - self.t_use[instant][0] - 1
            set_t0 = pyo.RangeSet(t_min,t_max-cycle_length)
            set_P0 = set_P0.difference(set_t0)
            bin_t0 = pyo.Var(set_t0, within=pyo.Boolean)
            starting_time_plus = pyo.Var(within=pyo.NonNegativeReals)
            starting_time_minus = pyo.Var(within=pyo.NonNegativeReals)
            
            setattr(self.mod, f"set_t0_{instant}", set_t0)
            # setattr(self.mod, f"set_d_{instant}", set_t0)
            setattr(self.mod, f"bin_{instant}", bin_t0)
            setattr(self.mod, f"starting_time_plus_{instant}", starting_time_plus)
            setattr(self.mod, f"starting_time_minus_{instant}", starting_time_minus)
            
            time_con= pyo.Constraint(expr=sum(bin_t0[t] for t in set_t0)==1)
            
            # print("BONJOUR", self.t_use[instant][0], self.t_range[instant])
            # set_t0.display()
            
            setattr(self.mod, f"bin_t_con_{instant}", time_con)
            starttime_con_plus = pyo.Constraint(expr=sum(t*bin_t0[t] for t in set_t0)- self.t_use[instant][0] <= starting_time_plus)
            setattr(self.mod, f"starttime_con_plus_{instant}", starttime_con_plus)
            starttime_con_minus = pyo.Constraint(expr=self.t_use[instant][0] - sum(t*bin_t0[t] for t in set_t0) <= starting_time_minus)
            setattr(self.mod, f"starttime_con_minus_{instant}", starttime_con_minus)
            
            # set_t0.display()

            pow_con = pyo.Constraint(set_t0, rule=rule_pow_wg)
            setattr(self.mod, f"bin_p_con_{instant}", pow_con)
            
            confort_con = pyo.Expression(rule=rule_confort)
            setattr(self.mod, f"confort_con_{instant}", confort_con)
            

        pow_con = pyo.Constraint(set_P0, rule=rule_pow_wg2)
        self.mod.pow_con = pow_con
        
        self.mod.t_confort_lvl = pyo.Expression(expr = sum(getattr(self.mod, f"confort_con_{instant}") for instant in self.mod.t_set))
            
        return
            
        
class fixed(device) :
    def __init__(self, power_profile, **kwargs) : 
        """Fixed profile devices, act as a parameter, so one very simple constraint
        to fix the power at each time step to the value of the profile

        Args:
            power_profile (list): list of power at each time step
        """
        total_time = len(power_profile)
        power_range = [[power_profile[k], power_profile[k]] for k in range(total_time)]
        time_use = [[k, k+1] for k in range(total_time)]
        time_range = [[0, 0] for k in range(len(time_use))]
        super().__init__(power_range, time_use, time_range, **kwargs)
        total_t_index = pyo.RangeSet(0, len(power_profile)-1)
        self.mod.pow_con = pyo.Constraint(total_t_index, rule=rule_fixed)
        return
    
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
        time_use = [[k, k+1] for k in range(total_time)]
        time_range = [[0, 0] for k in range(len(time_use))]
        super().__init__(power_range, time_use, time_range, **kwargs)
        
        if not surface :
            self.PV_surface = pyo.Var(initialize=0, within=pyo.NonNegativeReals, bounds=(0, None))
            self.mod.PV_surface = self.PV_surface
            
            self.mod.pow_con = pyo.Constraint(self.time_total_set, rule=rule_PV)
        else :
            self.PV_surface = pyo.Param(initialize=surface, within=pyo.NonNegativeReals)
            self.mod.PV_surface = self.PV_surface
            self.mod.pow_con = pyo.Constraint(self.time_total_set, rule=rule_PV)
        return
    
    def update_irradiance(self, new_irradiance) : 
        del self.mod.pow_con
        self.mod.pow_con = pyo.Constraint(self.time_total_set, rule=rule_PV)
    
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
        super().__init__(power_range, time_use, time_range, **kwargs)
        self.generate_spec_constraint()

    def generate_spec_constraint(self) : 

        self.mod.pow_con = pyo.Constraint(self.mod.t_set, rule=rule_flex)
        self.mod.p_confort_lvl = pyo.Expression(self.t_set, rule=confort_rule_flex)
        
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
        self.generate_spec_constraint()
        
    def generate_spec_constraint(self) : 
        """
        Ici on a un vecteur de binaires pour quand ça s'active ou pas.
        """
        self.mod.on_off = pyo.Var(self.mod.t_set, within=pyo.Boolean, initialize=[0 for k in self.mod.t_set])
        self.mod.sum_on_off_con_min = pyo.Constraint(expr=(sum(self.mod.on_off[k] for k in self.mod.t_set)*self.power_needed*self.deltat 
                                                       >= 
                                                       self.energy_needed))
        self.mod.sum_on_off_con_max = pyo.Constraint(expr=(sum(self.mod.on_off[k] for k in self.mod.t_set)*self.power_needed*self.deltat 
                                                       <= 
                                                       max(1.5*self.energy_needed, self.power_needed*self.deltat + self.energy_needed)))

        self.mod.pow_con = pyo.Constraint(self.mod.t_set, rule=rule_AoN)
        
        self.mod.p_con_l.deactivate()
        self.mod.p_con_u.deactivate()
        self.mod.p_excess_l.fix(0)
        self.mod.p_excess_u.fix(0)
        return
        
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
            self.E_range = (kwargs.get('min_rate', 0.1 * self.capacity), kwargs.get('max_rate', 0.9 * self.capacity))
            self.mod.capacity = self.capacity
            p_range_rate = kwargs.get('p_range_rate', 0.5)
            self.p_range_bat = (-p_range_rate*self.capacity, p_range_rate*self.capacity)
        else : 
            self.E_range = E_range # [Emin, Emax]
            self.p_range_bat = p_range
            self.capacity = pyo.Param(initialize=self.E_range[1], within=pyo.NonNegativeReals)
            self.mod.capacity = self.capacity
        
        # + custom constraints soc : E_min <= E <= E_max + suivie E(t) = E(t - 1) + P delta t
        self.charge_eff = kwargs.get('charge_eff', 0.98)
        self.dcharge_eff = kwargs.get('dcharge_eff', 0.98)
        self.E0 = [kwargs.get('E0', 0.5 * (self.E_range[0] + self.E_range[1]))]
        self.E = pyo.Var(self.t_set, within=pyo.NonNegativeReals)
        self.P_plus = pyo.Var(self.t_set, within=pyo.NonNegativeReals)
        self.P_minus = pyo.Var(self.t_set, within=pyo.NonNegativeReals)
        self.mod.not_home_set = pyo.RangeSet()
        self.mod.home_set = pyo.RangeSet(0, self.total_time - 1) # Exist because same function for EV
        self.start_set = pyo.Set(initialize=[0])
        self.end_set = pyo.Set()
      
        self.mod.E = self.E 
        self.mod.P_plus = self.P_plus
        self.mod.P_minus = self.P_minus
        self.E_min = None
        self.generate_bat_constraint(E_end=kwargs.get('E_end', self.E0[0]))

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
        self.E_end = E_end
        self.p_range_bat = p_range
        
        self.charge_eff = kwargs.get('charge_eff', 0.92)
        self.dcharge_eff = kwargs.get('dcharge_eff', 0.92)
        self.E0 = E0s
        self.E = pyo.Var(self.t_set, within=pyo.Reals, bounds=(self.E_range[0], self.E_range[1]))
        self.P_plus = pyo.Var(self.t_set, within=pyo.NonNegativeReals, bounds=(0, p_range[1]))
        self.P_minus = pyo.Var(self.t_set, within=pyo.NonNegativeReals, bounds=(0, -p_range[0]))
        
        home_set = []
        start_set = []
        end_set = []
        not_home_set = []
        time = 0
        c = 0
        while time < self.total_time : 
            t0, tend = time_home[c]
            if time == t0 : 
                start_set.append(t0)
                end_set.append(tend-1)
                for t in range(t0, tend):
                    home_set.append(t)
                    time+=1
                c += 1
            else : 
                not_home_set.append(time)
                time+=1
        

        self.mod.home_set = pyo.Set(initialize=home_set)
        self.mod.not_home_set = pyo.Set(initialize=not_home_set)
        
        self.start_set = pyo.Set(initialize=start_set)
        self.mod.start_set = self.start_set
        self.end_set = pyo.Set(initialize=end_set)
        self.mod.end_set = self.end_set
        
        self.mod.E = self.E 
        self.mod.P_plus = self.P_plus
        self.mod.P_minus = self.P_minus
        self.generate_bat_constraint(E_end=E_end)
        
        
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
    
    