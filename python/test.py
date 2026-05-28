import sys
sys.path.append("/Users/theophilemounier/Desktop/git/projet_g3/python")
sys.path.append("/home/theophile/Desktop/git/projet_g3/python")
import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import matplotlib.pyplot as plt

#%% test de device.py

# import commu_opti.community.device as d


# power_range = [[10, 20], [-10, 10]]
# time_use = [[1, 2], [3, 4]]
# time_range = [[-1, 1], [-2, 2]]
# dev = d.device(power_range, time_use, time_range)
# dev.mod.p_con_l.pprint()
# dev.mod.p_con_u.pprint()
# dev.mod.t_con_l.pprint()
# dev.mod.t_con_u.pprint()


#%% test de membre.py
import commu_opti.community.device as d
import commu_opti.community.community as comm

prod_profile = [0, 0, 0, 0, 0, 0, 0, 0, 30, 30, 30, 30, 30, 30, 30, 30, 0, 0, 0, 0, 0, 0, 0, 0]

# prod_profile = [30 for k in range(24)]
# Objets
# machine à laver 

options = {"total_time" : 24, "deltat" : 1}
# wash_mach = {'cycle_length' : [6], 
#              'power_needed' : [3], 
#              "start_pref" : [16], 
#              "time_range" : [[-24, 24]], 
#              }

wash_mach = {'cycle_length': [3],
  'power_needed': [2000.0],
  'start_pref': [22],
  'time_range': [[0, 0]]
  }

# wash_mach = {'cycle_length' : [0.5], 
#              'power_needed' : [3], 
#              "start_pref" : [18], 
#              "time_range" : [[0, 0]], 
#              }

device_wash_mach = d.white_good(**wash_mach, **options)

print("\nWASHING MACHINE DEFINED\n")

# plaque_electrique

# {'parameters': {'cycle_length': [0.5, 0.5],
#   'power_needed': [0.0, 0.0],
#   'start_pref': [13, 18],
#   'time_range': [(12, 14), (18, 22)],
#   'name': 'plaque_electrique'},
#  'type': 'white_good'}

# réfrigérateur

therm_load = {
    "power_range" : [[8, 9] for k in range(options["total_time"])], 
}

device_therm = d.flex(**therm_load, **options)

print("\nTHERMAL LOAD DEFINED\n")

# EV

# EV_load = {
#     "p_range" : [-10000, 10000], 
#     "E_range" : [8360.0, 41800.0],
#     "time_home" : [[0, 20], [22, 24]], 
#     "E0s" : [25080.0, -12825.25809394293],
#     "E_min" : [21185.25809394293, 25080.0], 
#     "E_end" : 21185.25809394293
# }

EV_load = {
    "p_range" : [-10, 10], 
    "E_range" : [8, 40],
    "time_home" : [[4, 10], [18, 24]], 
    "E0s" : [25, -13],
    "E_min" : [20, 25], 
    "E_end" : 20
}

device_EV = d.EV(**EV_load)

print("\nEV DEFINED\n")

# Fixed profile

fixed_load = {
    "power_profile" : [5 for t in range(options["total_time"])]
}

fixed_load_device = d.fixed(**fixed_load, **options)

print("\nFIXED DEFINED\n")

pv_prod = {
    "irradiance_profile" : prod_profile, 
    "surface" : None,
    "eff" : 0.2,
    }

pv_prod_device = d.PV(**pv_prod, **options)

print("\nPV PRODUCTION DEFINED\n")

bat_load = {
    "p_range" : [-10, 10], 
    "E_range" : None, 
    }

bat_load_device = d.battery(**bat_load, **options)

print("\nBATTERY DEVICE DEFINED\n")

def define_devices(wash_mach, therm_load, EV_load, fixed_load, pv_prod, bat_load, options) :
    device_wash_mach = d.white_good(**wash_mach, **options)
    device_therm = d.flex(**therm_load, **options)
    device_EV = d.EV(**EV_load)
    device_fixed = d.fixed(**fixed_load, **options)
    device_PV = d.PV(**pv_prod, **options)
    device_bat = d.battery(**bat_load, **options)
    
    return device_wash_mach, device_therm, device_EV, device_fixed, device_PV, device_bat


