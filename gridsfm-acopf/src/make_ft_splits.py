#!/usr/bin/env python3
"""Family-stratified nested FT splits (10 in 100 in 1000) + common validation set.
Pool rule (unchanged from the FT1000 run): T = first 1000 IPOPT-feasible labels in manifest
order, V = following feasible labels (<=100). Inside T, a seeded family-stratified interleave
gives nested prefixes whose family mix tracks the pool mix."""
import json, sys, random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SEEDS = {'ACTIVSg500': 20261107, 'ACTIVSg2000': 20261105}
OK = {'LOCALLY_SOLVED', 'OPTIMAL', 'ALMOST_LOCALLY_SOLVED'}
def fam(s): return s.split('_')[1]
def main(grid):
    lab = ROOT/'full/ft_labeled'/grid
    ids = [l.split(',')[0] for l in (ROOT/f'full/scenarios/{grid}_ft/cases.csv').read_text().splitlines() if l.strip()]
    feas, infeas, missing = [], [], []
    for s in ids:
        p = lab/f'{s}.pyg.json'
        if not p.exists(): missing.append(s); continue
        m = json.loads(p.read_text()).get('metadata', {})
        (feas if (m.get('feasible') or str(m.get('termination_status')) in OK) else infeas).append(s)
    T, V = feas[:1000], feas[1000:1100]
    rng = random.Random(SEEDS[grid])
    byf = {}
    for s in T: byf.setdefault(fam(s), []).append(s)
    keyed = []
    for f, members in sorted(byf.items()):
        rng.shuffle(members); n = len(members)
        for r, s in enumerate(members): keyed.append(((r + rng.random()) / n, s))
    order = [s for _, s in sorted(keyed)]
    mix = lambda L: {f: sum(fam(s) == f for s in L) for f in sorted(byf)}
    out = {'grid': grid, 'seed': SEEDS[grid], 'n_manifest': len(ids), 'n_feasible': len(feas),
           'n_infeasible': len(infeas), 'n_missing': len(missing), 'train_order': order, 'val': V,
           'mix': {str(n): mix(order[:n]) for n in (10, 100, 1000)}, 'val_mix': mix(V)}
    (ROOT/'full/ft_splits'/f'{grid}_split.json').write_text(json.dumps(out, indent=1))
    print(grid, {k: out[k] for k in ('n_feasible', 'n_infeasible', 'n_missing')}, out['mix'], 'val', len(V), out['val_mix'])
if __name__ == '__main__':
    for g in sys.argv[1:]: main(g)
