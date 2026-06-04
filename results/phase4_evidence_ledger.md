# Phase 4 Evidence Ledger

## Step 1 - Cap Bank Instantiation + Sweep
- Netlist evidence: `circuits/lc_dco_nmos_top.cir` has `X_cap_msb` and `X_cap_lsb`.
- Command: `./venv/bin/python scripts/sweep_cap_bank.py`
- Outputs: `results/cap_bank_sweep.csv`, `results/cap_bank_sweep_summary.txt`, `results/cap_bank_sweep.png`
- Result: 64/64 sweep-phase points oscillated; measured range 1.5020 to 2.4029 GHz.

## Step 2 - Temperature Sweep
- Command: `./venv/bin/python scripts/sweep_temperature.py`
- Outputs: `results/temperature_sweep.csv`, `results/temperature_sweep_summary.txt`, `results/temperature_sweep.png`
- Result: -40, 0, 27, and 85 C all oscillated. Fixed mode measured 0.0 MHz deviation; PTAT mode rewrote the included LDO `B_vref` source per temperature and measured 20.0 MHz deviation.

## Step 3 - LDO V_ref Code Tracking
- Netlist evidence: `circuits/blocks/ldo_tail_nmos.cir` has code-driven `B_vref`.
- Command: `./venv/bin/python scripts/verify_vref_tracking.py`
- Outputs: `results/vref_tracking.csv`, `results/vref_tracking_report.txt`
- Result: V_ref tracks monotonically from 0.4700 V down to 0.2685 V along the checked code path.

## Step 4 - KLayout Layout
- Command: `klayout -b -r scripts/generate_layout.py`
- Outputs: `layouts/lc_dco_nmos.gds`, `layouts/lc_dco_nmos.oas`, `results/layout_generation_report.txt`
- Result: Generated top cell `LC_DCO_NMOS` with cross-coupled pair marker, LC tank conductors, cap-bank arrays, and LDO/tail marker on SG13G2 stream layers.

## Step 5 - DRC
- Command: `./venv/bin/python scripts/run_drc.py`
- Outputs: `results/drc_report.txt`, `results/drc_lc_dco_nmos/lc_dco_nmos.lyrdb`
- Result: Official IHP DRC launch reached the BEOL rules but blocked on a PDK/KLayout runtime error: undefined DRC helper `absolute`. This is not a clean DRC signoff.
- Fallback attempted: `./venv/bin/python scripts/run_magic_drc_extract.py`; blocked because installed Magic cannot load the IHP full tech file.

## Step 6 - LVS
- Command: `./venv/bin/python scripts/run_lvs.py`
- Output: `results/lvs_report.txt`
- Result: Official IHP LVS wrapper blocked because the local Python environment cannot import `klayout.db`; layout is also a placement/routing placeholder, not a PCell-level device layout. This is not a clean LVS signoff.

## Step 7 - Parasitic Extraction
- Command: `./venv/bin/python scripts/run_pex.py`
- Outputs: `results/lc_dco_nmos_extracted.spice`, `results/pex_report.txt`
- Result: Generated explicit RC parasitic approximation because no calibrated KLayout RCX wrapper was found in the local PDK tree. This is not calibrated foundry PEX.
- Fallback attempted: `./venv/bin/python scripts/run_magic_drc_extract.py`; blocked before extraction by Magic/IHP tech-file compatibility.

## Step 8 - Post-Layout Simulation
- Command: `./venv/bin/python scripts/post_layout_sim.py`
- Outputs: `results/post_layout_waveform.csv`, `results/post_layout_comparison.md`
- Result: ngspice return code 0 on the approximation-backed extracted netlist; frequency 2.3461 GHz, power 929.2 uW.