community = comm.community([])

import commu_opti.community.member as memb
# Create dictionaries for different test cases
test_cases = {
    "wash_machine": {
        "name": "wash_test",
        "devices": [],
        "community": community,
        "prod_profile" : prod_profile, 
        "socio" : [1, 0, 0, 0.01], 
        "id" : 1
    },
    # "thermostat": {
    #     "name": "therm_test",
    #     "devices": [],
    #     "community": community,
    #     "prod_profile" : prod_profile, 
    #     "socio" : [1, 0, 0, 100], 
    #     "id" : 1
    # },
    # "EV": {
    #     "name": "EV_test",
    #     "devices": [],
    #     "community": community,
    #     "prod_profile" : prod_profile, 
    #     "socio" : [1, 0, 0, 1], 
    #     "id" : 1
    # },
    # "fixed_profile": {
    #     "name": "fixed_profile_test",
    #     "devices": [],
    #     "community": community,
    #     "prod_profile" : prod_profile, 
    #     "socio" : [1, 0, 0, 1], 
    #     "id" : 1
    # },
    # "bat" : {
    #     "name" : "bat_test", 
    #     "devices": [],
    #     "community": community,
    #     "prod_profile" : prod_profile, 
    #     "socio" : [1, 0, 0, 1], 
    #     "id" : 1
    #     }, 
    # "all_devices": {
    #     "name": "all_test",
    #     "devices": [],
    #     "community": community,
    #     "prod_profile" : prod_profile, 
    #     "socio" : [1, 1, 1, 1], 
    #     "id" : 1
    # },
    }

member_options = {
    "calc_ref" : False, 
    "eco" : {
        "cost_grid_buy" : 1000, 
        "cost_grid_sell" : 0,
        "cost_ex" : 0, 
        "cost_PV" : 100, 
        "PV_min" : 0,
        "cost_bat" : 100,
        "bat_min" : 0,
    },
    "enviro" : {
        "carbone_grid" : 15,
        "carbone_commu" : 0.1
    },
    "auto" : {
        "coef_auto" : 1
    },
    "pena" : {
        "coef_pena" : 1
    }, 
    "confort" : {
        "coef_p" : 1, 
        "coef_t" : 1
    },
    "bat_exchange" : True,
}

# Run tests from dictionaries
for case_name, case_params in test_cases.items():
    print(f"{case_name} test")
    device_wash_mach, device_therm, device_EV, device_fixed, device_PV, device_bat = define_devices(wash_mach, therm_load, EV_load, fixed_load, pv_prod, bat_load,options)
    
    if case_name=="wash_machine" : 
        # case_params['devices'] = [device_wash_mach, device_PV]
        case_params['devices'] = [device_wash_mach]
    elif case_name=="thermostat" :
        case_params['devices'] = [device_therm, device_PV]
    elif case_name=="EV" :
        case_params['devices'] = [device_EV, device_PV]
    elif case_name=="bat" : 
        case_params['devices'] = [device_bat, device_PV]
    elif case_name=="all_devices" :
        case_params['devices'] = []
        case_params['devices'].append(device_wash_mach)
        case_params['devices'].append(device_therm)
        # case_params['devices'].append(device_EV)
        case_params['devices'].append(device_PV)
        case_params['devices'].append(device_bat)
    elif case_name=="fixed_profile" :
        case_params['devices'] = [device_fixed, device_PV]

    
    test_member = memb.member(case_params['devices'], 
                              case_params['socio'],  
                              case_params['id'], **member_options)
    # community = comm.community([test_member])
    test_member.build_model(**test_member.kwargs)
    test_member.self_optimize("gurobi")
    device = test_member.devices[0]
    # test_member.mod_member.P_bat.display()
    # test_member.devices[0].mod.bin_0.display()
    # test_member.mod_member.P_grid_minus.display()
    # test_member.mod_member.obj.pprint()
    print(f"{case_name} test solved")
    print(f"""Results : price = {pyo.value(test_member.price)} (investissement : {pyo.value(test_member.price_invest)}, operation : {pyo.value(test_member.price_operation)})
          enviro = {pyo.value(test_member.enviro)}, auto = {pyo.value(test_member.auto)}, confort = {pyo.value(test_member.confort)}""")
    test_member.mod_member.write('member.lp', io_options={'symbolic_solver_labels': True})
    
