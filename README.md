# Reproducibility package

Data and code to reproduce the results of the GridSFM AC-OPF benchmark and the RMS/EMT interconnection case study.

| Folder | Content | Guide |
|---|---|---|
| `gridsfm-acopf/` | Benchmark of the GridSFM-Open foundation model against open AC-OPF solvers on two synthetic grids | [`gridsfm-acopf/README.md`](gridsfm-acopf/README.md) |
| `ai-agents-rms-emt-case-study/` | RMS (ANDES) and EMT (DPsim, ParaEMT) ride-through case study on a 2,000-bus synthetic Texas grid | [`ai-agents-rms-emt-case-study/README.md`](ai-agents-rms-emt-case-study/README.md) |

## Requirements

* Python 3 with `numpy`, `pandas`, `scipy`, `matplotlib` and `openpyxl`. The GridSFM folder lists exact versions in `gridsfm-acopf/environment/`.
* Julia 1.11.7 and the other third-party tools listed in each folder README, only to rerun the solvers and simulators.
* Third-party data and software are available from their original sources, linked in each folder README.

Each folder README lists its contents, requirements, the commands that regenerate its tables and figures, and a map from each reported table, figure and number to the file, column or script that holds it.

## Verifying files

`SHA256SUMS` in this folder and in each subfolder lists every included file. Run `sha256sum -c SHA256SUMS` from the folder that holds the file.

## License

Code: MIT (see `LICENSE`). Data, reports, logs and figures: CC BY 4.0 unless a third-party license applies.
