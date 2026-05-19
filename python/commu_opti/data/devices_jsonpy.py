
# Present state possibilities => "awake", "asleep", "away" 
# those will be tranlated later to 2 numbers : number of people at home and number of people awake.
# Source principale : https://librairie.ademe.fr/energies/6931-8605-l-equipement-des-menages-francais-en-appareils-electrodomestiques.html

"""

This file create a json with the characteristics of the different devices.

When E_types is given, the power can be translated threw a formula in utils.py.

for the key when here is how it is done : 

    - presence_state : the device is used only if the presence state is in the list
    - proba_t : if given, gives the probability of using it at each time t corresponding to the possible time
    - proba : if given, gives the probability of using it once during the day, if no probability is given, then it always 1.
    - where : if given, gives the room where the inhabitant needs to be for the device to be used (for the lights).
    - time : gives the time slots when the device can be used in the format [t0, tend, probability].

deviation is parameter to force the relative deviation of the power distribution associated to the device.    


Heating system, climatisation and water heater are modelled in a separate way 

Possible fields : 
'C_proba' -> heating system capacitance probability, in MJ/K

'DPE_proba' -> heating system DPE probability

'E_types' -> Energic reference of the different types of the device, used for calculating the power 

'P_popu' -> power of the device depending on the number of people in the household

'P_types' -> power of the different types of the device, used for calculating the power

'R_DPE' -> heating system thermal resistance depending on the DPE, in m2.K/W

'T_activation' -> Temperature of activation for the climatisation, in °C

'T_minus' -> Temperature difference between the inside and the outside for the climatisation, in °C

'T_needed_asleep' -> Temperature needed for the heating system when the inhabitants are asleep, in °C

'T_needed_awake' -> Temperature needed for the heating system when the inhabitants are awake, in °C

'V_popu' -> volume of the device depending on the number of people in the household

'cap_popu' -> capacity of the device depending on the number of people in the household

'coef_R' -> coefficient for the thermal resistance R1 and R2 of the heating system

'cycle_length' -> duration of the cycle of the device, in h

'deviation' -> deviation for the power of the device, in proportion

'energy_needed' -> energy needed for the device, in Wh

'increase_power' -> increase of the power of the device in case of a variation of the temperature, in proportion per m2

'nb_proba' -> probability of having a certain number of devices, depending on the number of people in the household

'net_deviation' -> deviation for the net power of the device, in °C for the heating system and climatisation

'power' -> power of the device, in W

'proba' -> probability of using the device during the day

'time_between_cycles' -> time between 2 cycles of the device, in h

'types_proba'-> probability of having a certain type of device, used for calculating the power when E_types or P_types is given 

'when' -> gives the conditions for using the device as mentionned above

"""

