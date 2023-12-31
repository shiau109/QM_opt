from qm.qua import *
from qm.QuantumMachinesManager import QuantumMachinesManager
from qm import SimulationConfig
from configuration import *
from qualang_tools.results import fetching_tool, progress_counter
from qualang_tools.loops import from_array
from macros import qua_declaration, multiplexed_readout, live_plotting
import matplotlib.pyplot as plt
import warnings
from scipy import signal
from scipy.optimize import curve_fit
from matplotlib.ticker import FuncFormatter
from common_fitting_func import *
warnings.filterwarnings("ignore")

from datetime import datetime
import sys

q_id = [0,1,2,3]
n_avg = 1000
span = 3 * u.MHz
df = 100 * u.kHz
dfs = np.arange(-span, +span + 0.1, df)

flux_min = -0.5
flux_max = 0.5
step = 0.01
flux = np.arange(flux_min, flux_max + step / 2, step)
depletion_time = 10 * u.us

simulate = False

def mRO_flux_dep_resonator( q_id,n_avg,dfs,flux,depletion_time,simulate,mode,qmm):
    with program() as multi_res_spec_vs_flux:
        I, I_st, Q, Q_st, n, n_st = qua_declaration(nb_of_qubits=len(q_id))
        df = declare(int) 
        dc = declare(fixed) 
        with for_(n, 0, n < n_avg, n + 1):
            with for_(*from_array(df, dfs)):
                for i in q_id:
                    update_frequency("rr%s"%(i+1), df + resonator_IF[i])
                with for_(*from_array(dc, flux)):
                    for i in q_id:
                        set_dc_offset("q%s_z"%(i+1), "single", dc)                   
                    wait(flux_settle_time * u.ns)  
                    multiplexed_readout(I, I_st, Q, Q_st, resonators=[x+1 for x in q_id], sequential=False)
                    wait(depletion_time * u.ns, ["rr%s"%(i+1) for i in q_id]) 
            save(n, n_st)
        with stream_processing():
            n_st.save("n")
            for i in q_id:
                I_st[q_id.index(i)].buffer(len(flux)).buffer(len(dfs)).average().save("I%s"%(i+1))
                Q_st[q_id.index(i)].buffer(len(flux)).buffer(len(dfs)).average().save("Q%s"%(i+1))
    if simulate:
        simulation_config = SimulationConfig(duration=10_000)  # In clock cycles = 4ns
        job = qmm.simulate(config, multi_res_spec_vs_flux, simulation_config)
        job.get_simulated_samples().con1.plot()
        plt.show()
    else:
        qm = qmm.open_qm(config)
        job = qm.execute(multi_res_spec_vs_flux)
        I_list, Q_list = ["I%s"%(i+1) for i in q_id], ["Q%s"%(i+1) for i in q_id]
        if mode == 'live':
            results = fetching_tool(job, I_list + Q_list + ["n"], mode='live')
            while results.is_processing():
                all_results = results.fetch_all()
                n = all_results[-1]
                I, Q = all_results[0:len(q_id)], all_results[len(q_id):len(q_id)*2]
                for i in q_id:
                    I[q_id.index(i)] = u.demod2volts(I[q_id.index(i)], readout_len)
                    Q[q_id.index(i)] = u.demod2volts(Q[q_id.index(i)], readout_len)
                    res_flux_live_plot(I,Q)
                    progress_counter(n, n_avg, start_time=results.start_time)
            plt.show()      
        elif mode == 'wait_for_all':
            results = fetching_tool(job, I_list + Q_list + ["n"], mode="wait_for_all")
            fetch_data = results.fetch_all()
            I, Q = fetch_data[0:len(q_id)], fetch_data[len(q_id):len(q_id)*2]
        Flux = np.zeros((len(q_id), len(flux)))
        Frequency = np.zeros((len(q_id), len(dfs)))
        Amplitude = np.zeros((len(q_id), len(dfs), len(flux)))
        Phase = np.zeros((len(q_id), len(dfs), len(flux)))
        for i in q_id:
            S = u.demod2volts(I[q_id.index(i)] + 1j * Q[q_id.index(i)], readout_len)
            R = np.abs(S)
            phase = np.angle(S)
            Flux[i] = flux
            Frequency[i] = dfs + resonator_IF[i] + resonator_LO
            Amplitude[i] = R
            Phase[i] = signal.detrend(np.unwrap(phase)) 
        qm.close()
        return Flux, Frequency, Amplitude, Phase, I, Q

