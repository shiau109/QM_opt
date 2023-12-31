from qm.QuantumMachinesManager import QuantumMachinesManager
from qm.qua import *
from qm import SimulationConfig
import sys
import pathlib
# QM_script_root = str(pathlib.Path(__file__).parent.parent.resolve())
# sys.path.append(QM_script_root)
import matplotlib.pyplot as plt
from qualang_tools.loops import from_array
from qualang_tools.results import fetching_tool
from qualang_tools.plot import interrupt_on_close
from qualang_tools.results import progress_counter
from exp.RO_macros import multiRO_declare, multiRO_measurement, multiRO_pre_save
import warnings

warnings.filterwarnings("ignore")
from qualang_tools.units import unit
u = unit(coerce_to_integer=True)

import exp.config_par as gc

def freq_time_rabi( dfs, time, q_name, ro_element, config, qmm, n_avg = 100, initializer = None, simulate=False):

    ref_xy_IF = {}
    for xy in q_name:
        ref_xy_IF[xy] = gc.get_IF(xy, config)

    freq_len = len(dfs)
    time_len = len(time)
    with program() as rabi:

        iqdata_stream = multiRO_declare(ro_element)
        t = declare(int)  
        n = declare(int)
        n_st = declare_stream()
        df = declare(int)  # QUA variable for the readout frequency
        with for_(n, 0, n < n_avg, n + 1):
            with for_(*from_array(df, dfs)):
                # Update the frequency of the xy elements
                with for_( *from_array(t, time) ):  
                    # Init
                    if initializer is None:
                        wait(100*u.us)
                        #wait(thermalization_time * u.ns)
                    else:
                        try:
                            initializer[0](*initializer[1])
                        except:
                            print("Initializer didn't work!")
                            wait(100*u.us)
                    for q in q_name:
                        update_frequency(q, ref_xy_IF[q]+df)

                    # Operation
                    for q in q_name:
                        play("x180", q, t)
                    align()
                    # Measurement
                    multiRO_measurement(iqdata_stream, ro_element, weights="rotated_")
            # Save iteration
            save(n, n_st)

        with stream_processing():
            n_st.save("iteration")

            multiRO_pre_save(iqdata_stream, ro_element, (freq_len,time_len) )
    if simulate:
        simulation_config = SimulationConfig(duration=10_000)  
        job = qmm.simulate(config, rabi, simulation_config)
        job.get_simulated_samples().con1.plot()
        plt.show()
        # pass
    else:
        qm = qmm.open_qm(config)
        job = qm.execute(rabi)

        fig, ax = plt.subplots(2, len(ro_element))
        if len(ro_element) == 1:
            ax = [[ax[0]],[ax[1]]]
        interrupt_on_close(fig, job)

        ro_ch_name = []
        for r_name in ro_element:
            ro_ch_name.append(f"{r_name}_I")
            ro_ch_name.append(f"{r_name}_Q")

        data_list = ro_ch_name + ["iteration"]   
        results = fetching_tool(job, data_list=data_list, mode="live")
        output_data = {}
        while results.is_processing():
            fetch_data = results.fetch_all()
            for r_idx, r_name in enumerate(ro_element):
                ax[0][r_idx].cla()
                ax[1][r_idx].cla()
                output_data[r_name] = np.array([fetch_data[r_idx*2], fetch_data[r_idx*2+1]])

                # Plot I
                # ax[0][r_idx].set_ylabel("I quadrature [V]")
                plot_freq_dep_time_rabi(output_data[r_name], dfs, time, [ax[0][r_idx],ax[1][r_idx]])
                # # Plot Q
                # ax[0][r_idx].set_ylabel("Q quadrature [V]")
                # plot_flux_dep_qubit(output_data[r_name][1], offset_arr, d_freq_arr,ax[1][r_idx]) 

            iteration = fetch_data[-1]
            # Progress bar
            progress_counter(iteration, n_avg, start_time=results.get_start_time()) 

            plt.pause(1)

        fetch_data = results.fetch_all()
        output_data = {}
        for r_idx, r_name in enumerate(ro_element):
            output_data[r_name] = np.array([fetch_data[r_idx*2], fetch_data[r_idx*2+1]])

        qm.close()
        return output_data


