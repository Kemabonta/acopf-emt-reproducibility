#!/usr/bin/env python3
"""Common evaluator: one Ybus per scenario, every method scored from its own
V, theta, Pg, Qg by the same code. Writes per-(scenario, method) rows to eval/rows_<grid>.parquet/csv.
Usage: evaluate_full.py GRID [--workers N]"""
from __future__ import annotations
import json, sys, math, argparse
from pathlib import Path
import numpy as np, pandas as pd
import scipy.sparse as sp
from matpowercaseframes import CaseFrames

ROOT = Path(__file__).resolve().parents[1]; RES = ROOT/'full/results'; OUT = ROOT/'eval'
OK = {'LOCALLY_SOLVED', 'OPTIMAL', 'ALMOST_LOCALLY_SOLVED', 'SUCCESS'}
ANG = 60.0
# method name -> (results subdir, kind)
METHODS = {
    'PM-IPOPT': ('powermodels', 'pm'), 'MATPOWER-MIPS': ('matpower', 'mp'),
    'pandapower-PIPS': ('pandapower', 'pp'), 'GridSFM-Z0': ('gridsfm', 'gs'),
    'GridSFM-FT10': ('gridsfm_ft10', 'gs'), 'GridSFM-FT100': ('gridsfm_ft100', 'gs'),
    'GridSFM-FT1000': ('gridsfm_ft1000', 'gs'), 'DC-OPF': ('dcopf', 'pm'),
    'GridSFM-FT10-S1only': ('gridsfm_ft10_s1only', 'gs'), 'GridSFM-FT100-S1only': ('gridsfm_ft100_s1only', 'gs'),
    'GridSFM-FT1000-final': ('gridsfm_ft1000_final', 'gs'), 'GridSFM-FT10-commonval': ('gridsfm_ft10_commonval', 'gs'),
}

def load_json(p):
    try: return json.loads(Path(p).read_text())
    except Exception: return None

def load_case(path):
    cf = CaseFrames(str(path)); base = float(cf.baseMVA)
    bus = cf.bus; gen = cf.gen; br = cf.branch; gc = cf.gencost
    ids = bus.BUS_I.values.astype(int); idx = {b: i for i, b in enumerate(ids)}
    nb = len(ids)
    c = dict(base=base, ids=ids, idx=idx, type=bus.BUS_TYPE.values.astype(int),
             Pd=bus.PD.values.astype(float), Qd=bus.QD.values.astype(float),
             Gs=bus.GS.values.astype(float), Bs=bus.BS.values.astype(float),
             Vmin=bus.VMIN.values.astype(float), Vmax=bus.VMAX.values.astype(float))
    gst = gen.GEN_STATUS.values > 0
    c.update(gbus=np.array([idx[int(b)] for b in gen.GEN_BUS.values]), gon=gst,
             Pmax=gen.PMAX.values.astype(float), Pmin=gen.PMIN.values.astype(float),
             Qmax=gen.QMAX.values.astype(float), Qmin=gen.QMIN.values.astype(float))
    gcv = gc.values.astype(float)  # MODEL STARTUP SHUTDOWN NCOST C2 C1 C0 (quadratic)
    assert (gcv[:, 0] == 2).all() and (gcv[:, 3] == 3).all(), 'expect quadratic polynomial costs'
    c.update(c2=gcv[:, 4], c1=gcv[:, 5], c0=gcv[:, 6])
    on = br.BR_STATUS.values > 0
    f = np.array([idx[int(b)] for b in br.F_BUS.values])[on]; t = np.array([idx[int(b)] for b in br.T_BUS.values])[on]
    r = br.BR_R.values[on]; x = br.BR_X.values[on]; b = br.BR_B.values[on]
    tap = br.TAP.values[on].astype(float); tap[tap == 0] = 1.0
    tap = tap * np.exp(1j * np.deg2rad(br.SHIFT.values[on].astype(float)))
    ys = 1 / (r + 1j * x); ytt = ys + 1j * b / 2; yff = ytt / (tap * np.conj(tap))
    yft = -ys / np.conj(tap); ytf = -ys / tap
    nl = len(f); rows = np.arange(nl)
    Cf = sp.csr_matrix((np.ones(nl), (rows, f)), (nl, nb)); Ct = sp.csr_matrix((np.ones(nl), (rows, t)), (nl, nb))
    Yf = sp.diags(yff) @ Cf + sp.diags(yft) @ Ct; Yt = sp.diags(ytf) @ Cf + sp.diags(ytt) @ Ct
    Ysh = (c['Gs'] + 1j * c['Bs']) / base
    Ybus = Cf.T @ Yf + Ct.T @ Yt + sp.diags(Ysh)
    c.update(f=f, t=t, Yf=Yf.tocsr(), Yt=Yt.tocsr(), Ybus=Ybus.tocsr(), rateA=br.RATE_A.values[on].astype(float), nl=nl)
    return c

