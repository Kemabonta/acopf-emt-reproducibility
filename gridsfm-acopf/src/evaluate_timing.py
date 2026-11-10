#!/usr/bin/env python3
import json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]; T = ROOT/'full/timing'
M = {'pm': 'PM-IPOPT', 'mp': 'MATPOWER-MIPS', 'pp': 'pandapower-PIPS', 'gs': 'GridSFM-Z0'}
OK = {'LOCALLY_SOLVED', 'OPTIMAL', 'ALMOST_LOCALLY_SOLVED', 'SUCCESS', 'PREDICTED'}
rows = []
for g in ['ACTIVSg2000', 'ACTIVSg500']:
    for k, m in M.items():
        for sub, pas in [(k, 'pinned_parallel'), (k + '_repeat', 'pinned_sequential_repeat')]:
            for f in sorted((T/g/sub).glob('*.json')):
                if f.name.startswith('WARMUP_'): continue
                d = json.loads(f.read_text()); st = str(d.get('termination_status'))
                rows.append(dict(grid=g, method=m, pass_=pas, scenario_id=f.stem, status=st,
                                 solved=bool(d.get('solved')) and st in OK or st == 'PREDICTED',
                                 solve_time=d.get('solve_time'), wall_time=d.get('wall_time'), build_time=d.get('build_time'), model_load_s=d.get('model_load_s')))
df = pd.DataFrame(rows).rename(columns={'pass_': 'pass'})
main = df[df['pass'] == 'pinned_parallel']
main.to_csv(ROOT/'eval/timing_rows.csv', index=False)
print(main.groupby(['grid', 'method']).solve_time.median())
