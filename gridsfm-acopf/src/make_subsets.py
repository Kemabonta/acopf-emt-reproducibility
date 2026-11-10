#!/usr/bin/env python3
"""timing50 (pinned timing subset) and warm-start lists/seeds.
usage: make_subsets.py timing | warmlist | warmseeds"""
import json, sys, random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; RES = ROOT/'full/results'
GRIDS = ['ACTIVSg2000', 'ACTIVSg500']; SEED = {'ACTIVSg2000': 20261104, 'ACTIVSg500': 20261106}
QUOTA = {'S1': 13, 'S2': 7, 'S3': 10, 'S4': 5, 'S5': 5, 'S6': 7, 'S7': 3}
def cases(g): return [l.split(',', 1) for l in (ROOT/f'full/scenarios/{g}/cases.csv').read_text().splitlines() if l.strip()]
def strat(g, pool, seed_off=0):
    rng = random.Random(SEED[g] + seed_off); by = {}
    for s, p in pool: by.setdefault(s.split('_')[1], []).append((s, p))
    out = []
    for f, k in QUOTA.items():
        m = sorted(by.get(f, [])); rng.shuffle(m); out += m[:k]
    return out
mode = sys.argv[1]; D = ROOT/'full/timing'
if mode == 'timing':
    for g in GRIDS:
        sel = strat(g, cases(g))
        (D/f'{g}_timing50.csv').write_text('\n'.join(f'{s},{p}' for s, p in sel) + '\n')
        conv = ROOT/'full/conversions_eval'/g
        (D/f'{g}_timing50_pyg.csv').write_text('\n'.join(f'{s},{conv}/{s}.pyg.json' for s, p in sel) + '\n')
        (D/f'{g}_repeat10.csv').write_text('\n'.join(f'{s},{p}' for s, p in sel[::5]) + '\n')
        (D/f'{g}_repeat10_pyg.csv').write_text('\n'.join(f'{s},{conv}/{s}.pyg.json' for s, p in sel[::5]) + '\n')
        print(g, len(sel))
elif mode == 'warmlist':
    W = ROOT/'full/results_warm'
    for g in GRIDS:
        if g == 'ACTIVSg2000':
            sel = [l.split(',', 1) for l in (ROOT/'full/scenarios/ACTIVSg2000/warm50.csv').read_text().splitlines() if l.strip()]
        else:
            pool = [(s, p) for s, p in cases(g) if (json.loads((RES/g/'powermodels'/f'{s}.json').read_text()).get('solved'))]
            sel = strat(g, pool, 1)
        (W/g).mkdir(parents=True, exist_ok=True)
        (W/g/'warm50.csv').write_text('\n'.join(f'{s},{p}' for s, p in sel) + '\n'); print(g, len(sel))
elif mode == 'warmseeds':
    W = ROOT/'full/results_warm'
    for g in GRIDS:
        sel = [l.split(',')[0] for l in (W/g/'warm50.csv').read_text().splitlines() if l.strip()]
        for name, sub in [('Z0', 'gridsfm'), ('FT1000', 'gridsfm_ft1000'), ('GT', 'powermodels'), ('DC', 'dcopf')]:
            seeds = {}
            for s in sel:
                p = RES/g/sub/f'{s}.json'
                if not p.exists(): continue
                d = json.loads(p.read_text())
                if not d.get('bus'): continue
                seeds[s] = {'bus': {k: {'vm': v.get('vm', 1.0), 'va': v['va']} for k, v in d['bus'].items()},
                            'gen': {k: {'pg': v['pg'], 'qg': v.get('qg', 0.0)} for k, v in d.get('gen', {}).items()}}
            (W/g/f'seeds_{name}.json').write_text(json.dumps(seeds)); print(g, name, len(seeds))
        (W/g/'seeds_NONE.json').write_text('{}')