def extract(kind, d, c, pmgen_rows=None):
    """Return Vm, Va(rad), Pg(MW, per gen row, NaN unknown), Qg(MVAr)."""
    nb = len(c['ids']); ng = len(c['gbus'])
    Vm = np.full(nb, np.nan); Va = np.full(nb, np.nan); Pg = np.full(ng, np.nan); Qg = np.full(ng, np.nan)
    base = c['base']
    for k, v in (d.get('bus') or {}).items():
        bid = int(k) + 1 if kind == 'pp' else int(k)
        i = c['idx'].get(bid)
        if i is None: continue
        Vm[i] = v.get('vm', np.nan)
        Va[i] = v['va'] if 'va' in v else np.deg2rad(v.get('va_deg', np.nan))
    if kind in ('pm', 'gs'):
        for k, v in (d.get('gen') or {}).items():
            j = int(k) - 1
            if 0 <= j < ng: Pg[j] = v['pg'] * base; Qg[j] = v['qg'] * base
    elif kind == 'mp':
        for k, v in (d.get('gen') or {}).items():
            j = int(k) - 1
            if 0 <= j < ng: Pg[j] = v['pg']; Qg[j] = v['qg']
    # pandapower: stored gen dict omits sgen dispatch on multi-unit buses -> gen-side metrics not scored
    return Vm, Va, Pg, Qg

def residuals(c, Vm, Va, Pg, Qg, gen_known=True):
    out = {}
    base = c['base']; V = Vm * np.exp(1j * Va)
    vlo = np.maximum(c['Vmin'] - Vm, 0); vhi = np.maximum(Vm - c['Vmax'], 0); vv = np.maximum(vlo, vhi)
    out['v_viol_n'] = int((vv > 1e-4).sum()); out['v_viol_max_pu'] = float(vv.max())
    Sf = V[c['f']] * np.conj(c['Yf'] @ V) * base; St = V[c['t']] * np.conj(c['Yt'] @ V) * base
    lim = c['rateA'] > 0
    load = np.maximum(np.abs(Sf), np.abs(St))[lim] / c['rateA'][lim]
    out['th_viol_n'] = int((load > 1.001).sum()); out['th_overload_max_pct'] = float(max(0.0, (load.max() - 1) * 100)) if len(load) else 0.0
    out['max_loading_pct'] = float(load.max() * 100) if len(load) else np.nan
    dang = np.rad2deg(Va[c['f']] - Va[c['t']])
    out['ang_viol_n'] = int((np.abs(dang) > ANG + 1e-2).sum())
    if gen_known:
        on = c['gon']
        Sinj = V * np.conj(c['Ybus'] @ V) * base
        Sg = np.zeros(len(V), complex)
        np.add.at(Sg, c['gbus'][on], np.nan_to_num(Pg[on]) + 1j * np.nan_to_num(Qg[on]))
        mis = Sg - (c['Pd'] + 1j * c['Qd']) - Sinj
        out['bal_P_max_MW'] = float(np.abs(mis.real).max()); out['bal_Q_max_MVAr'] = float(np.abs(mis.imag).max())
        out['bal_P_L2_MW'] = float(np.linalg.norm(mis.real)); out['bal_Q_L2_MVAr'] = float(np.linalg.norm(mis.imag))
        pv = np.maximum(np.maximum(c['Pmin'] - Pg, Pg - c['Pmax']), 0)[on]; qv = np.maximum(np.maximum(c['Qmin'] - Qg, Qg - c['Qmax']), 0)[on]
        out['pg_viol_n'] = int((pv > 0.1).sum()); out['pg_viol_max_MW'] = float(np.nanmax(pv)) if len(pv) else 0.0
        out['qg_viol_n'] = int((qv > 0.1).sum()); out['qg_viol_max_MVAr'] = float(np.nanmax(qv)) if len(qv) else 0.0
        out['cost_recomp'] = float(np.nansum((c['c2'] * Pg ** 2 + c['c1'] * Pg + c['c0'])[on]))
    return out

