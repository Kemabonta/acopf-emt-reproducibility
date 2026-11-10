"""Derived from SAVED rows only (no solver, generator or training is run).
Median cost gap per grid x method on all eval scenarios vs. excluding the eval
scenarios whose case file is content-identical to a fine-tuning scenario.
Reads  eval/rows_all_with_refs.csv, eval/eval_ft_identical_scenarios.csv
Writes eval/tables/overlap_excluded_median_cost_gap.csv
Run from the gridsfm-acopf/ directory:  python src/overlap_sensitivity.py
"""
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent.parent
d = pd.read_csv(root / "eval" / "rows_all_with_refs.csv")
ids = set(pd.read_csv(root / "eval" / "eval_ft_identical_scenarios.csv").eval_id)
d["identical"] = d.scenario_id.isin(ids)
rows = []
for (grid, method), x in d.groupby(["grid", "method"]):
    a, b = x.cost_gap.median(), x[~x.identical].cost_gap.median()
    rows.append(dict(grid=grid, method=method, n_all=len(x), n_excl=int((~x.identical).sum()),
                     median_cost_gap_all=a, median_cost_gap_excl_identical=b,
                     abs_diff_percentage_points=abs(a - b) * 100))
out = pd.DataFrame(rows)
out.to_csv(root / "eval" / "tables" / "overlap_excluded_median_cost_gap.csv", index=False)
print(out.abs_diff_percentage_points.max())
