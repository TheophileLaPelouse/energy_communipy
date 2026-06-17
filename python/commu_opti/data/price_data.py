#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 16 15:29:32 2026

@author: theophilemounier
"""

import pandas as pd
import matplotlib.pyplot as plt
import datetime as dt
import os

csv_path="/Users/theophilemounier/Documents/Stage_these/Data/price_spot_france/day_ahead_price_FR_2021-01-01_2026-01-01.csv"

df = pd.read_csv(csv_path, sep=',', parse_dates=["ts_utc"])

df.columns = ['date', 'price']
file = "day_ahead_price_FR_2021-01-01_2026-01-01.csv"
df.to_csv(os.path.join(os.path.dirname(__file__), file))

# date_start = pd.Timestamp(dt.datetime(year=2022, month=5, day=15), tz='UTC')

# date_end = pd.Timestamp(dt.datetime(year=2022, month=5, day=16), tz='UTC')

# day = df[(df['date'] > date_start) & (df['date'] < date_end)]