def eval_scenario(args):
    grid, sid, cpath = args
    c = load_case(cpath)
    ref_bus = int(np.where(c['type'] == 3)[0][0])
    rows = []; sols = {}
    for m, (sub, kind) in METHODS.items():
        p = RES/grid/sub/f'{sid}.json'
        if not p.exists(): continue
        d = load_json(p)
        if d is None:
            rows.append(dict(grid=grid, scenario_id=sid, method=m, status='UNREADABLE', solved=False)); continue
        st = str(d.get('termination_status'))
        solved = (st == 'PREDICTED') if kind == 'gs' else (bool(d.get('solved')) or st in OK)
        r = dict(grid=grid, scenario_id=sid, family=sid.split('_')[1], method=m, status=st, solved=solved,
                 objective=d.get('objective'), solve_time=d.get('solve_time'), wall_time=d.get('wall_time'),
                 feas=d.get('feas'), feas_logit=d.get('feas_logit'), n_bus=len(c['ids']), load_MW=float(c['Pd'].sum()))
        if solved and d.get('bus'):
            Vm, Va, Pg, Qg = extract(kind, d, c)
            if np.isnan(Vm).any() or np.isnan(Va).any():
                r['note'] = f'missing_bus_values={int(np.isnan(Vm).sum())}'
                Vm = np.nan_to_num(Vm, nan=1.0); Va = np.nan_to_num(Va)
            gen_known = kind != 'pp' and not np.isnan(Pg[c['gon']]).all()
            r.update(residuals(c, Vm, Va, Pg, Qg, gen_known))
            if kind == 'gs': r['objective'] = r.get('cost_recomp', r['objective'])
            sols[m] = (Vm, Va - Va[ref_bus], Pg, Qg, gen_known)
        rows.append(r)
    # accuracy vs PM reference
    if 'PM-IPOPT' in sols:
        Vr, Ar, Pr, Qr, _ = sols['PM-IPOPT']; on = c['gon']
        for r in rows:
            m = r['method']
            if m not in sols or m == 'PM-IPOPT': continue
            Vm, Va, Pg, Qg, gk = sols[m]
            r['V_mae_pu'] = float(np.abs(Vm - Vr).mean()); r['V_max_pu'] = float(np.abs(Vm - Vr).max())
            da = np.rad2deg(np.angle(np.exp(1j * (Va - Ar))))
            r['ang_mae_deg'] = float(np.abs(da).mean()); r['ang_max_deg'] = float(np.abs(da).max())
            if gk:
                r['Pg_mae_MW'] = float(np.nanmean(np.abs(Pg - Pr)[on])); r['Qg_mae_MVAr'] = float(np.nanmean(np.abs(Qg - Qr)[on]))
                r['Pg_max_MW'] = float(np.nanmax(np.abs(Pg - Pr)[on]))
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('grid'); ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(); OUT.mkdir(exist_ok=True)
    lines = [l.split(',', 1) for l in (ROOT/f'full/scenarios/{a.grid}/cases.csv').read_text().splitlines() if l.strip() and not l.startswith('#')]
    if a.limit: lines = lines[:a.limit]
    jobs = [(a.grid, s, p) for s, p in lines]
    rows = []
    if a.workers > 1:
        from multiprocessing import Pool
        with Pool(a.workers) as pool:
            for i, rr in enumerate(pool.imap_unordered(eval_scenario, jobs, chunksize=4)):
                rows += rr
                if i % 50 == 0: print(a.grid, i, flush=True)
    else:
        for j in jobs: rows += eval_scenario(j)
    df = pd.DataFrame(rows)
    df.to_csv(OUT/f'rows_{a.grid}.csv', index=False)
    print('wrote', OUT/f'rows_{a.grid}.csv', df.shape)
    print(df.groupby('method')[['solved']].sum())

if __name__ == '__main__':
    main()
