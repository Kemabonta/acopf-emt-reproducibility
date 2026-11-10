# GridSFM AC-OPF benchmark

Title: *Benchmarking a Grid Foundation Model for AC Optimal Power Flow: Feasibility and Warm-Start Results on Synthetic Texas and South Carolina Grids*

This folder holds the data and code behind the results reported for the benchmark of GridSFM-Open 1.1.0 against Ipopt (PowerModels), MATPOWER MIPS, pandapower PIPS and a DC-OPF reference on ACTIVSg2000 (Texas footprint) and ACTIVSg500 (South Carolina footprint).

Raw solver outputs, scenario case files, converted graph files, labeled fine-tuning data and model weights are not included because of size; their SHA-256 checksums are listed in `MANIFEST_excluded_files.sha256`.

## Contents

| Path | Content |
|---|---|
| `src/` | Scenario generator, grid conversion, solver runners (`run_powermodels.jl`, `run_matpower.m`, `run_pandapower.py`, `run_dcopf.jl`, `run_powermodels_warm2.jl`), GridSFM inference and fine-tuning (`run_gridsfm.py`, `run_finetune_split.py`, `run_gridsfm_ft.py`), labeling (`batch_solve_labeled_pyg.jl`), the common evaluator (`evaluate_full.py`), `build_tables.py`, `make_figures.py` and `overlap_sensitivity.py`. |
| `eval/rows_ACTIVSg2000.csv`, `eval/rows_ACTIVSg500.csv`, `eval/rows_all_with_refs.csv` | One row per scenario and method from the common evaluator. Every table is computed from these rows. |
| `eval/timing_rows.csv` | Timing rows for the pinned 50-scenario subsets. |
| `eval/tables/` | Result tables (`.csv`, `.md`, `.tex`), `warm_start_per_scenario.csv` and `overlap_excluded_median_cost_gap.csv`. |
| `eval/eval_ft_identical_scenarios.csv` | Evaluation scenarios whose case file is identical to a fine-tuning scenario. |
| `figures/` | Figures 1 to 3 (`fig1_finetune_feasibility.png`, `fig2_warm_start.png`, `fig3_timing.png`). |
| `full/timing/`, `full/results_warm/`, `full/results/ACTIVSg2000/{powermodels_cold_repeat,powermodels_warm}` | Timing and warm-start result files read by `build_tables.py`. |
| `full/ft_models_strat/`, `full/ft_models/`, `full/ft_splits/` | Fine-tuning summaries (JSON: training and validation ids, epochs, validation gaps) and the training pool and validation splits. |
| `environment/` | Julia `Project.toml` and `Manifest.toml`, `python-packages.txt`, `versions.txt`, `checkpoint_sha256.txt`. |
| `grids/` | Source and SHA-256 of the grid cases. The cases are linked, not copied. |
| `MANIFEST_excluded_files.sha256` | SHA-256 checksums of the files that are not included. |
| `SHA256SUMS` | SHA-256 of every file in this folder. Check with `sha256sum -c SHA256SUMS`. |

## Requirements

* Python 3.13 with `pandas`, `numpy`, `scipy` and `matplotlib` (full list in `environment/python-packages.txt`).
* Julia 1.11.7 with the packages in `environment/Project.toml` and `environment/Manifest.toml` (only needed to rerun the solvers).
* Hardware used for the reported runs: one virtual machine with 8 cores of an Intel Xeon processor, 15 GiB of memory and no GPU; all runs were CPU-only (`environment/versions.txt`).

## Reproducing the tables and figures

Run from this folder.

```
python src/overlap_sensitivity.py   # writes eval/tables/overlap_excluded_median_cost_gap.csv
python src/make_figures.py          # writes figures/*.png from eval/tables and eval/timing_rows.csv
python src/build_tables.py          # rebuilds eval/tables/* from eval/rows_*.csv, the fine-tuning summaries and the timing and warm-start results
```

`src/build_tables.py` reads `eval/rows_*.csv`, `full/ft_models*/`, `full/timing`, `full/results_warm` and `full/results/ACTIVSg2000/powermodels_*`. Rebuilding `eval/rows_*.csv` from raw solver output with `src/evaluate_full.py` needs the raw result files, which are not included.

