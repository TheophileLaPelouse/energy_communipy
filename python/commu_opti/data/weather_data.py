from pvgis_api import PVGISClient
import requests
import pandas as pd
import os

#%% parameters

# We choose 5 differents location in France and each time one in the city, one in the countryside 
locations = {
    "Lille" : (50.63, 3.06),
    "Lille_countryside" : (50.63, 2.5),
    "Lyon" : (45.76, 4.83),
    "Lyon_countryside" : (45.76, 3.8),
    "Marseille" : (43.3, 5.4),
    "Marseille_countryside" : (43.4, 5.54),
    "Toulouse" : (43.6, 1.44), 
    "Toulouse_countryside" : (43.5, 1.14),
    "Nates" : (47.22, -1.55),
    "Nates_countryside" : (47.22, -1.9),
}

year = 2020


#%% Open meteo data

folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather_data")
os.makedirs(folder, exist_ok=True)

def get_weather_data(lat, lon, year, url, name="weather_forecast") :
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
    
    res = requests.get(url, params=params).json()
    df = pd.DataFrame(res['hourly'])
    file = os.path.join(folder, f"{name}_{year}_{lat}_{lon}.csv")
    df.to_csv(file, index=False)
    
for loc in locations : 
    lat, lon = locations[loc]
    get_weather_data(lat, lon, year, url="https://historical-forecast-api.open-meteo.com/v1/forecast", name="weather_forecast")
    get_weather_data(lat, lon, year, url="https://archive-api.open-meteo.com/v1/archive", name="weather_archive")
    
#%% Pvgis 
client = PVGISClient()

res_pvgis = client.hourly_radiation(
    lat=45.0, lon=8.0,
)

#%%

format_= "%Y%M%d:%H%m"
df = pd.DataFrame()
n_pvgis = len(res_pvgis["outputs"]["hourly"])
irr = [res_pvgis["outputs"]["hourly"][k]['G(i)'] for k in range(n_pvgis)]
time = pd.to_datetime([res_pvgis["outputs"]["hourly"][k]['time'] for k in range(n_pvgis)], format=format_)

df["time"] = time
df["irradiance"] = irr
file = os.path.join(folder, f"irradiance_{lat}_{lon}.csv")
df.to_csv(file, index=False)


#%%
df = pd.DataFrame(res_forecast['minutely_15'])