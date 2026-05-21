import sys
sys.path.append("/Users/theophilemounier/Desktop/git/projet_g3/python")
sys.path.append("/home/theophile/Desktop/git/projet_g3/python")
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import matplotlib.pyplot as plt
import pandas as pd 
import os 

from commu_opti.generate_device_infos import generate_member_data_random
from commu_opti.commu_builder import define_community, define_members
from commu_opti.community.utils import extract_values
#%%

n_iter_max = 1000
averages = []
variances = []
eps_average = 0.001
eps_variance = 0.001
c = 0
results = {}
while c<2 or ((abs(averages[-1] - averages[-2])/averages[-1] > eps_average or abs(variances[-1] - variances[-2])/variances[-1] > eps_variance) and c < n_iter_max):
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


#%% look at each device values

non_equip = ['Econs', 'Pcons_max', 'Pcons_min', 'Pgrid_max', 'Pgrid_min', 'Egrid_plus', 'Egrid_minus']
tableau = {}
for equipment in results : 
    if equipment not in non_equip : 
        average_Econs = sum(results[equipment]["Econs"])/len(results[equipment]["Econs"])
        average_P_max = max(results[equipment]["Pcons_max"])
        average_P_min = min(results[equipment]["Pcons_min"])
        tableau[equipment] = {"Econs" : average_Econs, "Pcons_max" : average_P_max, "Pcons_min" : average_P_min}

df = pd.DataFrame(tableau, index=["Econs", "Pcons_max", "Pcons_min"], columns=tableau.keys())
df = df.round(2)
# df.to_csv(os.path.join(os.path.dirname(__file__), "results_generation_data.csv"))

png_path = os.path.join(os.path.dirname(__file__), "results_generation_data.png")
fig, ax = plt.subplots(figsize=(0.6 + 1 * len(df.columns), 5))
ax.axis("off")
table = ax.table(
    cellText=df.values,
    rowLabels=df.index,
    colLabels=df.columns,
    cellLoc="center",
    loc="center",
)
table.auto_set_font_size(False)
table.set_fontsize(8)
fig.tight_layout()
# fig.savefig(png_path, dpi=300, bbox_inches="tight")
# plt.close(fig)

# On va pouvoir vérifier éléments par éléments ce qui ne va pas 

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