## Map of reported results to files

| Reported result | Source (file, column or script) |
|---|---|
| 500 evaluation scenarios per grid; seven perturbation families (S1 load scaling, S2 per-bus load, S3 branch outage, S4 generator outage, S5 rating derate, S6 renewable availability, S7 combined stress) | `src/scenario_generator.py` (`FAMILIES`, `apply_scenario`) |
| Texas fine-tuning validation list: 39 renewable and 1 combined-stress scenarios among the first 40 | `full/ft_models_strat/ACTIVSg2000_ft1000/ft1000_summary.json` (`val_ids[:40]`) |
| Post-pool validation lists of 93 (Texas) and 85 (South Carolina) scenarios | `full/ft_splits/*_split.json` (`val`); `ft1000_summary.json` (`n_val`) |
| Fine-tuning recipe: up to 10 epochs, AdamW, learning rate 1e-4, weight decay 1e-4, batch size 1, gradient clipping at 5, best validation epoch | `src/run_finetune_split.py` (header), `src/run_finetune_simple.py` |
| Texas FT1000: 4 epochs completed, epoch-1 checkpoint, validation median gap 0.51% | `full/ft_models_strat/ACTIVSg2000_ft1000/ft1000_summary.json` (`epochs_completed`, `best`) |
| South Carolina FT1000: epoch 4, validation median gap 1.46% | `full/ft_models_strat/ACTIVSg500_ft1000/ft1000_summary.json` (`best`) |
| Zero-shot gap on the FT1000 validation list 0.31% versus about 5.3% on the FT10 and FT100 validation sets (Texas) | `ft*_summary.json` (`zero_shot_val.median_cost_gap`: 0.0031, 0.0532, 0.0534) |
| Ipopt tolerances 1e-8, 3,000 iterations | `src/run_powermodels.jl` (line 49) |
| MIPS tolerances 1e-8, default limit of 150 iterations | `src/run_matpower.m` (lines 10 and 11) |
| PIPS with pandapower 3.5.6 defaults | `src/run_pandapower.py` (`pp.runopp` with default options) |
| No solver time limit in the benchmark runs; 120 s limit in the warm-start runs | `src/run_powermodels.jl`; `src/run_powermodels_warm2.jl` (`max_cpu_time`) |
| Hardware and software versions | `environment/versions.txt` |
| Table I, Texas and South Carolina rows (cost gap, maximum dP, maximum dQ, thermal violations) | `eval/tables/table2a_accuracy.csv` (`cost_gap_median_pct`); `eval/tables/table2b_violations.csv` (`bal_P_max_MW_med`, `bal_Q_max_MVAr_med`, `share_any_thermal_viol`) |
| Ipopt and MIPS mismatch below 0.001 MW and 0.001 Mvar | `eval/tables/table2b_violations.csv` |
| Zero-shot gap 5.36% (Texas) and 46.0% (South Carolina); DC-OPF gaps 2.24% and 2.42% | `eval/tables/table2a_accuracy.csv` |
| Fine-tuned gaps 0.44 to 1.36% (Texas) and 1.08 to 8.56% (South Carolina) | `eval/tables/table2a_accuracy.csv`; `eval/tables/table4_finetune_curve.csv` |
| Median overloaded branches 149 (zero-shot) and 32 (FT1000) on South Carolina | `eval/tables/table2b_violations.csv` (`thermal_viol_n_med`) |
| Table II convergence counts (Ipopt and MIPS 498 and 488, PIPS 495 and 494, DC-OPF 498 and 500, GridSFM 500 and 500) | `eval/tables/table0_counts.csv` (`converged`) |
| Table II pinned-subset medians (Ipopt 6.25 and 0.558 s, MIPS 3.39 and 0.674 s, PIPS 21.4 and 1.24 s, GridSFM zero-shot 1.32 and 0.157 s) | `eval/tables/table1_speed.csv` (`pinned_median_s`) |
| 49 successful timing records for Texas MIPS and PIPS | `eval/tables/table1_speed.csv` (`pinned_n`) |
| Ipopt and MIPS objective agreement 8.9e-10 (Texas) and 1.3e-8 (South Carolina); PIPS 2.2e-5 and 9.0e-3, above 0.1% in 99% of South Carolina pairs | `eval/tables/table5_solver_agreement.csv` (`obj_rel_median`, `share_obj_gt_0p1pct`) |
| Figure 1, panels (a) to (d) | `src/make_figures.py`; `eval/tables/table4_finetune_curve.csv` (`grid`, `n_finetune`, `subset`, `cost_gap_median_pct`, `ci95_lo_pct`, `ci95_hi_pct`); `eval/tables/table2b_violations.csv` (`grid`, `method`, `bal_P_max_MW_med`, `bal_Q_max_MVAr_med`, `share_any_thermal_viol`) |
| 95% bootstrap confidence interval of the median, 10,000 resamples | `src/build_tables.py` (`NBOOT = 10000`, seed 20261104) |
| South Carolina alternative protocols: FT10 on the post-pool validation list 10.45%, FT100 on load-scaling scenarios 2.19%, FT1000 final epoch 1.95% | `eval/tables/table4_finetune_curve.csv` (rows `GridSFM-FT10-commonval`, `GridSFM-FT100-S1only`, `GridSFM-FT1000-final`) |
| Warm start, South Carolina FT1000: 1.55 times, p below 1e-10, 90% of scenarios faster, iterations 45 to 30.5, time 0.583 to 0.364 s | `eval/tables/table6_warm_start.csv` (`geo_mean_speedup`, `wilcoxon_p`, `win_rate`, `median_iter_cold`, `median_iter_warm`, `cold_median_s`, `warm_median_s`) |
| South Carolina zero-shot seeds 0.26 times (4% faster); ground-truth seeds 1.49 times; DC-OPF seeds 1.48 times | `eval/tables/table6_warm_start.csv` (rows `Z0`, `GT`, `DC`) |
| Texas FT1000 seeds 1.12 times, 6.63 to 5.66 s, 49 of 50 pairs converged, p = 0.06 | `eval/tables/table6_warm_start.csv` (`geo_mean_speedup`, `cold_median_s`, `warm_median_s`, `both_converged`, `wilcoxon_p`) |
| Timed-out Texas pair at 159.8 s; counting it gives 1.05 times and p = 0.11 | `eval/tables/warm_start_per_scenario.csv` (scenario `ACTIVSg2000_S1_0088`, `warm_s`); computed from the 50 pairs in that file |
| Texas zero-shot, ground-truth and DC-OPF seeds 1.22 and 1.17 times, p below 1e-5; control with no start values 0.57 times | `eval/tables/table6_warm_start.csv` |
| Objectives of warm and cold runs matched on every jointly converged pair | `eval/tables/table6_warm_start.csv` (`same_obj_within_1e4` equals `both_converged`) |
| Figure 2 (warm-start speedup distributions) | `src/make_figures.py`; `eval/tables/warm_start_per_scenario.csv` (`grid`, `condition`, `cold_ok`, `warm_ok`, `speedup`) |
| Figure 3 (pinned-subset timing) | `src/make_figures.py`; `eval/timing_rows.csv` (`grid`, `method`, `solved`, `solve_time`) |
| ROC-AUC on Texas 0.42, 0.95 and 0.88 (zero-shot, FT100, FT1000) with 2 positive scenarios | `eval/tables/table3_feasibility.csv` (`ROC_AUC`, `n_infeasible`) |
| ROC-AUC on South Carolina 0.50, 0.59, 0.65 and 0.78 with 12 positive scenarios; FT10 flags 10 of 12 positives and 311 of 488 others; zero-shot flags all scenarios | `eval/tables/table3_feasibility.csv` (`TP`, `FP`) |
| Ipopt did not converge on 2 Texas and 12 South Carolina scenarios; MIPS did not converge on the same scenarios | `eval/tables/table0_counts.csv`; `eval/tables/table5_solver_agreement.csv` (`converge_disagree`) |
| Identical evaluation and fine-tuning scenarios (24 of 500 and 91 of 500; 24 and 85 in the training pool); exclusion changes no median gap by more than 0.31 percentage points | `eval/eval_ft_identical_scenarios.csv`; `eval/tables/overlap_excluded_median_cost_gap.csv` (see the next section) |

