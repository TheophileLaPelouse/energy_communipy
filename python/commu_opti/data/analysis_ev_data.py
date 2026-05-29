import pandas as pd 
import numpy as np
import matplotlib.pyplot as plt
import os
import json


eta = 0.88


csv_path = "/Users/theophilemounier/Documents/Stage_these/Data/EV_sorensen/Dataset 1_EV charging reports.csv"
df = pd.read_csv(csv_path, sep=';', parse_dates=['Start_plugin', 'End_plugout'], dayfirst=True, decimal=',')

# Drop rows with NaN in important columns to avoid errors downstream
df.dropna(subset=['User_ID', 'User_type', 'Garage_ID', 'El_kWh', 'Duration_hours', 'Start_plugin', 'End_plugout'], inplace=True)

users = set()

for ids in df['User_ID'][df["User_type"] == "Private"] : 
    users.add(ids)
    

# Pour chaque user, on récupère garage maison ou pas, nb kwh de charge, temps de charge.

dico_users = {user: {"home" : [], "E" : [], "time" : [], "start" : [], "end" : []} for user in users}


for k in df.index : 
    user = df["User_ID"][k]
    if user in dico_users : 
        garage = df["Garage_ID"][k]
        if user.startswith(garage) : 
            dico_users[user]["home"].append(True)
        else : 
            dico_users[user]["home"].append(False)
            
        dico_users[user]["E"].append(df["El_kWh"][k])
        dico_users[user]["time"].append((df["Duration_hours"][k]))
        dico_users[user]["start"].append((df["Start_plugin"][k]))
        dico_users[user]["end"].append((df["End_plugout"][k]))
        
        
for user, val in dico_users.items() : 
    val["Cap"] = max(val["E"])*eta
    average_time = sum(val["time"])/len(val["time"])
    variance_time = sum((t - average_time)**2 for t in val["time"])/len(val["time"])
    sigma_time = variance_time**0.5
    val["average_time"] = average_time
    val["variance_time"] = sigma_time
    val["max_power"] = max(val["E"][t]/val["time"][t] for t in range(len(val["E"])))
    
    
def iterate_users(user, val) : 
    nmax = len(val["E"])
    t0 = 0
    n = 0
    
    Loss = 0
    Cap = val["Cap"]
    time_not_home = []
    energy_not_home = []
    hours_not_home = []
    
    t_full_charge = Cap/val["max_power"]
    # print(t_full_charge)
    while t0 < nmax : 
        # Search for each two point at full charge
        # Full charge is defined as less power for charging than 90% of max power or more than 4 hours of charge
        # print("\n")
        
        charges = []
        start = []
        homes = []
        end = []
        sessions = []
        while t0 < nmax and (val['E'][t0]/val['time'][t0] >= val["max_power"]*0.9 and val['time'][t0] <= t_full_charge*0.5 and val['home'][t0]) :
            n += 1
            t0 += 1
        # print('t0', t0)
        if t0 < nmax : 
            end.append(val['end'][t0]) # We want the first end time too
            n += 1
            
            while n < nmax and (val['E'][n]/val['time'][n] >= val["max_power"]*0.9 or val['time'][n] <= t_full_charge*0.5 and val['home'][n]) : 
                charges.append(val['E'][n])
                start.append(val['start'][n])
                homes.append(val['home'][n])
                end.append(val['end'][n])
                n += 1
            if n < nmax : 
                charges.append(val['E'][n])
                start.append(val['start'][n])
                homes.append(val['home'][n])
                end.append(val['end'][n])
            # print("n", n)
            # print("end", end)
            # print("start", start)
            if n < nmax :
                Loss = sum(charges) # As we supposed that the cycle begin and end at full charge 
                # print("Loss", Loss)
                s = 0
                deltat = end[0]-end[0] # Just to initialize deltat
                # Compute power and time when not at home
                # print("n, t0", n, t0)
                for i in range(n-t0) : 
                    # print('i', i)
                    if not homes[i] : 
                        s += charges[i]
                        deltat += end[i+1] - end[i] 
                        sessions.append((end[i], end[i+1]))
                    if homes[i] : 
                        deltat += start[i] - end[i]
                        sessions.append((end[i], start[i]))
                hours_not_home.append(sessions)
                time_not_home.append(deltat.total_seconds()/3600)
                energy_not_home.append(s - Loss)
            t0 = n
            
    val["time_not_home"] = time_not_home
    val["hours_not_home"] = hours_not_home
    val["energy_not_home"] = energy_not_home
    
    return 