list_devices = {
    "refrigerator" : {
        "proba" : 1,
        # "types" : {"A", "B", "C", "D", "E", "F", "G"},
        "nb_proba" : {1 : 0.8, 2 : 0.17, 3 : 0.03},
        "types_proba" : {"A" : 0.4, "B" : 0.04, "C" : 0.04, "D" : 0.05, "E" : 0.02, "F": 0.02, "G" : 0.03},
        "E_types" : {"A" : 40, "B" : 50, "C" : 63, "D" : 79, "E" : 100, "F" : 125, "G" : 160}, # IEE %
        
        "V_popu" : {1 : 200, 2 : 240, 3 : 242, 4 : 265, 5 : 280, 6 : 300}, # L
        "cycle_length" : 22/60, # h
        "time_between_cycles" : 1.5, # h
        "increase_power" : 1/(18-6), # /°C to multiply by power (linear model but should be fine for small variations)
        "when" : {"presence_state" : ["awake", "asleep", "away"]},
    },
    "TV" : {
        "proba" : 0.92,
        # "types" : {"LCD_LED", "LCD", "OLED", "Plasma", "Cathodique"},
        "nb_proba" : {1 : 0.57, 2 : 0.25, 3: 0.07, 4: 0.02, 5 : 0.01, 0: 0.08},
        "types_proba" : {"LCD_LED" : 0.43, "LCD" : 0.35, "OLED" : 0.12, "Plasma" : 0.08, "Cathodique" : 0.025},
        # "types_proba_autres" : {"LCD_LED" : 0.37, "LCD" : 0.44, "OLED" : 0.05, "Plasma" : 0.07, "Cathodique" : 0.04},
        "P_types" : {"OLED" : 100, "LCD_LED" : 90, "LCD" : 120, "Plasma" : 400, "Cathodique" : 100}, #W
        # Source https://www.kelwatt.fr/guide/conso/television
        "when" : {"presence_state" : ["awake"], "proba_t" : 0.7}
    },
    "congelateur" : {
        "proba" : 0.445,
        "nb_proba" : {1 : 0.4, 2 : 0.05, 3 : 0.01},
        # "types" : {"A", "B", "C", "D", "E", "F", "G"},
        "types_proba" : {"A" : 0.4, "B" : 0.05, "C" : 0.05, "D" : 0.06, "E" : 0.04},
        "E_types" : {"A" : 40, "B" : 50, "C" : 63, "D" : 79, "E" : 100, "F" : 125, "G" : 160}, # EEI % 
        "V_popu" : {1 : 160, 2 : 220, 3 : 220, 4 : 220, 5 : 230, 6 : 230}, # L
        "cycle_length" : 22/60, # h arbitrairement choisi comme pour le frigo
        "time_between_cycles" : 3, # h arbitrairerement choisi 2 fois plus grand que le frigo.
        "when" : {"presence_state" : ["awake", "asleep", "away"]},
    },
    "lighting" : {
        "proba" : 1, 
        # "nb" : 0.12, #/m2
        # "types" : {"LED", "Fluo", "Incandescence", "halogene"},
        "types_proba" : {"LED" : 0.5, "Fluo" : 0.14, "Incandescence" : 0.13, "halogene" : 0.23}, 
        # Hypothèse : 300 lux moyen dans chaque pièce, lumen = lux * surface
        "P_types" : {"LED" : 1/140*300, "Fluo" : 1/70*300, "Incandescence" : 1/12*300, "halogene" : 1/22*300}, # W/surface 
        # source : https://fr.wikipedia.org/wiki/Efficacit%C3%A9_lumineuse_d'une_source
        "when" : {"presence_state" : ["awake"], "where" : "room", "moment" : ["night"]}
    },
    "plaque_electrique" : {
        "proba" : 0.91*0.52, # 0.5 because not everyone has an electric stove
        "power" : 2.4*1000, # W assumption taking 1200 Wh/cooking
        "cycle_length" : 0.5, # h
        "when" : {"presence_state" : ["awake"], "where" : "kitchen", "time" : [[12, 14, 0.5], [18, 22, 0.5]]}
    },
    "hoven" : {
        "proba" : 0.76*0.81,
        # "types" : {"A++", "A+", "A", "B", "C", "D"}, 
        "E_types" : {
            'A++ 50L': 380.0,
            'A+ 50L': 532.0,
            'A 50L': 684.0,
            'B 50L': 874,
            'C 50L': 1102.0,
            'D 50L': 1368.0,
            'A++ 70L': 422,
            'A+ 70L': 590.8,
            'A 70L': 759.6,
            'B 70L': 970.6,
            'C 70L': 1223.8,
            'D 70L': 1519.2}, #Wh/cycle
        "types_proba" : {'A++ 50L': 0.112, 'A+ 50L': 0.112, 'A 50L': 0.056, 'B 50L': 0.028, 'C 50L': 0.014, 'D 50L': 0.0056,
            'A++ 70L': 0.088, 'A+ 70L': 0.088, 'A 70L': 0.044, 'B 70L': 0.022, 'C 70L': 0.011, 'D 70L': 0.0044
            },
        "cycle_length" : 0.5, # h
        "proba" : 0.1,
        "when" : {"presence_state" : ["awake"], "where" : "kitchen", "time" : [[12, 14, 0.3], [18, 22, 0.3]]}
    },
    "microwave" : {
        "proba" : 0.69, 
        "cycle_length" : 1/12, # h
        "power" : 700, # W asumption
        "when" : {"presence_state" : ["awake"], "where" : "kitchen", "time" : [[6, 10, 0.2], [12, 14, 0.5], [18, 22, 0.5]]} 
    }, 
    "boiler" : { # coffee machine included
        "proba" : 0.9, 
        "power" : 1200, # W asumption
        "cycle_length" : 1/60, # h asumption
        "when" : {"presence_state" : ["awake"], "where" : "kitchen", "time" : [[6, 10, 0.7], [18, 22, 0.2]]}
        }, 
    "toaster" : {
        "proba" : 0.8, 
        "power" : 1000, # W asumption
        "cycle_length" : 1/12, # h asumption
        "when" : {"presence_state" : ["awake"], "where" : "kitchen", "time" : [[6, 10, 0.8], [12, 14, 0.3]]}
    }, 
    "washing_machine" : {
        "proba" : 0.87, 
        "cap_popu" : {1 : 6.8, 2: 7.25, 3 : 7.7, 4 : 8.2, 5 : 8.75, 6 : 9.25}, # kg
        # "types" : {"A+++", "A++", "A+", "A", "B", "C", "D"}, 
        "E_types" : {"A+++" : 60, "A++" : 80, "A+" : 90, "A" : 95, "B" : 100, "C" : 110, "D" : 120}, # IEE %
        "types_proba" : {"A+++" : 0.075, "A++" : 0.15, "A+" : 0.15, "A" : 0.075, "B" : 0.06, "C" :0.02, "D":0.02}, 
        "cycle_length" : 3, # h
        "when" : {"presence_state" : ["awake"], "spec" : ["at start"], "proba" : 2/7}
    }, 
    "dryer" : {
        "proba" : 0.25, # Quasiment que des lave-linge sèchants
        # "types" : {"A+++", "A++", "A+", "A", "B", "C", "D"},
        "types_proba" : {"A+++" : 0.09, "A++" : 0.16, "A+" : 0.14, "A" : 0.08, "B" : 0.075, "C" :0.04, "D":0.02},
        "cap_popu" : {1 : 6.8, 2: 7.25, 3 : 7.7, 4 : 8.2, 5 : 8.75, 6 : 8.75}, # kg
        "E_types" : {"A+++" : 24, "A++" : 32, "A+" : 42, "A" : 65, "B" : 76, "C" : 85, "D" : 100}, # IEE %
        "cycle_length" : 2, # h
        "when" : {"presence_state" : ["awake"], "spec" : ["at start"], "proba" : 2/7}
    }, 
    "dishwasher" : {
        "proba" : 0.51, 
        "cap_popu" : {1 : 12.5, 2 : 12.7, 3 : 13, 4 : 13.1, 5 : 13.4, 6 : 13.4}, # couverts
        # "types" : {"A+++", "A++", "A+", "A", "B", "C", "D"},
        "types_proba" : {"A+++" : 0.075, "A++" : 0.16, "A+" : 0.15, "A" : 0.08, "B" : 0.03, "C" :0.025, "D":0.02},
        "E_types" : {"A+++" : 50, "A++" : 56, "A+" : 63, "A" : 71, "B" : 80, "C" : 90, "D" : 100}, # IEE %
        "cycle_length" : 2, # h
        "when" : {"presence_state" : ["awake"], "spec" : ["at start"], "proba" : 4/7},
    }, 
    "small_object_charge" : {
        "proba" : 1,
        "power" : 20, # W
        "cycle_length" : 1, # h
        "deviation" : 1, 
        "when" : {"presence_state" : ["awake"], "spec" : ["before leave"]}, 
    }, 
    "fix_computer" : {
        "proba" : 0.54, 
        "power" : 100, # W
        "when" : {"presence_state" : ["awake"], "proba_t" : 0.5}
    }, 
    "fixed_load_parameters" : {
        "power" : 30, # W 
    }, 
    "heating_system" : {
        "proba" : 0.37, 
        "T_wanted_awake" : 20, # °C
        "T_wanted_asleep" : 18, # °C
        "T_wanted_away" : 15, # °C
        "net_deviation" : 3, # °C
        # "types" : {"resistor", "heat_pump"},
        "types_proba" : {"resistor" : 32/37, "heat_pump" : 5/37},
        "when" : {"presence_state" : ["awake", "asleep"]},
    }, 
    "climatisation" : {
        "proba" : 0.25, # Hellowatt
        "T_activation" : 25, # °C
        "T_minus" : -7, # °C compared to outside temperature
        "net_deviation" : 3, # °C
        "when" : {"presence_state" : ["awake", "asleep"]}
    }, 
    "water_heater" : {
        "proba" : 0.44, # Ademe ballon électrique
        "energy_needed" : 2190, # Wh average per day and per person, source Ademe
        "P_popu" : {1: 1500, 2 : 1500, 3 : 2000, 4 : 2500, 5 : 2750, 6 : 3000}, # W asumption
        "deviation" : 0.5, # proportion
        "when" : {"presence_state" : ["awake", "asleep", "away"]},
    }

}
    