## Evaluation and fine-tuning scenario overlap

* Evaluation and fine-tuning scenarios were generated with different master seeds: Texas evaluation 20261104, Texas fine-tuning 20261105, South Carolina evaluation 20261106, South Carolina fine-tuning 20261107 (`src/scenario_generator.py`). Scenario identifiers repeat between the evaluation and fine-tuning manifests but refer to different cases.
* Two scenarios are identical when their case files are identical after normalizing the function-name line. Families S1, S2, S5, S6 and S7 draw continuous values and have no matches. Families S3 and S4 apply one discrete outage to the base case, so the same outage gives an identical file.

| | Texas (ACTIVSg2000) | South Carolina (ACTIVSg500) |
|---|---|---|
| Identical evaluation scenarios | 24 of 500 (8 S3, 16 S4) | 91 of 500 (42 S3, 49 S4) |
| In the 1,000-scenario training pool | 24 | 85 |
| In the post-pool validation list | 0 | 0 |
| Matching only non-converged fine-tuning scenarios | 0 | 6 |
| In the FT10 and FT100 training subsets | 1 and 2 | 2 and 28 |
| In the FT10 and FT100 in-pool validation sets | 2 and 5 | 27 and 16 |
| In the reported common subset | 24 of 498 | 85 of 488 |
| Distinct evaluation case files | 494 | 455 |

