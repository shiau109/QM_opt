
from qm.qua import *
from qm import SimulationConfig
import matplotlib.pyplot as plt
import warnings
from exp.xyfreq_sweep_flux_dep import *
warnings.filterwarnings("ignore")

from datetime import datetime
import sys



# Dynamic config
from OnMachine.MeasFlow.ConfigBuildUp_new import spec_loca, config_loca
from config_component.configuration import import_config
from config_component.channel_info import import_spec
from OnMachine.Octave_Config.QM_config_dynamic import initializer

spec = import_spec( spec_loca )
config = import_config( config_loca ).get_config()
qmm, _ = spec.buildup_qmm()
init_macro = initializer(10000,mode='wait')


ro_elements = ['q1_ro']
q_name = ['q1_xy'] 
z_name = ['q1_z']

saturation_len = 1  # In us (should be < FFT of df)
saturation_ampRatio = 0.1  # pre-factor to the value defined in the config - restricted to [-2; 2)
n_avg = 200

flux_range = (-0.1,0.1)
flux_resolution = 0.005

freq_range = (-400,400)
freq_resolution = 1

dataset = xyfreq_sweep_flux_dep( flux_range, flux_resolution, freq_range, freq_resolution, q_name, ro_elements, z_name, config, qmm, saturation_ampRatio=saturation_ampRatio, saturation_len=saturation_len, n_avg=n_avg, sweep_type="z_pulse", simulate=False)


plt.show()

from exp.config_par import *

# Plot
freqs = dataset.coords["frequency"].values
flux = dataset.coords["flux"].values
for ro_name, data in dataset.data_vars.items():
    xy_LO = dataset.attrs["ref_xy_LO"][q_name[0]]
    xy_IF_idle = dataset.attrs["ref_xy_IF"][q_name[0]]
    z_offset = dataset.attrs["ref_z"][z_name[0]]
    print(ro_name, xy_LO, xy_IF_idle, z_offset, data.shape)
    fig, ax = plt.subplots(2)
    plot_ana_flux_dep_qubit(data, flux, freqs, xy_LO, xy_IF_idle, z_offset, ax)
    ax[0].set_title(ro_name)
    ax[1].set_title(ro_name)

plt.show()

save_data = False
if save_data:
    from exp.save_data import save_nc  
    save_nc()