
from ..community import np, dt
from . import pyo
from ..commu_builder import define_members, define_community
from ..generate_device_infos import separate_horizon_futur
from ..data.generate_data_V2 import get_price_data
from pyomo.contrib.iis import write_iis
import time


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

    

    community = define_community(members, **param_commu, **price_options)
    new_weather = [weather_history[0]] + weather_forecast[1:horizon]
    new_irradiance = [irradiance_history[0]] + irradiance_forecast[1:horizon]
    new_price_buy = price_options["eco"]["cost_grid_buy"][:horizon]
    new_price_sell = price_options["eco"]["cost_grid_sell"][:horizon]
    new_prices = {"price_buy" : new_price_buy, "price_sell" : new_price_sell}
    
    for i in community.current_members_id : 
        m = community.members[i]
        # m.rolling_horizon_update(new_weather, new_irradiance, new_prices, general_only=False)
        m.reset_horizon(new_weather, new_irradiance, new_prices)
    
    def roll(community, horizon, total_time, method) : 
        t0 = time.time()
        for t in range(kwargs.get("until", total_time - horizon)) :
            print("Starting optimization for time step", t)
            if method == "admm" : 
                community.optimize_admm("gurobi", **community.kwargs)
            elif method == "selves" :
                # community.optimize_selves("gurobi", **community.kwargs)
                community.mod.active_members.store_values({i : 0 for i in community.member_set})
                community.optimize("gurobi")
            else : 
                community.optimize("gurobi")
            if t == 0 : 
                # print(community.mod.active_members.extract_values())
                community.aggregate_distributed_information()
                without_rolling = community.results.copy()
                # print(community.ref_values)
            print("\nOptimization finished !", t)
            
            i = 0
            irradiance_t = irradiance_history[t+1]
            new_irradiance = [irradiance_t] + irradiance_forecast[t+2:t+1+horizon]
            weather_t = weather_history[t]
            new_weather = [weather_t] + weather_forecast[t+1:t+horizon]
            new_price_buy = price_options["eco"]["cost_grid_buy"][t+1:t+1+horizon]
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
        t1 = time.time()
        print(f"Rolling horizon optimization took {t1-t0:.2f} seconds.")
        return with_rolling, without_rolling
    
    method = community.kwargs.get("method", "centralized")
    if kwargs.get("optimize_selves", False) :
        method = "selves"
    print("method",method)
    with_rolling, without_rolling = roll(community, horizon, total_time, method)
    
    if kwargs.get("compare_selves", True) : 
        old_weather = [weather_history[0]] + weather_forecast[1:horizon]
        old_irradiance = [irradiance_history[0]] + irradiance_forecast[1:horizon]
        old_price_buy = price_options["eco"]["cost_grid_buy"][:horizon]
        old_price_sell = price_options["eco"]["cost_grid_sell"][:horizon]
        old_prices = {"price_buy" : old_price_buy, "price_sell" : old_price_sell}
        for m in community.members :
            m.reset_horizon(old_weather, old_irradiance, old_prices)
        
        community.update_model(custom_active_id=[]) # Remove all active_members in the constraints => no exchange between members
        if method=="admm" : 
            for m in community.members : 
                m.mod.active_members.store_values({i : 0 for i in m.member_set})
        
        with_rolling_selves, without_rolling_selves = roll(community, horizon, total_time, method)
        return with_rolling, without_rolling, with_rolling_selves, without_rolling_selves, {"community" : community}
    
    if debug : 
        return with_rolling, without_rolling, {"community" : community}
    return with_rolling, without_rolling

