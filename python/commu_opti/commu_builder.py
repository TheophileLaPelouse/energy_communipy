from .community.device import PV, battery, device, white_good, flex, EV, fixed, AoN
from .community.member import member
from .community.community import community
import time

def define_devices(list_args, **kwargs) : 
    # print("devices", list_args)
    devices = []
    c = 0
    for dico in list_args :
        # print(dico)
        if isinstance(list_args, dict) :
            args = list_args[dico]
            name = dico
            # print(dico)
        else : 
            args = dico
            name = f"device_{c}"
            c += 1
        
        args["parameters"]["name"] = name
        
        if args["type"] == "white_good" : 
            devices.append(white_good(**args["parameters"], **kwargs))
        elif args["type"] == "flex" :
            devices.append(flex(**args["parameters"], **kwargs))
        elif args["type"] == "EV" :
            devices.append(EV(**args["parameters"], **kwargs))
        elif args["type"] == "fixed" :
            devices.append(fixed(**args["parameters"], **kwargs))
        elif args["type"] == "device" :
            devices.append(device(**args["parameters"], **kwargs))
        elif args["type"] == "AoN" :
            devices.append(AoN(**args["parameters"], **kwargs))
        elif args["type"] == "PV" :
            devices.append(PV(**args["parameters"], **kwargs))
        elif args["type"] == "battery" :
            devices.append(battery(**args["parameters"], **kwargs))
        elif args["type"] == "water_heater" : 
            devices.append(AoN(**args["parameters"], **kwargs))
    return devices

def define_members(list_args, **kwargs) : 
    members = []
    # print("Defining members")
    for args in list_args : 
        t0 = time.time()
        devices = define_devices(args["devices"], **args["device_options"])
        members.append(member(devices=devices, **args["parameters"], **kwargs))
        print("Member defined in", time.time() - t0, "seconds\n")
    return members

def define_community(members, **kwargs) : 
    print("Defining Community")
    return community(members, **kwargs)