user = "AsO10-3"
iterate_users(user, dico_users[user])

for user, val in dico_users.items() : 
    iterate_users(user, val)
    
#%% plot presence profile of EV for each user
plt.figure()
for user in dico_users :
    proba = [0 for k in range(24)]
    for sessions in dico_users[user]['hours_not_home'] : 
        for session in sessions : 
            start = session[0].hour
            end = start + (session[1] - session[0]).total_seconds()/3600
            print(user, session)
            if not (np.isnan(start) or np.isnan(end)) : 
                end = round(end)
                for h in range(start, end+1) :
                    proba[h%24] += 1
    if sum(proba) != 0 : 
        proba = [p/sum(proba) for p in proba]
        plt.plot(proba, label=user)
plt.legend()
plt.xlabel('Hour of the day')
plt.ylabel('Probability of not being at home')
plt.title('Presence profile of EV for each user')

#%% Compute average time of session not at home and variance for each user

travels = []
for user in dico_users :
    average = 0
    variance = 0
    c = 0
    for sessions in dico_users[user]['hours_not_home'] :
        for session in sessions : 
            length = (session[1] - session[0]).total_seconds()/3600
            if 0.2 <= length <= 18 :
                average+=length
                c+=1
    if c > 0 :
        average = average/c
        
    for k in range(len(dico_users[user]['hours_not_home'])) :
        sessions = dico_users[user]['hours_not_home'][k]
        for session in sessions : 
            length = (session[1] - session[0]).total_seconds()/3600
            if 0.2 <= length <= 18 : 
                variance += (length - average)**2
                travels.append({
                "user" : user,
                "start" : session[0],
                "end" : session[1],
                "length" : length,
                "power" : dico_users[user]['energy_not_home'][k]/dico_users[user]['time_not_home'][k] if dico_users[user]['time_not_home'][k] > 0 else 0, 
                "capacity" : dico_users[user]['Cap'], 
                "user" : user
                })
    if c > 0 :
        variance = variance/c
    
    dico_users[user]['average_time_not_home'] = average
    dico_users[user]['variance_time_not_home'] = variance**0.5
    dico_users[user]['usuable_data'] = c
    
    
# Number of cars in each capacity range
capa_range = [0 for k in range(0, 100, 10)]
for user in dico_users : 
    capa = dico_users[user]['Cap']
    index = round(capa/10)
    if index < len(capa_range) : 
        capa_range[index] += 1
        
        
travels = pd.DataFrame(travels)

# Average travel count per day depending on the capacity range of the cars

# Create capacity class (0-5, 5-15, 15-25, etc.)
def capacity_class(capa):
    return(round(capa/10))

travels['capacity_class'] = travels['capacity'].apply(capacity_class)
capacities = travels.groupby(['capacity_class', 'user'])

travels_day = travels.groupby([travels['start'].dt.date, 'user'])

# Probability of having a car of capacity class X and conditional P(Y|X)
# X: capacity_class (rounded capacity/10); Y: average travels per day per user (rounded)
travels_per_day = travels_day.size().rename('travels_per_day').reset_index()
avg_travels_per_user = travels_per_day.groupby('user')['travels_per_day'].mean().rename('avg_travels_per_day')

user_capacity = travels.groupby('user')['capacity_class'].first().rename('capacity_class')
user_cap_trav = pd.concat([user_capacity, avg_travels_per_user], axis=1).dropna().reset_index()
cap_trav = (
    user_cap_trav
    .groupby('capacity_class')['avg_travels_per_day']
    .agg(avg_travels_per_day='mean', var_travels_per_day='var')
    .reset_index()
)


# Probability of having Y length depending on X the number of travels

travels_per_day_per_user = travels_per_day.groupby('travels_per_day').size().rename("count").reset_index()
len_count = travels_day['length'].agg(travels='count', length='mean')

total_count = travels_per_day_per_user['count'].sum()
trav = travels_per_day_per_user['count']/total_count

trav_len = (
    len_count
    .groupby('travels')['length']
    .agg(avg_len='mean', var_len='var')
    .reset_index()
)

# Probability of having Y length depending on X the capacity
# Group travel lengths by capacity class: for each capacity_class compute avg and var of travel length
len_by_capacity = (
    travels
    .groupby('capacity_class')['length']
    .agg(avg_len='mean', var_len='var', count='count')
    .reset_index()
)

# No correlation observed for this.

# Probability of having X power consumed depending on Y the capacity and Z the length of the travel

# Group power by capacity class and travel length class (rounded to nearest hour)
travels_power = travels.copy()
travels_power['length_class'] = travels_power['length'].round().astype(int)