def freq_power_rabi( dfs, amps, q_name, ro_element, config, qmm, n_avg = 100, initializer = None, simulate=False):

    ref_xy_IF = {}
    for xy in q_name:
        ref_xy_IF[xy] = gc.get_IF(xy, config)

    freq_len = len(dfs)
    amp_len = len(amps)
    with program() as rabi:

        iqdata_stream = multiRO_declare(ro_element)
        ra = declare(fixed)  
        n = declare(int)
        n_st = declare_stream()
        df = declare(int)  # QUA variable for the readout frequency
        with for_(n, 0, n < n_avg, n + 1):
            with for_(*from_array(df, dfs)):
                # Update the frequency of the xy elements
                with for_( *from_array(ra, amps) ):  
                    # Init
                    if initializer is None:
                        wait(100*u.us)
                        #wait(thermalization_time * u.ns)
                    else:
                        try:
                            initializer[0](*initializer[1])
                        except:
                            print("Initializer didn't work!")
                            wait(100*u.us)
                    for q in q_name:
                        update_frequency(q, ref_xy_IF[q]+df)

                    # Operation
                    for q in q_name:
                        play("x180"*amp(ra), q)
                    align()
                    # Measurement
                    multiRO_measurement(iqdata_stream, ro_element, weights="rotated_")
            # Save iteration
            save(n, n_st)

        with stream_processing():
            n_st.save("iteration")

            multiRO_pre_save(iqdata_stream, ro_element, (freq_len,amp_len) )
    if simulate:
        simulation_config = SimulationConfig(duration=10_000)  
        job = qmm.simulate(config, rabi, simulation_config)
        job.get_simulated_samples().con1.plot()
        plt.show()
        # pass
    else:
        qm = qmm.open_qm(config)
        job = qm.execute(rabi)

        fig, ax = plt.subplots(2, len(ro_element))
        if len(ro_element) == 1:
            ax = [[ax[0]],[ax[1]]]
        interrupt_on_close(fig, job)

        ro_ch_name = []
        for r_name in ro_element:
            ro_ch_name.append(f"{r_name}_I")
            ro_ch_name.append(f"{r_name}_Q")

        data_list = ro_ch_name + ["iteration"]   
        results = fetching_tool(job, data_list=data_list, mode="live")
        output_data = {}
        while results.is_processing():
            fetch_data = results.fetch_all()
            for r_idx, r_name in enumerate(ro_element):
                ax[0][r_idx].cla()
                ax[1][r_idx].cla()
                output_data[r_name] = np.array([fetch_data[r_idx*2], fetch_data[r_idx*2+1]])

                # Plot I
                # ax[0][r_idx].set_ylabel("I quadrature [V]")
                plot_freq_dep_time_rabi(output_data[r_name], dfs, amps, [ax[0][r_idx],ax[1][r_idx]])
                # # Plot Q
                # ax[0][r_idx].set_ylabel("Q quadrature [V]")
                # plot_flux_dep_qubit(output_data[r_name][1], offset_arr, d_freq_arr,ax[1][r_idx]) 

            iteration = fetch_data[-1]
            # Progress bar
            progress_counter(iteration, n_avg, start_time=results.get_start_time()) 

            plt.pause(1)

        fetch_data = results.fetch_all()
        output_data = {}
        for r_idx, r_name in enumerate(ro_element):
            output_data[r_name] = np.array([fetch_data[r_idx*2], fetch_data[r_idx*2+1]])

        qm.close()
        return output_data

def plot_freq_dep_time_rabi( data, time, dfs, ax=None ):
    """
    data shape ( 2, N, M )
    2 is I,Q
    N is freq
    M is flux
    """
    idata = data[0]
    qdata = data[1]
    zdata = idata +1j*qdata
    s21 = zdata

    if type(ax)==None:
        fig, ax = plt.subplots()
        ax.set_title('pcolormesh')
        fig.show()
    ax[0].pcolormesh( dfs, time, np.abs(s21), cmap='RdBu')# , vmin=z_min, vmax=z_max)
    ax[1].pcolormesh( dfs, time, np.angle(s21), cmap='RdBu')# , vmin=z_min, vmax=z_max)


def plot_ana_freq_time_rabi( data, dfs, time, freq_LO, freq_IF, ax=None ):
    """
    data shape ( 2, N, M )
    2 is I,Q
    N is freq
    M is time
    """
    idata = data[0]
    qdata = data[1]
    zdata = idata +1j*qdata
    s21 = zdata

    abs_freq = freq_LO+freq_IF+dfs
    if type(ax)==None:
        fig, ax = plt.subplots()
        ax.set_title('pcolormesh')
        fig.show()
    ax[0].pcolormesh( time, abs_freq, np.abs(s21), cmap='RdBu')# , vmin=z_min, vmax=z_max)
    # ax[0].axvline(x=freq_LO+freq_IF, color='b', linestyle='--', label='ref IF')
    # ax[0].axvline(x=freq_LO, color='r', linestyle='--', label='LO')
    ax[0].axhline(y=freq_LO+freq_IF, color='black', linestyle='--', label='ref IF')

    ax[0].legend()
    ax[1].pcolormesh( time, abs_freq, np.angle(s21), cmap='RdBu')# , vmin=z_min, vmax=z_max)
    ax[1].axhline(y=freq_LO+freq_IF, color='black', linestyle='--', label='ref IF')

    ax[1].legend()