to_plot = {
    "powers" : {
        "P_grid" : [pyo.value(test_member.P_grid_plus[t]-test_member.P_grid_minus[t]) for t in range(test_member.total_time)],
        "P_bat" : [pyo.value(test_member.P_bat[t]) for t in range(test_member.total_time)],
        # "P_bat_plus" : [pyo.value(test_member.devices[-1].P_plus[t]) for t in range(test_member.total_time)],
        # "P_bat_minus" : [pyo.value(test_member.devices[-1].P_minus[t]) for t in range(test_member.total_time)],
        # "P_bat_cons" : [pyo.value(test_member.devices[-1].Pcons[t]) for t in range(test_member.total_time)],
        "P_cons" : [pyo.value(test_member.P_cons[t]) for t in range(test_member.total_time)], 
        # "P_exchange" : [pyo.value(test_member.P_exchange[t]) for t in range(test_member.total_time)],
        "P_prod" : [pyo.value(test_member.P_prod[t]) for t in range(test_member.total_time)],
    }
}

# to_plot2 = {
#     "powers" : {
#         "E" : [pyo.value(test_member.devices[-1].E[t]) for t in range(test_member.total_time)],   
#     }
# }
    
test_member.plot_power_curves(**to_plot)
# test_member.plot_power_curves(**to_plot2)

#%% Community test 

import commu_opti.community.device as d
import commu_opti.community.community as comm
import commu_opti.community.member as memb

options = {"total_time" : 5, "deltat" : 1, "def_irradiance" : False}

members_dico = {
    "member1" : {
        "devices" : [
            {
                "type" : "fixed", 
                "parameters" : {
                    "power_profile" : [10 for t in range(options["total_time"])]
                }
            }, 
            {
                "type" : "PV", 
                "parameters" : {
                    "irradiance_profile" : [20 for t in range(5)],
                    "surface" : 5,
                    }
                }
        ],
        "socio" : [1, 1, 1, 1],
        "id" : 1
    }, 
    "member2" : {
        "devices" : [
            {
                "type" : "fixed", 
                "parameters" : {
                    "power_profile" : [10 for t in range(options["total_time"])]
                }
            }
        ],
        "socio" : [1, 1, 1, 1],
        "id" : 2
    },
    # "member3" : {
    #     "power_profile" : [0 for t in range(5)], 
    #     "devices" : [
    #         {
    #             "type" : "fixed", 
    #             "parameters" : {
    #                 "power_profile" : [10 for t in range(options["total_time"])]
    #             }
    #         }
    #     ],
    #     "socio" : [1, 1, 1, 1],
    #     "id" : 2
    # }
}

coef_options = {
    "eco" : {
        "cost_grid_buy" : 10, 
        "cost_grid_sell" : -2.5,
        "cost_ex" : 0, 
    },
    "enviro" : {
        "carbone_grid" : 0.5,
        "carbone_commu" : 0.1
    },
    "auto" : {
        "coef_auto" : 1
    },
    "pena" : {
        "coef_pena" : 1
    }
}


members = []
co = None
c = 0
for key in members_dico : 
    m = members_dico[key]
    devices = []
    for device in m["devices"] : 
        devices.append(getattr(d, device["type"])(**device["parameters"], **options))
    member = memb.member(devices, m["socio"], m["id"], calc_ref = False, **options)
    members.append(member)
    c += 1
co = comm.community(members, **options, **coef_options)
# co.build_model()
co.optimize("gurobi")
co.mod.write('commu.lp', io_options={'symbolic_solver_labels': True})

