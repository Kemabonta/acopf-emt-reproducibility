# AI agents running an RMS and EMT ride-through workflow

Title: *AI Agents Executing an RMS and EMT Ride-Through Workflow on a 2,000-Bus Synthetic Texas Grid: A Case Study with Open-Source Tools*

This folder holds the data, logs and scripts behind the results reported for the case study. One agent ran ANDES (RMS) on the full 2,000-bus ACTIVSg2000 network. A second agent ran DPsim and ParaEMT (EMT) on a Kron-reduced area around bus 6255.

The ACTIVSg2000 case files and the simulators are available from their original sources linked below and are not included. Values the study printed in text and that have no table behind them are listed in `data/derived/reported_values.csv`.

## Contents

| Path | Content |
|---|---|
| `logs/` | `author_messages.csv` (63 author messages: `agent`, `msg_no`, `time_mst`, `class`) and `elapsed_time.csv` (first message and last deliverable). |
| `criteria/` | `rms_criteria_locked.json` (locked RMS criteria) and `emt_pass_lines.md` (EMT pass lines and tolerances). |
| `data/case_matrix/` | Dispatch scenarios S1 to S4, RMS cases T1 to T11, EMT events E1 to E13, the requirement-to-pass-line map R1 to R12, and the cross-check and cross-tool tolerances (CSV). |
| `data/rms_results/` | `rms_verdict_matrix.csv` (44 RMS runs by 15 criteria) and the Buchanan unit 1 speed traces for S4 T8 with and without the project. |
| `data/andes_exchange/` | ANDES results exported for the EMT area: power-flow JSON, `S1_T*_poi.csv`, per-event boundary CSVs in `boundary/` (recompressed as tar.xz), `member_sha256.txt` and a README with the column definitions. |
| `data/emt_traces/` | As-studied EMT traces for DPsim and ParaEMT, one CSV per case (`dpsim/`, `paraemt/`). |
| `data/emt_initialization/` | DPsim and ParaEMT initial-condition comparison (`dpsim_paraemt_initial_comparison.csv`, split by case in `by_case/`) and the EMT and ANDES paired-event comparison (`emt_andes_paired_events.csv`). |
| `data/emt_results/` | `tuned_scores.xlsx` (sheets `Tuned scores`, `Clearing peaks`, `Notes`). |
| `data/speed/` | `rms_emt_comparison.xlsx` (sheets `S1 comparison`, `Wall clock`) and `wall_clock_observations.csv`. |
| `data/table3_inputs/` | The ANDES and EMT traces for the S1 single-line-to-ground case used in Table III. |
| `data/derived/` | `electrical_distance_to_6255.csv` and `reported_values.csv`. |
| `src/` | `derived/` (`parse_case.py`, `electrical_distance_to_6255.py`) and `figures/make_figures.py`. |
| `figures/` | Figure 2 (`fig2_buchanan_speed_S4T8.png`). |
| `SHA256SUMS` | SHA-256 of every file in this folder. Check with `sha256sum -c SHA256SUMS`. |

## Requirements

* Python 3 with `numpy`, `pandas`, `matplotlib` and `openpyxl`.
* To run `src/derived/*.py`, download the ACTIVSg2000 case files (links below) into `data/third_party/ACTIVSg2000/`. Run `python src/derived/parse_case.py` first to create the case tables.
* All paths in the scripts are relative to this folder.

## Reproducing the figures and checking the numbers

Run from this folder.

```
python src/figures/make_figures.py        # writes figures/fig2_buchanan_speed_S4T8.png and prints the final speed, time and minimum and maximum without project
```

Check the RMS counts:

```
python - <<'PY'
import csv
r = list(csv.DictReader(open('data/rms_results/rms_verdict_matrix.csv')))
print(len(r))                                                                        # 44 runs
print(sum(1 for x in r for k, v in x.items() if k != 'Case' and v.startswith('F')))  # 127 failing cells
print(sum(1 for x in r if x['Y3'].startswith('F')))                                   # Y3 fails on 44 runs
PY
```

