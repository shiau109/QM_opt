"""
        QUBIT SPECTROSCOPY
This sequence involves sending a saturation pulse to the qubit, placing it in a mixed state,
and then measuring the state of the resonator across various qubit drive intermediate dfs.
In order to facilitate the qubit search, the qubit pulse duration and amplitude can be changed manually in the QUA
program directly without having to modify the configuration.

The data is post-processed to determine the qubit resonance frequency, which can then be used to adjust
the qubit intermediate frequency in the configuration under "qubit_IF".

Note that it can happen that the qubit is excited by the image sideband or LO leakage instead of the desired sideband.
This is why calibrating the qubit mixer is highly recommended.

This step can be repeated using the "x180" operation to adjust the pulse parameters (amplitude, duration, frequency)
before performing the next calibration steps.

Prerequisites:
    - Identification of the resonator's resonance frequency when coupled to the qubit in question (referred to as "resonator_spectroscopy_multiplexed").
    - Calibration of the IQ mixer connected to the qubit drive line (whether it's an external mixer or an Octave port).
    - Set the flux bias to the maximum frequency point, labeled as "max_frequency_point", in the configuration.
    - Configuration of the cw pulse amplitude (const_amp) and duration (const_len) to transition the qubit into a mixed state.
    - Specification of the expected qubits T1 in the configuration.

Before proceeding to the next node:
    - Update the qubit frequency, labeled as "qubit_IF_q", in the configuration.
"""

from qm.qua import *
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.loops import from_array
from macros import qua_declaration, multiplexed_readout, live_plotting
from common_fitting_func import *
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings("ignore")

###################
#   Data Saving   #
###################
from datetime import datetime
import sys

save_progam_name = sys.argv[0].split('\\')[-1].split('.')[0]  # get the name of current running .py program
save_time = str(datetime.now().strftime("%Y%m%d-%H%M%S"))
save_path = f"{save_dir}\{save_time}_{save_progam_name}"

###################
# The QUA program #
###################
q_id = [2]
Qi = 3
focus = False
n_avg = 1000  # The number of averages
operation_flux_point = [0, 4.000e-02, -0.2542, -0.3914, -3.400e-01] 

# Adjust the pulse duration and amplitude to drive the qubit into a mixed state
saturation_len = 20 * u.us  # In ns (should be < FFT of df)
if focus: saturation_amp = 0.0007  # pre-factor to the value defined in the config - restricted to [-2; 2)
else: saturation_amp = 0.1  # pre-factor to the value defined in the config - restricted to [-2; 2)

# Qubit detuning sweep with respect to qubit_IF
if focus:
    # 1. Hitting the spot:
    span = 0.4 * u.MHz
    df = 1 * u.kHz
else:
    # 2. Wide-scan, Find 02/2:
    span = 400 * u.MHz
    df = 200 * u.kHz
dfs = np.arange(-span, +span + 0.1, df)
res_F = resonator_flux( operation_flux_point[Qi-1], *p1[Qi-1])
res_IF = (res_F - resonator_LO)/1e6
res_IF = int(res_IF * u.MHz)

with program() as multi_qubit_spec:
    I, I_st, Q, Q_st, n, n_st = qua_declaration(nb_of_qubits=len(q_id))
    df = declare(int)  # QUA variable for the readout frequency
    resonator_freq1 = declare(int, value=res_IF)  
    # Adjust the flux line biases to check whether you are actually measuring the qubit
    for i in range(4):
        set_dc_offset("q%s_z"%(i+1), "single", operation_flux_point[i])
    update_frequency(f"rr{Qi}", resonator_freq1)  
    # update_frequency(f"rr{Qi}", int((-103.3362)*u.MHz)) 
    with for_(n, 0, n < n_avg, n + 1):
        with for_(*from_array(df, dfs)):
            for i in q_id:
                update_frequency("q%s_xy"%(i+1), df + qubit_IF[i])
            for i in q_id:
                play("saturation" * amp(saturation_amp), "q%s_xy"%(i+1), duration=saturation_len * u.ns)  
                align("q%s_xy"%(i+1), "rr%s"%(i+1))
            multiplexed_readout(I, I_st, Q, Q_st, resonators=[x+1 for x in q_id], amplitude=0.99)
            # wait(thermalization_time * u.ns)
        save(n, n_st)

    with stream_processing():
        n_st.save("n")
        for i in q_id:
            I_st[q_id.index(i)].buffer(len(dfs)).average().save("I%s"%(i+1))
            Q_st[q_id.index(i)].buffer(len(dfs)).average().save("Q%s"%(i+1))
        

#####################################
#  Open Communication with the QOP  #
#####################################
qmm = QuantumMachinesManager(host=qop_ip, port=qop_port, cluster_name=cluster_name, octave=octave_config)
print("Running QUA version: %s" %(qmm.version()))

###########################
# Run or Simulate Program #
###########################

simulate = False

if simulate:
    simulation_config = SimulationConfig(duration=10_000)  # In clock cycles = 4ns
    job = qmm.simulate(config, multi_qubit_spec, simulation_config)
    job.get_simulated_samples().con1.plot()
    plt.show()
else:
    qm = qmm.open_qm(config)
    job = qm.execute(multi_qubit_spec)

    live_plotting(n_avg, q_id, job, dfs, [], 
                     "Qubit spectroscopy", save_data, save_path, stage="7", normalize=False, dimension=1)
    
    qm.close()
