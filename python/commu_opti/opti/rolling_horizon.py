
from ..community import np, dt
from . import pyo
from ..commu_builder import define_members, define_community
from ..generate_device_infos import separate_horizon_futur
from ..data.generate_data_V2 import get_price_data
from pyomo.contrib.iis import write_iis


def rolling_horizon_optimization(params_member, param_commu, price_options, **kwargs) : 
    total_time = kwargs.get("total_time", 24)
    horizon = kwargs.get("horizon", 24)
    deltat = kwargs.get("deltat", 1)
    date = kwargs.get("date", dt.datetime.now())
    debug = kwargs.get("debug", False)
    nb_of_days = int(total_time/deltat/24)
    n = len(params_member)
    irradiance_forecast = kwargs.get("irradiance_forecast", [0 for k in range(total_time)])
    irradiance_history = kwargs.get("irradiance_history", [0 for k in range(total_time)])
    
    weather_forecast = kwargs.get("weather_forecast", [0 for k in range(total_time)])
    weather_history = kwargs.get("weather_history", [0 for k in range(total_time)])
    
    if not kwargs.get("skip_params", False) : 
    
        for param in params_member : 
            param["device_options"] = {"total_time" : total_time, "deltat" : deltat}

            param, devices_futur = separate_horizon_futur(param, horizon, deltat=deltat)
            param["parameters"]["time_window"] = [date, date + dt.timedelta(days=nb_of_days)]
            param["parameters"]["horizon"] = horizon
            param["parameters"]["devices_futur"] = devices_futur
            if "PV" in param["devices"] : 
                param["devices"]["PV"]["parameters"]["irradiance_profile"] = [irradiance_history[0]] + irradiance_forecast[1:horizon]

    
    members = define_members(params_member)

    new_weather = [20 for k in range(horizon)]

    community = define_community(members, **param_commu, **price_options)
    new_irradiance=[]
    for t in range(kwargs.get("until", total_time - horizon)) :
        print("Starting optimization for time step", t)
        if community.kwargs["method"] == "admm" : 
            community.optimize_admm("gurobi", **community.kwargs)
        elif community.kwargs["method"] == "selves" : 
            community.optimize_selves("gurobi", **community.kwargs)
        else : 
            community.optimize("gurobi")
        if t == 0 : 
            community.aggregate_distributed_information()
            without_rolling = community.results.copy()
            print(community.ref_values)
        print("\nOptimization finished !", t)
        
        i = 0
        # d = community.members[0].devices[0]
        # pv = community.members[0].devices[1]
        # while i < 24 and pyo.value(d.mod.bin_t0[0, i])*d.mod.available_time_set[0, i].value != 1:
        #     i += 1

        # print("bin_t0", i, [pyo.value(d.mod.bin_t0[0, i]) for i in range(24)])
        # print("P_cons", [pyo.value(d.mod.Pcons[k]) for k in range(24)])
        # print("irradiance", [pyo.value(pv.mod.Pcons[k]) for k in range(24)])
        # print("price", pyo.value(community.members[0].price), pyo.value(community.members[0].mod_member.obj_expr))
        # print("available_time", [d.mod.available_time_set[0, t].value for t in range(24)])
        # print("used_tim", d.mod.used_time.extract_values())
        
        # print("E", [pyo.value(d.mod.E[k]) for k in range(24)])
        # print("Pcons", [pyo.value(d.mod.Pcons[k]) for k in range(24)])
        # print("E_return", [pyo.value(d.mod.E_return[k]) for k in range(24)])
        # print("E_min_t", [pyo.value(d.mod.E_min_t[k]) for k in range(24)])
        # print("new_irradiance1", new_irradiance)
        irradiance_t = irradiance_history[t+1]
        new_irradiance = [irradiance_t] + irradiance_forecast[t+2:t+1+horizon]
        # print("new_irradiance2", new_irradiance)
        weather_t = weather_history[t]
        new_weather = [weather_t] + weather_forecast[t+1:t+horizon]
        new_price_buy = price_options["eco"]["cost_grid_buy"][t+1:t+1+horizon]
        print(len(new_price_buy), len(price_options["eco"]["cost_grid_buy"]))
        new_price_sell = price_options["eco"]["cost_grid_sell"][t+1:t+1+horizon]
        new_prices = {"price_buy" : new_price_buy, "price_sell" : new_price_sell}

        for i in community.current_members_id : 
            m = community.members[i]
            m.keep_in_memory()
            m.rolling_horizon_update(new_weather, new_irradiance, new_prices)

    if kwargs.get("until", total_time - horizon) > 0 : 
        for i in community.current_members_id : 
            m = community.members[i]
            m.objectif_from_memory()
        community.aggregate_distributed_information(from_memory=True)
        with_rolling = community.results.copy()
    else : 
        with_rolling = None
        without_rolling = None
    
    if debug : 
        return with_rolling, without_rolling, {"community" : community}
    return with_rolling, without_rolling