Check the author-message counts (`agent`, `class`): `logs/author_messages.csv` has 55 messages to the RMS agent (38 routine check-ins and 17 substantive) and 8 to the EMT agent. The elapsed time of 3.8 days is the span in `logs/elapsed_time.csv` (2026-10-29 15:44 to 2026-11-02 10:27 MST, 3.78 days).

## Map of reported tables, figures and numbers to files

`data/derived/reported_values.csv` has the columns `quantity`, `value`, `unit`, `table_or_section` and `source_type`. Rows in that file are referred to below as "reported values".

| Reported item | Source |
|---|---|
| Table I, locked criteria | `criteria/rms_criteria_locked.json` (RMS); `criteria/emt_pass_lines.md` (EMT). The RMS criteria were hashed before any fault run with SHA-256 `ebf6e9fde748c2ea8d937dea150563b79ed912ef121b57d3e5e136005bab191a`; the EMT criteria with `66c1cc215fc34a006407456564c4be6b8e9d11ae5d804e91de5922bae4fcdef6`. The JSON file here omits one metadata field of the original, so its own checksum differs from the recorded value. |
| Table II, tool and model differences | Reported values (project transformer, time steps, plant bases); wall-clock row: `data/speed/wall_clock_observations.csv` (`tool`, `case`, `step`, `simulated_s`, `wall_s`, `wall_s_per_sim_s`) and sheet `Wall clock` of `data/speed/rms_emt_comparison.xlsx` |
| Table III, S1 paired events | `data/speed/rms_emt_comparison.xlsx`, sheet `S1 comparison` (columns `ANDES`, `DPsim 20 us`, `ParaEMT 50 us`); traces in `data/table3_inputs/` (`andes_S1_T5_poi.csv`: `t_from_fault_s`, `poi_V_pu`; `dpsim_*` and `paraemt_*` `_S1_E2_fast_on_dt50.csv`: `t_s`, `poi_v_min_pu`) |
| Table IV, ten errors | Reported values (rows 1 to 3, 6, 8, 10 and the speed values); clearing-ramp row: `data/emt_results/tuned_scores.xlsx` |
| Figure 1 (workflow) | Drawn diagram; it has no data behind it. |
| Figure 2 (Buchanan unit 1 speed, S4 T8) | `src/figures/make_figures.py`; `data/rms_results/S4_T8_Buchanan_speed_with_project.csv` and `..._without_project.csv` (`time_s`, `speed_pu`) |
| 44 RMS cases (11 events by 4 dispatches); 127 failing criterion cells; Y3 fails on every run | `data/rms_results/rms_verdict_matrix.csv` (`Case`, `B1` to `Y5`; a failing cell begins with `F`) |
| Loss-of-synchronism rule (speed gate 1.20 and 0.80 pu for 0.05 s; angle relative to the center of inertia above 360 degrees) | Reported values; criterion text in `criteria/rms_criteria_locked.json` (`section_6_verbatim`, line Y3) |
| 15 without-project comparisons; 13 of 15 with the same machines slipping | Reported values; Buchanan S4 T8 traces in `data/rms_results/` |
| S4 T8: Buchanan unit 1 reaches 1.20 pu at 4.01 s (1.229 pu) with the project; 0.985 to 1.007 pu for 60 s without | `data/rms_results/S4_T8_Buchanan_speed_*.csv` (`speed_pu`: 1.2287 at 4.0055 s; minimum 0.9846, maximum 1.0074) |
| S2 T11 no-project run stopping at 8.41 s on bus 6215 | Reported values |
| B3 as low as -19.8 Mvar on S4 T1 | `data/rms_results/rms_verdict_matrix.csv`, column `B3`, row `S4 T1` (-19.802) |
| L3 load return at 5.00 to 5.56 s | Reported values |
| 220-row EMT intake bench (176 pass, 2 fail, 42 informational, 178 scored) | Reported values |
| 84-row EMT system study (12 events, 42 cases: S1 18, S2 14, S3 5, S4 5; two time steps; 460 pass, 16 fail, 112 not applicable, 252 informational) | Reported values; EMT traces in `data/emt_traces/` |
| Austin 2 turbine angle swing of at most 70 degrees | Reported values |
| Wall-clock run times (ANDES 366 and 365 s; DPsim 246 s at 20 us and 497 s at 10 us; ParaEMT 38 to 42 s) | `data/speed/wall_clock_observations.csv` |
| Solver step: first adoption of 1/240 s (377 s on S1 T1, 403 s on S1 T5), original 1/480 s solver (820 s), agreement within 0.0032, 0.0065, 0.0064 and 0.0007 pu, 1/120 s rejected at 0.17 pu | Reported values |
| Kron-reduced area (21 buses and 76 branches; S4: 7 and 18; 14 boundary buses; 45 mutual terms dropped; reconstruction errors 1.327e-9 pu and 1.882e-8 degrees; short-circuit level and X/R at bus 6255) | Reported values |
| Prefault battery P and Q, E1/T1 voltage, E2/T5 voltage and reactive current, E8/T7 held voltage | `data/speed/rms_emt_comparison.xlsx`, sheet `S1 comparison` |
| DPsim and ParaEMT initial agreement (0.0004 pu and 0.4 MW) | `data/emt_initialization/dpsim_paraemt_initial_comparison.csv` and `by_case/` (`case`, `quantity`, `dpsim`, `paraemt`, `difference`, `tolerance`, `result`); `emt_andes_paired_events.csv` (`pair`, `tool`, `quantity`, `emt`, `transient`, `result`) |
| Clearing-ramp result: S1 E5 peak 2.39 to 1.01 pu (minimum-phase one-cycle RMS) and 27.9 to 1.09 pu (instantaneous) | `data/emt_results/tuned_scores.xlsx`, sheet `Clearing peaks` (row `dpsim`, `S1`, `E5`: 27.88, 1.09, 2.39, 1.01) |
| Buchanan unit 1 (bus 3105) is eight branches from the point of interconnection, minimum series impedance 0.418 pu on 100 MVA | `data/derived/electrical_distance_to_6255.csv` (`bus` 3105: `min_series_abs_z_pu100` 0.4180, `min_hops` 8); `src/derived/electrical_distance_to_6255.py` |
| Project data (133 MW battery, 130 MW load, bus 6255 at 230 kV; 75% IT and 25% cooling, power factor 0.98, 133 MVA transformer with 8% reactance and X/R 40) | `data/case_matrix/dispatch_scenarios_as_run.csv`; reported values |
| Dispatch scenarios, events and requirement map | `data/case_matrix/` (`dispatch_scenarios_as_run.csv`, `dispatch_scenarios_plan.csv`, `fault_and_event_cases.csv`, `events_pairing.csv`, `requirement_to_pass_line.csv`, `rms_emt_crosscheck_tolerances.csv`, `cross_tool_tolerances.csv`) |
| 63 author messages: 55 to the RMS agent (38 routine) and 8 to the EMT agent | `logs/author_messages.csv` |
| 3.8 days elapsed | `logs/elapsed_time.csv` |
| Tool versions and settings (ANDES 2.0.0 at 1/240 s with KLU and Newton tolerance 1e-4; DPsim 1.4; ParaEMT commit `d79d735a4a587d56c5b88187d1a499195b6b2b84`) | Reported values and the links below |

## Third-party items

These items are linked, not redistributed.

| Item | Where |
|---|---|
| ACTIVSg2000 case files | Texas A&M Electric Grid Test Case Repository: https://electricgrids.engr.tamu.edu/electric-grid-test-cases/activsg2000/ |
| ANDES 2.0.0 | https://github.com/CURENT/andes |
| DPsim 1.4 | https://github.com/sogno-platform/dpsim |
| ParaEMT (commit `d79d735`) | https://github.com/NatLabRockies/ParaEMT_public |
| ERCOT Nodal Operating Guides and Planning Guide | https://www.ercot.com/mktrules/guides |

## License

Code: MIT (`../LICENSE`). Data, logs and figures: CC BY 4.0 unless a third-party license applies. ACTIVSg2000, ANDES, DPsim and ParaEMT keep their own licenses.
