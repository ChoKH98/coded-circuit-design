# Post-Layout Simulation Comparison

Command: `ngspice -b /home/whqkrel/rfic_project/results/lc_dco_nmos_extracted.spice`

Return code: `0`

| Metric | Pre-layout | Post-layout extracted | Delta |
| --- | ---: | ---: | ---: |
| Frequency | 2.4027 GHz | 2.3461 GHz | -56.6 MHz |
| Power | 904.0 uW | 929.2 uW | 25.2 uW |
| Phase noise | see pre-layout phase-noise script | not recalculated by transient-only PEX run | N/A |

Notes: post-layout netlist uses explicit RC parasitic approximation from `scripts/run_pex.py`.

Ngspice output tail:

```text
rence value :  2.12019e-07
 Reference value :  2.13123e-07
 Reference value :  2.14367e-07
 Reference value :  2.15585e-07
 Reference value :  2.16773e-07
 Reference value :  2.17935e-07
 Reference value :  2.19017e-07
 Reference value :  2.20193e-07
 Reference value :  2.21341e-07
 Reference value :  2.22585e-07
 Reference value :  2.23657e-07
 Reference value :  2.24695e-07
 Reference value :  2.25733e-07
 Reference value :  2.26817e-07
 Reference value :  2.28007e-07
 Reference value :  2.29121e-07
 Reference value :  2.30329e-07
 Reference value :  2.31499e-07
 Reference value :  2.32769e-07
 Reference value :  2.33935e-07
 Reference value :  2.35095e-07
 Reference value :  2.36329e-07
 Reference value :  2.37411e-07
 Reference value :  2.38565e-07
 Reference value :  2.39735e-07
 Reference value :  2.40891e-07
 Reference value :  2.42137e-07
 Reference value :  2.43221e-07
 Reference value :  2.44273e-07
 Reference value :  2.45361e-07
 Reference value :  2.46653e-07
 Reference value :  2.47769e-07
 Reference value :  2.48973e-07
 Reference value :  2.50143e-07
 Reference value :  2.51215e-07
 Reference value :  2.52257e-07
 Reference value :  2.53409e-07
 Reference value :  2.54597e-07
 Reference value :  2.55749e-07
 Reference value :  2.56889e-07
 Reference value :  2.58063e-07
 Reference value :  2.59297e-07
 Reference value :  2.60609e-07
 Reference value :  2.61789e-07
 Reference value :  2.62965e-07
 Reference value :  2.64213e-07
 Reference value :  2.65357e-07
 Reference value :  2.66497e-07
 Reference value :  2.67707e-07
 Reference value :  2.68781e-07
 Reference value :  2.69839e-07
 Reference value :  2.71007e-07
 Reference value :  2.72111e-07
 Reference value :  2.73311e-07
 Reference value :  2.74511e-07
 Reference value :  2.75705e-07
 Reference value :  2.76927e-07
 Reference value :  2.78191e-07
 Reference value :  2.79367e-07
 Reference value :  2.80537e-07
 Reference value :  2.81775e-07
 Reference value :  2.82977e-07
 Reference value :  2.84061e-07
 Reference value :  2.85315e-07
 Reference value :  2.86577e-07
 Reference value :  2.87695e-07
 Reference value :  2.88745e-07
 Reference value :  2.89807e-07
 Reference value :  2.90899e-07
 Reference value :  2.92009e-07
 Reference value :  2.93111e-07
 Reference value :  2.94083e-07
 Reference value :  2.95123e-07
 Reference value :  2.96221e-07
 Reference value :  2.97259e-07
 Reference value :  2.98205e-07
 Reference value :  2.99183e-07
No. of Data Rows : 150017
=============================================
NMOS-Only LC-DCO + LDO Tail Results
=============================================
v_max               =  1.31224e+00 at=  2.99851e-07
v_min               =  4.87166e-01 at=  2.99211e-07
V_swing [V]:
v_swing = 8.250729e-01
i_vdd               =  -1.03245e-03 from=  1.50000e-07 to=  3.00000e-07
P_dc [uW]:
p_dc_uw = 9.292023e+02
vs_avg              =  4.68380e-01 from=  1.50000e-07 to=  3.00000e-07
V(vs) avg [V]:
vs_avg = 4.683796e-01
Waveform saved.
ngspice-46+ done

```