print("Optimization done \n")

# co.calc_gains("gurobi")
# print("Gains calculated \n")

# co.distribute_gains(method="proportional")
# print("Gains distributed proportionaly \n")

# co.distribute_gains(method="equal")
# print("Gains distributed equally \n")

# co.distribute_gains(method="shapley")
# print("Gains distributed with Shapley \n")


to_plot = {
    "powers" : {
        "P_grid" : [pyo.value(co.mod.P_grid_plus[t]+co.mod.P_grid_minus[t]) for t in range(co.total_time)],
        "P_bat" : [pyo.value(co.mod.P_bat[t]) for t in range(co.total_time)],
        "P_cons" : [pyo.value(co.mod.P_cons[t]) for t in range(co.total_time)], 
        "P_exchange" : [pyo.value(co.mod.P_commu_exchange[t]) for t in range(co.total_time)],
    }
}
    
co.plot_power_curves(**to_plot)
        
# to_plot_hex = {
#     "values" : {
#         "gain shapley" : co.members_gains["shapley"],
#         "gain proportional" : co.members_gains["proportional"],
#         "gain equal" : co.members_gains["equal"],
#     },
#     "members" : [f"member {m}" for m in co.members_id],
#     "title" : "Gains distribution comparison"
# }
# co.plot_hexagon(**to_plot_hex)

#%% Test de generate_data.py
from commu_opti.data.generate_data import generate_n_profile
import matplotlib.pyplot as plt

profile = [[0, 8, 1], [8, 16, 0], [16, 24, 1]]

detailed_profile, details = generate_n_profile(5, profile, offset=2, lengths_rate=1.3, lengths_breaks_rate=0.3, detailed= True)

for i, detail in enumerate(details):
    plt.figure()
    plt.step(range(len(detail)), detail, 'b', where='post', label=str(detailed_profile[i]))
    plt.title(f"Profile {i}")
    plt.xlabel("Time")
    plt.ylabel("Presence")
    plt.ylim(-0.5, 1.5)
    plt.legend()
    plt.grid()

plt.show()

#%% Test profil conso generate_data.py
from commu_opti.data.generate_data import generate_n_profile, create_random_agent
from commu_opti.commu_builder import define_devices, define_members, define_community
profile = [[0, 8, 1], [8, 16, 0], [16, 24, 1]]
agent = create_random_agent(profile, forced_devices={"batterie", "PV_generation"})

import os 
import pandas as pd 
import matplotlib.pyplot as plt

if agent.get("PV_generation") : 
    prod_profile = agent["PV_generation"]["parameters"]["production_profile"]
else : 
    prod_profile = [0 for t in range(24)]

param = {"devices" : agent, "device_options" : {"total_time" : 24, "deltat" : 1}, 
         "parameters" : {
            "production_profile" : prod_profile,
            "socio" : [1, 1, 1, 1],
            "id_" : 1, 
            "bat_exchange" : False, 
         }}

# Test first for one device with eache device : 
# for device in agent : 
#     print(f"Testing device {device} \n")
#     param["devices"] = {device : agent[device]}
#     member = define_members([param])[0]
#     member.mod_member.write(f'member_{device}.lp', io_options={'symbolic_solver_labels': True})

member = define_members([param])[0]

member.mod_member.write('member.lp', io_options={'symbolic_solver_labels': True})

member.self_optimize("gurobi")
to_plot = {
    "powers" : {
        "P_grid" : [pyo.value(member.P_grid_plus[t]-member.P_grid_minus[t]) for t in range(member.total_time)],
        "P_bat" : [pyo.value(member.P_bat[t]) for t in range(member.total_time)],
        "P_cons" : [pyo.value(member.P_cons[t]) for t in range(member.total_time)], 
        "P_exchange" : [pyo.value(member.P_exchange[t]) for t in range(member.total_time)],
        "P_prod" : prod_profile, 
    }
}

