#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  1 08:42:55 2026

@author: theophilemounier
"""

import matplotlib.pyplot as plt
import os 


#%% mi-stage presentation

presence = [1, 1, 1, 1, 1, 1, 2, 2, 0, 0, 2, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 1, 1]

hoven = [0, 0, 0, 0, 0, 0, 0.1, 0.1, 0.1, 0.2, 0.3, 0.4, 0.4, 0.2, 0.1, 0.1, 0.2, 0.3, 0.2, 0.1, 0, 0, 0, 0]

usage_proba = [hoven[k]*(presence[k]==2) for k in range(24)]


plt.figure()
plt.plot(range(24), presence, 'o')
plt.title('Presence profile of one person during a day')
plt.yticks([0, 1, 2], ['away', 'asleep', 'awake'])
plt.xlabel('Hour of the day')
plt.ylabel('Presence state')
plt.savefig(os.path.join('..', 'typst', 'mi_stage_data', 'presentation', 'assets', 'presence_profile.png'), dpi=300)

plt.figure()
plt.plot(range(24), hoven, '+--')
plt.title("Probability of using the hoven for one awake person during a day")
plt.xlabel('Hour of the day')
plt.ylabel('Probability of using the hoven')
plt.savefig(os.path.join('..', 'typst', 'mi_stage_data', 'presentation', 'assets', 'hoven_probability.png'), dpi=300)

plt.figure()
plt.plot(range(24), usage_proba, '+--')
plt.title("Probability of using the hoven during a day")
plt.xlabel('Hour of the day')
plt.ylabel('Probability of using the hoven')
plt.savefig(os.path.join('..', 'typst', 'mi_stage_data', 'presentation', 'assets', 'usage_probability.png'), dpi=300)