def res_flux_live_plot(I,Q):
    Flux = np.zeros((len(q_id), len(flux)))
    Frequency = np.zeros((len(q_id), len(dfs)))
    Amplitude = np.zeros((len(q_id), len(dfs), len(flux)))
    Phase = np.zeros((len(q_id), len(dfs), len(flux)))
    for i in q_id:
        S = I[q_id.index(i)] + 1j * Q[q_id.index(i)]
        R = np.abs(S)
        phase = np.angle(S)
        Flux[i] = flux
        Frequency[i] = dfs + resonator_IF[i] + resonator_LO
        Amplitude[i] = R
        Phase[i] = signal.detrend(np.unwrap(phase)) 
        x_label = "Flux bias [V]"
        y_label = "Readout Freq [GHz]"  
        title = "Flux dep. Resonator spectroscopy"
        plt.suptitle(title + " signal: amplitude")             
        plt.subplot(1, len(q_id), q_id.index(i)+1)
        plt.cla()
        plt.title("q%s:"%(i+1))
        if q_id.index(i)==0: 
            plt.ylabel(y_label)
        plt.xlabel(x_label)
        plt.pcolor(Flux[i], Frequency[i], Amplitude[i])        
        plt.gca().yaxis.set_major_formatter(FuncFormatter(format_y_axis))
    plt.tight_layout()
    plt.pause(0.1)

def format_y_axis(value, tick_number):
    return f'{value * 1e-9:.3f}'

def res_flux_fitting(signal):
    min_index = [[] for _ in q_id]
    max_index = [[] for _ in q_id]
    res_F = [[] for _ in q_id]
    resonator_flux_params, resonator_flux_covariance = [], []
    res_LO = resonator_LO
    for i in q_id:
        for j in range(len(Flux[i])):
            min_index[i].append(np.argmin(signal[i][:,j]))

        temp_params, temp_covariance = curve_fit(
            f = resonator_flux, 
            xdata = Flux[i],
            ydata = Frequency[i][min_index[i]],
            p0=p[i],
            bounds = ([0,0,0,-0.5,-np.inf], [3e6,7,10,0.5,np.inf]))
        resonator_flux_params.append(temp_params)
        resonator_flux_covariance.append(temp_covariance)
        res_F[i].append(resonator_flux(Flux[i], *resonator_flux_params[i]))
        res_F[i] = res_F[i][0]
        max_index[i] = np.argmax(res_F[i])
        second_largest_value = np.partition(res_F[i], -2)[-2] 
        second_largest_index = np.where(res_F[i] == second_largest_value)[0][0]
        max_flux = Flux[i][max_index[i]]
        sec_flux = Flux[i][second_largest_index]

        if abs(max_flux) >= abs(sec_flux):
            max_ROF =  resonator_flux(sec_flux, *resonator_flux_params[i])
            print(f'Q{i+1}: maximum ROF: {max_ROF:.4e}, maximum res_IF: {(max_ROF-res_LO):.4e}, corresponding flux: {sec_flux:.3e}')
        else:
            max_ROF =  resonator_flux(max_flux, *resonator_flux_params[i])
            print(f'Q{i+1}: maximum ROF: {max_ROF:.4e}, maximum res_IF: {(max_ROF-res_LO):.4e}, corresponding flux: {max_flux:.3e}')            
    print(resonator_flux_params)
    return res_F, min_index

def res_flux_plot(Flux,Frequency,signal,fitting):
    x_label = "Flux bias [V]"
    y_label = "Readout Freq [GHz]"
    if fitting:  
        res_F, min_index = res_flux_fitting(signal)
        for i in q_id: 
            # TOP figure
            plt.subplot(2, len(q_id), q_id.index(i)+1)
            plt.cla()
            plt.title("q%s:"%(i+1))
            if q_id.index(i)==0: 
                plt.ylabel(y_label)
            plt.pcolor(Flux[i], Frequency[i], signal[i])        
            plt.plot(Flux[i], Frequency[i][min_index[i]])
            plt.gca().yaxis.set_major_formatter(FuncFormatter(format_y_axis))
            # BOTTOM figure
            plt.subplot(2, len(q_id), len(q_id)+q_id.index(i)+1)
            plt.cla()
            plt.xlabel(x_label)
            if q_id.index(i)==0:
                plt.ylabel(y_label)
            plt.plot(Flux[i], Frequency[i][min_index[i]])
            plt.plot(Flux[i], res_F[i])
            plt.gca().yaxis.set_major_formatter(FuncFormatter(format_y_axis))  
        plt.tight_layout()
    else:
        for i in q_id:
            plt.subplot(1, len(q_id), q_id.index(i)+1)
            plt.cla()
            plt.title("q%s:"%(i+1))
            if q_id.index(i)==0: 
                plt.ylabel(y_label)
            plt.xlabel(x_label)
            plt.pcolor(Flux[i], Frequency[i], signal[i])        
            plt.gca().yaxis.set_major_formatter(FuncFormatter(format_y_axis))
        plt.tight_layout()
    plt.show()

qmm = QuantumMachinesManager(host=qop_ip, port=qop_port, cluster_name=cluster_name, octave=octave_config)
Flux, Frequency, Amplitude, Phase, I, Q = mRO_flux_dep_resonator(q_id,n_avg,dfs,flux,depletion_time,simulate,'live',qmm) 
fig = res_flux_plot(Flux,Frequency,Amplitude,True)