device_energy = {}
# to_plot["powers"]["total"] = [0 for t in range(member.total_time)]
for d in member.devices : 
    if d.name != "heater" :
    #     to_plot["powers"][f"P_{d.name}"] = [pyo.value(d.mod.Pcons[t]) for t in range(member.total_time)]
        # to_plot["powers"]["total"] = [to_plot["powers"]["total"][t] + pyo.value(d.mod.Pcons[t]) for t in range(member.total_time)]
        device_energy[d.name] = sum([pyo.value(d.mod.Pcons[t]) for t in range(member.total_time)])
    # if d.name == "EV_zoe" :
    #     to_plot["powers"][f"E_{d.name}"] = [pyo.value(d.mod.E[t]) if d.mod.E[t].value else 0 for t in range(member.total_time)]
    
member.plot_power_curves(**to_plot)

data_folder = os.path.join(os.path.dirname(__file__), "../../projet_g3_data")
fridge_file = os.path.join(data_folder, "water_heater_refrigerator.xlsx")
df_fridge = pd.read_excel(fridge_file, sheet_name="Sheet2", parse_dates=["date"])

# time = [k*0.25 for k in range(len(df_fridge))]
# plt.plot(time, df_fridge["power"], label="Real consumer profile")
# plt.legend()

#%% Creattion random community test 

from commu_opti.data.generate_data import generate_n_profile, create_random_agent, detailed_profile
from commu_opti.commu_builder import define_devices, define_members, define_community

profile = [[0, 8, 1], [8, 16, 0], [16, 24, 1]]
profiles = generate_n_profile(15, profile, offset=2, lengths_rate=1.3, lengths_breaks_rate=0.3)

agents = []
prod_profiles = []
for profile in profiles :
    agent = create_random_agent(profile)
    agents.append(agent)
    if agent.get("PV_generation") : 
        prod_profiles.append(agent["PV_generation"]["parameters"]["production_profile"])
    else : 
        prod_profiles.append([0 for t in range(24)])
    
members_params = []
for i, agent in enumerate(agents) :
    param = {"devices" : agent, "device_options" : {"total_time" : 24, "deltat" : 1}, 
             "parameters" : {
                "production_profile" : prod_profiles[i],
                "socio" : [0.1, 0, 0, 1],
                "id_" : i+1, 
                "bat_exchange" : False, 
             }}
    members_params.append(param)
members = define_members(members_params)

for member in members : 
    member.self_optimize("gurobi")
    
    to_plot = {
        "powers" : {
            # "P_grid" : [pyo.value(member.P_grid_plus[t]-member.P_grid_minus[t]) for t in range(member.total_time)],
            "P_prod" : member.P_prod, 
        }
    }
    for d in member.devices : 
        if d.name != "" :
            to_plot["powers"][f"P_{d.name}"] = [pyo.value(d.mod.Pcons[t]) for t in range(member.total_time)]
            # to_plot["powers"]["total"] = [to_plot["powers"]["total"][t] + pyo.value(d.mod.Pcons[t]) for t in range(member.total_time)]
            # device_energy[d.name] = sum([pyo.value(d.mod.Pcons[t]) for t in range(member.total_time)])
    if not member.ref_values == [1, 1, 1 , 1] : 
        plt.figure(member.id)
        to_plot["title"] = f"Member {member.id}"
        member.plot_power_curves(**to_plot)


#%% def save candidate

import json 
import os 
import numpy as np

data_folder = os.path.join(os.path.dirname(__file__), "../../projet_g3_data/candidates")
if not os.path.exists(data_folder) : 
    os.makedirs(data_folder)

def convert_to_serializable(obj):
    if isinstance(obj, np.integer):  # Convert NumPy integers to Python int
        return int(obj)
    if isinstance(obj, np.floating):  # Convert NumPy floats to Python float
        return float(obj)
    if isinstance(obj, np.ndarray):  # Convert NumPy arrays to lists
        return obj.tolist()
    raise TypeError(f"Type {type(obj)} not serializable")