power_cap_len = (
    travels_power
    .groupby(['capacity_class', 'length_class'])['power']
    .agg(avg_power='mean', var_power='var', count='count')
    .reset_index()
)

# Marginal statistics (optional helpers)
power_by_capacity = (
    travels_power
    .groupby('capacity_class')['power']
    .agg(avg_power='mean', var_power='var', count='count')
    .reset_index()
)

power_by_length = (
    travels_power
    .groupby('length_class')['power']
    .agg(avg_power='mean', var_power='var', count='count')
    .reset_index()
)



# So main correlation observed is the obvious one between number of travel a day and length of these travels
# and the one between the power and the length and the capactity of the car that is more complex

# Checking number of day used 

dates = travels.groupby(['user', 'capacity_class'])['start'].agg(first='first', last='last', days_with_travel=lambda x: x.dt.date.nunique())
dates["duration"] = (dates['last'] - dates['first']).dt.days + 1
dates["prop_days_used"] = dates['days_with_travel']/dates['duration']
dates.reset_index()
cap_used = dates.groupby('capacity_class')['prop_days_used'].agg(avg='mean', var='var').reset_index()

#%% Plot number of cars in each capacity range
plt.figure()
ranges = [f"{k-5}-{k+5}" for k in range(0, 70, 10)]
plt.bar(ranges, capa_range)
plt.xlabel('Capacity range (kWh)')
plt.ylabel('Number of cars')
plt.title('Number of cars in each capacity range')

average_proba_trav = cap_trav['avg_travels_per_day'].mean() # Does not depend much on the size of the car 

#%% Plot number of travels per day depending on the capacity range of the cars
plt.figure()
plt.bar(ranges, cap_trav['avg_travels_per_day'].to_numpy())
plt.xlabel('Capacity range (kWh)')
plt.ylabel('Average number of travels per day')
plt.title('Average number of travels per day depending on the capacity range of the cars')

average_proba_trav = cap_trav['avg_travels_per_day'].mean() # Does not depend much on the size of the car 

#%% Plot average travel length depending on the number of travels per day
plt.figure()
plt.bar(trav_len['travels'], trav_len['avg_len'])
plt.xlabel('Number of travels per day')
plt.ylabel('Average travel length (hours)')
plt.title('Average travel length depending on the number of travels per day')
        
#%% Save travel length statistic 
stats_path = os.path.join(os.path.dirname(__file__), "ev_travel_statistics.json")

json_car = {
    "travels_length" : {
        key : (avg, var**(1/2)) for key, avg, var in 
        zip(trav_len['travels'], trav_len['avg_len'], trav_len['var_len'])
    },
    "power_by_capacity_length" : {
        cap : {length : (avg, var**(1/2)) for length, avg, var in 
        zip(power_cap_len['length_class'], power_cap_len['avg_power'], power_cap_len['var_power'])
        }
        for cap in power_cap_len['capacity_class']
    }, 
    "travel_proba" : {
        key : (avg, var**(1/2)) for key, avg, var in 
        zip(cap_used['capacity_class'], cap_used['avg'], cap_used['var'])
    }, 
    "nb_travels_proba" : {
        key : val for key, val in
        zip(travels_per_day_per_user['travels_per_day'], trav)        
    }
}
    
    
with open(stats_path, 'w') as f:
    json.dump(json_car, f, indent=4)
    
    
#%% Plot energy not at home for each user
plt.figure()
c = 0
for user in dico_users : 
    c += 1
    energy_per_session = sum(dico_users[user]['energy_not_home'])/sum(dico_users[user]['time_not_home']) # Energy stored per hour in kwh
    print(user)
    print("E", sum(dico_users[user]['energy_not_home']) >= 0, sum(dico_users[user]['energy_not_home']))
    print("T", sum(dico_users[user]['time_not_home']) >= 0)
    plt.bar(c, energy_per_session, label=user)
    # plt.bar(user, sum(dico_users[user]['energy_not_home']), label=user)
# plt.legend()
plt.grid(axis='y')
plt.xlabel('User')
plt.ylabel('Energy not at home (kWh)')
plt.title('Energy not at home for each user')


#%% Statistic 

# On veut le nombre de trajet par jour en fonction de la capacité de la batterie, leur durée et leur énergie consommée.




#%%
for user in dico_users : 
    print(user, len(dico_users[user]['energy_not_home']), all(dico_users[user]['home']),dico_users[user]['end'][-1]- dico_users[user]['start'][0])