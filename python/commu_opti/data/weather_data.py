from pvgis_api import PVGISClient
import requests
import pandas as pd


#%% parameters
lat=45
lon = 8
year = 2020

#%% Pvgis 
client = PVGISClient()

res_pvgis = client.hourly_radiation(
    lat=45.0, lon=8.0,
)

#%% open meteo historical forecast


url = "https://historical-forecast-api.open-meteo.com/v1/forecast"

params = {
    "latitude": lat,
    "longitude": lon,   
    "start_date": f"{year}-01-01",
    "end_date": f"{year}-12-31",
    "hourly": [ # Possible toute les 15 minutes potentiellement
        "temperature_2m", # °C
        "wind_speed_10m", # km/h
        "shortwave_radiation" # W/m2
    ],
    "timezone": "UTC"
}

res_forecast = requests.get(url, params=params).json()

df = pd.DataFrame(res_forecast['hourly'])
df.to_csv(f"weather_forecast_{year}_{lat}_{lon}.csv", index=False)

#%% open meteo historical data


url = "https://archive-api.open-meteo.com/v1/forecast"

params = {
    "latitude": lat,
    "longitude": lon,   
    "start_date": f"{year}-01-01",
    "end_date": f"{year}-12-31",
    "hourly": [
        "temperature_2m",
        "wind_speed_10m",
        "shortwave_radiation"
    ],
    "timezone": "UTC"
}

res_history = requests.get(url, params=params).json()
df = pd.DataFrame(res_forecast['hourly'])
df.to_csv(f"weather_history_{year}_{lat}_{lon}.csv", index=False)


#%%

format_= "%Y%M%d:%H%m"
df = pd.DataFrame()
n_pvgis = len(res_pvgis["outputs"]["hourly"])
irr = [res_pvgis["outputs"]["hourly"][k]['G(i)'] for k in range(n_pvgis)]
time = pd.to_datetime([res_pvgis["outputs"]["hourly"][k]['time'] for k in range(n_pvgis)], format=format_)

df["time"] = time
df["irradiance"] = irr
df.to_csv(f"irradiance_{lat}_{lon}.csv", index=False)


#%%
df = pd.DataFrame(res_forecast['minutely_15'])