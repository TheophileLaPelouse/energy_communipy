from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource
from matplotlib.ticker import LinearLocator
from ..community import pyo

#%%
def plot_3d(x, y, z, title="3D Plot", xlabel="X-axis", ylabel="Y-axis", zlabel="Z-axis", save_path=None):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.plot(x, y, z, marker='+', linestyle='', color='b', label="Data Points")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_zlabel(zlabel)
    ax.legend()
    if save_path:
        plt.savefig(save_path)
    plt.show()
    return fig, ax


# def plot_2d(x, y, title="2D Plot", xlabel="X-axis", ylabel="Y-axis", save_path=None):
#     fig, ax = plt.subplot()
#     plt.plot(x, y, 
#     plt.title(title)
#     plt.xlabel(xlabel)
#     plt.ylabel(ylabel)
#     if save_path:
#         plt.savefig(save_path)
#     plt.show()
#     return fig, ax

def plot_hexagon_objective(values, title="Radar Objective Visualization", **kwargs):
    """
    Plot a hexagon radar chart based on objective values.

    Args:
        values (dictionnary): A dictionnary with list for each member and their corresponding values
        members (list): A list of member names, in the same order as the values in the dictionary.
        title (str): Title of the plot.
    """
    
    first_key = next(iter(values.keys()))
    n = len(values[first_key])
    # Define the angles for the vertices of the hexagon
    angles = [2*np.pi*(k/n) for k in range(n)]
    
    # print(n, angles)
    # Create the plot
    fig, ax = plt.subplots(subplot_kw=dict(polar=True))
    
    
    CB_color_cycle = ['#377eb8', '#ff7f00', '#4daf4a',
                  '#f781bf', '#a65628', '#984ea3',
                  '#999999', '#e41a1c', '#dede00']
    colors = kwargs.get("colors", CB_color_cycle)
    alpha = kwargs.get('alpha', 0.25)
    options = kwargs.get("options", {})
    dimension = kwargs.get("dimension", 0)
    circle = kwargs.get("circle", False)
    ylim = kwargs.get('ylim', None)
    
    c = 0
    for key in values :
        color = colors[c % len(colors)]
        c+=1
        # Plot the hexagon
        values_key = values[key]
        if isinstance(values_key[next(iter(values_key))], (tuple, list)) : 
            vals = [values[key][key2][dimension] for key2 in values[key]]
        else : 
            vals = [values[key][key2] for key2 in values[key]]
        
        if key in options : 
            ax.plot(angles + [angles[0]], vals + [vals[0]], **options[key]["plot"], label=key)
            ax.fill(angles, vals, **options[key]["fill"])   
        else :
            ax.plot(angles + [angles[0]], vals + [vals[0]], color=color, linewidth=1, label=key)
            ax.fill(angles, vals, color=color, alpha=alpha)

    # Add labels to the vertices
    labels = kwargs.get("labels", [key for key in values[first_key]])
    ax.set_xticks(angles)
    ax.set_xticklabels(labels)

    # Set the range for the radial axis
    if ylim :
        ax.set_ylim(0, ylim)
    
    # Set gridlines
    ax.grid(True)
    
    if circle : 
        theta = np.linspace(0, 2 * np.pi, 1000)  # Generate angles for a full circle
        r = np.full_like(theta, 1/n)  # Set the radius to 0.2
        ax.plot(theta, r, "--", color='red', linewidth=1)  # Draw the circle


    # Add title and legend
    ax.set_title(title, va='bottom')
    ax.legend(loc="upper right")#, bbox_to_anchor=(1.1, 1.1))
    
    path_to_save = kwargs.get("save_path", None)
    if path_to_save : 
        plt.savefig(path_to_save, bbox_inches='tight')

    # Show the plot
    plt.show()
    return fig, ax
    
def plot_power_curves(**kwargs) : 
    total_time = kwargs.get("total_time", 24)
    deltat = kwargs.get("deltat", 1)
    time = [t*deltat for t in range(total_time)]
    powers = kwargs.get("powers", {})
    title = kwargs.get("title", "Power Curves")
    xlabel = kwargs.get("xlabel", "Time (h)")
    ylabel = kwargs.get("ylabel", "Power (W)")
    
    fig, ax = plt.subplots()
    c = 0
    for label, power in powers.items() :
        if isinstance(power, (pyo.Var, pyo.Expression)) : 
            power_values = [pyo.value(power[t]) for t in range(total_time)]
        else : 
            power_values = power
        markers = ['+', 'x', 'o', 's', 'D', '^', '>']
        marker = markers[c % len(markers)]
        c+=1
        ax.plot(time, power_values, label=label, marker=marker, linestyle='-', linewidth=1)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True)
    ax.legend()
    plt.show()
    
    path_to_save = kwargs.get("save_path", None)
    if path_to_save : 
        plt.savefig(path_to_save, bbox_inches='tight')
    return fig, ax

    #%%
if __name__ == "__main__":
    # Example usage
    x = [10, 20, 30, 40, 50]
    y = [15, 25, 35, 45, 55]
    z = [5, 11, 10, 20, 25]

    # plot_3d(x, y, z)
    
    # x = [0, 1, 0]
    # y = [0, 0, 1]
    # z = [0, 1, 1]
    # plot_3d_shape(x, y, z)
    
    # x = [0, 1, 0, 1]
    # y = [0, 0, 1, 1]
    # z = [0, 1, 1, 0]
    # plot_3d_filled(x, y, z)
    # fig, ax = plot_3d(x, y, z)
    
    # X = [[0,1], [0, 1], [0.5, 0], [1,0.5]]
    # Y = [[0, 0], [1, 1], [0.5, 0], [0, 0.5]]
    # Z = [[0, 0], [0, 0], [1, 0], [0, 1]]
    # fig, ax, c = plot_3d_surface_(X, Y, Z)

    # plot_3d_square_with_surface()
    
    member_labels = ["Eco", "Enviro", "Comfort"]
    members = [1, 2, 3, 4]
    objective_values = {
        "method1" : {
            1 : [0.25],
            2 : [0.25],
            3 : [0.25],
            4 : [0.25]
        },
        "method2" : {
            1 : [0.5],
            2 : [0.25],
            3 : [0.15],
            4 : [0.1]
        }
    }
    plot_hexagon_objective(objective_values, alpha=0.2)
    
    # fig, ax = plot_3d(x, y, z)
    
    # X = np.arange(-5, 5, 0.25)
    # xlen = len(X)
    # Y = np.arange(-5, 5, 0.25)
    # ylen = len(Y)
    # X, Y = np.meshgrid(X, Y)

