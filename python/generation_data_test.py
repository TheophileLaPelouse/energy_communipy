import sys
sys.path.append("/Users/theophilemounier/Desktop/git/projet_g3/python")
sys.path.append("/home/theophile/Desktop/git/projet_g3/python")
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import matplotlib.pyplot as plt

from commu_opti.generate_device_infos import generate_member_data_random
from commu_opti.commu_builder import define_community, define_members
from commu_opti.community.utils import extract_values


n_iter_max = 500
averages = []
variances = []
eps_average = 10
eps_variance = 10
c = 0
results = {}
while c<2 or ((abs(averages[-1] - averages[-2]) > eps_average or abs(variances[-1] - variances[-2]) > eps_variance) and c < n_iter_max):
    print(f"Iteration {c}")
    param, final_result = generate_member_data_random()
    param["parameters"]["socio"] = [0, 0, 0, 1] # maximize confort should represent the current situation for people
    param["parameters"]["calc_ref"] = False
    list_members_params = [param]
    members = define_members(list_members_params)
    m = members[0]
    m.build_model()
    state = m.self_optimize('gurobi')
    if str(state['Solver'][0]['Status']) == 'warning' :
        break
    extract_values(m, results)
    if not averages : 
        averages.append(results["Econs"][0])
        variances.append(0)
    else :
        averages.append((c-1)/c * averages[-1] + results["Econs"][-1]/c)
        variances.append((c-1)/c * (variances[-1] + averages[-2]**2) + (results["Econs"][-1])**2/c - averages[-1]**2)
    c += 1

# param, final_result = generate_member_data_random()
# param["parameters"]["socio"] = [0, 0, 0, 1] # maximize confort should represent the current situation for people
# list_members_params = [param]
# members = define_members(list_members_params)
# m = members[0]
# m.self_optimize('gurobi')

plt.figure()
plt.plot(averages, '+')
plt.title("Average of Econs")
plt.xlabel("Iteration")
plt.ylabel("Average of Econs")

plt.figure()
plt.plot(variances, '+')
plt.title("Variance of Econs")
plt.xlabel("Iteration")
plt.ylabel("Variance of Econs")


#%% Test heating power model

from commu_opti.data.generate_data_V2 import heating_power_model

allocated = final_result['heating_system']['args']['allocated']
result = final_result['heating_system']['args']
T = {
    'awake' : allocated["T_wanted_awake"], 
    'asleep' : allocated["T_wanted_asleep"],
    'away' : allocated["T_wanted_away"]
}

T_min = {
        "awake" : 16, 
        "asleep" : 14,
        "away" : 10
    }

presence_profile = result['presence_profile']
R1 = result['building']['R1']
R2 = result['building']['R2']
C = result['building']['C']
weather = result['weather']
total_time = len(presence_profile)
deltat = 1
typ = "resistor"
power_profile = heating_power_model(T, weather["forecast"]["temperature"], presence_profile, R1, R2, C, total_time, deltat, typ)[0]
power_profile_min = heating_power_model(T_min, weather["forecast"]["temperature"], presence_profile, R1, R2, C, total_time, deltat, typ)[0]


#%% Test clim power model

from commu_opti.data.generate_data_V2 import clim_profile

allocated = final_result['climatisation']['args']['allocated']
result = final_result['climatisation']['args']
weather = result['weather']
params_clim, debug = clim_profile(allocated, deltat, total_time, result['presence_profile'], weather, result['building'], debug=True)