* The South Carolina variants trained on load-scaling scenarios only (`GridSFM-FT10-S1only`, `GridSFM-FT100-S1only`) have no matches.
* Excluding the identical scenarios from the rows in `eval/rows_all_with_refs.csv` changes no median cost gap by more than 0.31 percentage points (largest: 0.304 points, South Carolina FT10). `src/overlap_sensitivity.py` writes `eval/tables/overlap_excluded_median_cost_gap.csv` with the gaps for all rows and for the rows without the identical evaluation scenarios, per grid and method.
* `eval/eval_ft_identical_scenarios.csv` has the columns `grid, eval_id, family, ft_ids, ft_roles, in_FT10, in_FT100, in_FT1000`; `ft_ids` and `ft_roles` list every matching fine-tuning scenario.

## Third-party items

These items are linked, not redistributed.

| Item | Where | Note |
|---|---|---|
| GridSFM-Open 1.1.0 weights | https://huggingface.co/microsoft/GridSFM_Open | Checkpoint `gridsfm_open_v1.1.pt`, SHA-256 `f8a4396122e603e8303afdebe3b093819c0f64dac0878394aed0bd63205fd831` (`environment/checkpoint_sha256.txt`). Code from https://github.com/microsoft/GridSFM at commit `1ca775fd436d7ce013a1c0ab946e61ac7ef59ad6`. |
| ACTIVSg2000 and ACTIVSg500 | Texas A&M Electric Grid Test Case Repository: https://electricgrids.engr.tamu.edu/electric-grid-test-cases/activsg2000/ and https://electricgrids.engr.tamu.edu/electric-grid-test-cases/activsg500/ | SHA-256 of the copies used: `grids/GRID_FILE_SHA256.txt`. |
| MATPOWER 8.1.1-dev (MIPS) | https://github.com/MATPOWER/matpower, commit `80b6e16f760f58721ad31221c7287c28259cd4ad` | |
| pandapower 3.5.6 (PIPS) | https://github.com/e2nIEE/pandapower or `pip install pandapower==3.5.6` | |
| PowerModels 0.21.7, Ipopt.jl 1.16.0, JuMP 1.32.1, Julia 1.11.7 | Julia General registry | Exact versions in `environment/Manifest.toml`. |
| Octave 10.3.0, Python 3.13.5, torch 2.8.0 (CPU), torch_geometric 2.8.1 | | `environment/versions.txt`, `environment/python-packages.txt`. |

## License

Code: MIT (`../LICENSE`). Data, tables and figures: CC BY 4.0 unless a third-party license applies. The ACTIVSg cases, GridSFM weights, MATPOWER and pandapower keep their own licenses.