def save_candidate(members_params, name, id_) :
    file_name = f"candidate_{name}.json"
    file_path = os.path.join(data_folder, file_name)
    with open(file_path, 'w') as f:
        json.dump(members_params[id_-1], f, indent=4, default=convert_to_serializable)
        
to_save = [(3, "grosse_conso"), (15, "batterie")]
for i, name in to_save : 
    save_candidate(members_params, name, i)




#%% test generation data V2 : Markov states
from commu_opti.data.generate_data_V2 import generate_profile, generate_building, average_surface, initial_state_probabilities, get_weather_data, profile_to_presence
from commu_opti.data.utils import compute_average_number


build = generate_building()
print("House generated : ", build)

nb_people = 6
states = [f"{k}{j}" for k in range(nb_people+1) for j in range(nb_people+1)]
states = {states[i] : i for i in range(len(states))}
profile = generate_profile(nb_people, False, 1)

presence_profile = profile_to_presence(profile, nb_people)

plt.figure()
plt.plot([presence_profile[k]['awake'] for k in range(len(profile))], '+', label='awake')
plt.plot([presence_profile[k]['asleep'] for k in range(len(profile))], 'o', label='asleep')
plt.plot([presence_profile[k]['away'] for k in range(len(profile))], '_', label='away')
plt.legend()

#%% Test generation data V2 : one_device_allocation
from commu_opti.data.generate_data_V2 import one_device_allocation#, list_devices
from commu_opti.data.devices_jsonpy import list_devices
equipments = {}

print("\nFor 3 people")
nb_people = 3
profile = generate_profile(nb_people, False, 1)
for device in list_devices : 
    print(device)
    equipments[device] = one_device_allocation(list_devices[device], nb_people)
    
# print("\nFor 2 people")
# nb_people = 2
# profile = generate_profile(nb_people, False, 1)
# for device in list_devices : 
#     print(device)
#     equipments[device] = one_device_allocation(list_devices[device], nb_people)
    
    
#%% Test generation data V2 : profiles
from commu_opti.data.generate_data_V2 import profile_to_presence, device_activation_profile, when_to_profile, device_power_profile
import datetime as dt
print("Compute presence profile")

# presence_profile = profile_to_presence(profile, nb_people)
date_start = dt.datetime(2020, 12, 8)
date_end = dt.datetime(2020, 12, 9)
weather_forecast, irradiance_profile = get_weather_data(date_start, date_end)
weather_history, irradiance_history = get_weather_data(date_start, date_end, forecast=False)
weather = {"forecast" : {
    "temperature" : weather_forecast, 
    "irradiance" : irradiance_profile
    },
    "history" : {
        "temperature" : weather_history,
        "irradiance" : irradiance_history
    }
}

deltat = 1
final_result = {}
for device in equipments : 
    if equipments[device]["Number"] != 0 and equipments[device].get("P") != 0 : 
        print(f"\nDevice {device} \n")
        activation_profile, when_profile, presence_profile = device_activation_profile(profile, equipments[device], deltat, nb_people)
        print("Activation profile copmuted")
        args = {
            "activation_profile" : activation_profile,
            "when_profile" : when_profile,
            "presence_profile" : presence_profile,
            "device_name" : device,
            "allocated" : equipments[device],
            "building" : build,
            "nb_people" : nb_people,
            "deltat" : deltat,
            "weather" : weather
            }
        pow_profile = device_power_profile(**args)
        pow_profile["parameters"]["name"] = device
        print("Power profile computed")
        
        final_result[device] = {"power_profile" : pow_profile, "args" : args}
    
#%% define member using these profiles
from commu_opti.commu_builder import define_members


devices = {device : final_result[device]["power_profile"] for device in list(final_result.keys())[:]}

member_param = {
    'socio': [1, 1, 0, 1],
    'id_': 0,
}
param = {"devices" : devices, "device_options" : {"total_time" : 24, "deltat" : 1}, 
                    "parameters" : member_param}
list_members_params = [param]
members = define_members(list_members_params)
m = members[0]
m.self_optimize('gurobi')
# Need to verify at the end if we come to a coherent average value when generating a lot of profiles.