building = {    
    "types_proba" : {"house" : 0.3, "apartment" : 0.68, "building" : 0.02},
    "nb_popu_proba" : {1 : 0.27, 2 : 0.23, 3 : 0.18, 4 : 0.15, 5 : 0.1, 6 : 0.07},
    "DPE_proba" : {"A" : 0.05, "B" : 0.06, "C" : 0.37, "D" : 0.29, "E" : 0.15, "F" : 0.06, "G" : 0.03}, # Ademe
    "R_DPE" : {"A" : 2.5, "B" : 1.7, "C" : 1.3, "D" : 1, "E" : 0.7, "F" : 0.55, "G" : 0.35}, # m2.K/W
    "coef_R" : [0.3, 0.7],        
    "C_proba" : {25 : 0.2, 20 : 0.3, 15 : 0.3, 10 : 0.2}, # MJ/K un peu aléatoire ici
    "surface_probability" : {
        1: {20: 0.0800213063461695,
        35: 0.11076324996521954,
        50: 0.17118531393255348,
        70: 0.1934476112574181,
        90: 0.18444307217134476,
        110: 0.13901936019388422,
        140: 0.12112008613341044},
        2: {20: 0.05263160345422318,
        35: 0.08542988327973347,
        50: 0.15745820081562684,
        70: 0.19925078759515838,
        90: 0.2015898936740972,
        110: 0.16152103718488728,
        140: 0.1421185939962737},
        3: {20: 0.03266558463479743,
        35: 0.06023970774793562,
        50: 0.1379094823706121,
        70: 0.1996539573884693,
        90: 0.21777576130449944,
        110: 0.18599883227890404,
        140: 0.16575667427478213},
        4: {20: 0.02491463840750395,
        35: 0.04733649887569561,
        50: 0.12482370080874866,
        70: 0.19653459364806442,
        90: 0.22551258777034439,
        110: 0.19973926276661025,
        140: 0.18113871772303264},
        5: {20: 0.017563665881537825,
        35: 0.033567719706834975,
        50: 0.10828642554685668,
        70: 0.1896920709893704,
        90: 0.23346678583680064,
        110: 0.2157720231562118,
        140: 0.2016513088823877},
        6: {20: 0.014755672319619233,
        35: 0.02702613973718899,
        50: 0.09765253909760177,
        70: 0.1824006692836192,
        90: 0.23724787898183838,
        110: 0.22526621430035593,
        140: 0.2156508862797765}
    } # probability of having a surface given the number of people using insee data
}