
from qm.qua import *
import matplotlib.pyplot as plt
import warnings
from exp.readout_optimization import *
warnings.filterwarnings("ignore")

from datetime import datetime
import sys


# Dynamic config
from OnMachine.SetConfig.config_path import spec_loca, config_loca
from config_component.configuration import import_config
from config_component.channel_info import import_spec
from ab.QM_config_dynamic import initializer

spec = import_spec( spec_loca )
config = import_config( config_loca ).get_config()
qmm, _ = spec.buildup_qmm()
init_macro = initializer(100000,mode='wait')

# ro_elements = ['q0_ro','q1_ro','q2_ro']
ro_elements = ['q1_ro']
operate_qubit = ['q1_xy']
n_avg = 500


amp_range = (0.1, 1.8)
amp_resolution = 0.02
dataset = power_dep_signal( amp_range, amp_resolution, operate_qubit, ro_elements, n_avg, config, qmm, initializer=init_macro)

transposed_data = dataset.transpose("mixer", "state", "amplitude_ratio")

amps = transposed_data.coords["amplitude_ratio"].values
for ro_name, data in transposed_data.data_vars.items():  
    fig = plt.figure()
    ax = fig.subplots(1,2,sharex=True)
    plot_amp_signal( amps, data, ro_name, ax[0] )
    plot_amp_signal_phase( amps, data, ro_name, ax[1] )
    fig.suptitle(f"{ro_name} RO amplitude")
plt.show()
    

#   Data Saving   # 
save_data = True
if save_data:
    from exp.save_data import save_nc
    import sys
    save_nc(r"D:\Data\5Q4C\20240314", f"ro_amp_{operate_qubit[0]}", dataset)
