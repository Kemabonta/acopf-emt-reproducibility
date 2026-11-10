#!/usr/bin/env python3
"""Tables + figures from eval/rows_<grid>.csv (common evaluator), FT summaries,
warm-start and timing-subset results. Output: eval/tables/*.csv|.md|.tex, eval/figs/*.png|.pdf"""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]; EV = ROOT/'eval'; TB = EV/'tables'; FG = EV/'figs'
TB.mkdir(parents=True, exist_ok=True); FG.mkdir(parents=True, exist_ok=True)
GRIDS = ['ACTIVSg2000', 'ACTIVSg500']; GNAME = {'ACTIVSg2000': 'Texas (ACTIVSg2000)', 'ACTIVSg500': 'South Carolina (ACTIVSg500)'}
BASE_LOAD = {'ACTIVSg2000': 67109.0, 'ACTIVSg500': 7751.0}
EXACT = ['PM-IPOPT', 'MATPOWER-MIPS', 'pandapower-PIPS']
GS = ['GridSFM-Z0', 'GridSFM-FT10', 'GridSFM-FT100', 'GridSFM-FT1000']
FTN = {'GridSFM-Z0': 0, 'GridSFM-FT10': 10, 'GridSFM-FT100': 100, 'GridSFM-FT1000': 1000, 'GridSFM-FT10-S1only': 10, 'GridSFM-FT100-S1only': 100, 'GridSFM-FT1000-final': 1000, 'GridSFM-FT10-commonval': 10}
RNG = np.random.default_rng(20261104); NBOOT = 10000
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Times New Roman', 'DejaVu Serif'], 'font.size': 9,
                     'axes.labelsize': 9, 'legend.fontsize': 7.5, 'figure.dpi': 150, 'savefig.dpi': 300, 'savefig.bbox': 'tight'})

def boot_ci(x, f=np.median):
    x = np.asarray(x, float); x = x[~np.isnan(x)]
    if len(x) < 2: return (np.nan, np.nan)
    idx = RNG.integers(0, len(x), (NBOOT, len(x)))
    v = f(x[idx], axis=1); return tuple(np.percentile(v, [2.5, 97.5]))

def write(df, name, floatfmt='.4g'):
    df.to_csv(TB/f'{name}.csv', index=False)
    (TB/f'{name}.md').write_text(df.to_markdown(index=False, floatfmt=floatfmt))
    def cell(v):
        if isinstance(v, float):
            return '--' if math.isnan(v) else f'{v:{floatfmt}}'
        return str(v).replace('_', '\\_').replace('%', '\\%').replace('&', '\\&')
    lines = ['\\begin{tabular}{' + 'l' * len(df.columns) + '}', '\\hline',
             ' & '.join(cell(c) for c in df.columns) + ' \\\\', '\\hline']
    lines += [' & '.join(cell(v) for v in row) + ' \\\\' for row in df.itertuples(index=False)]
    lines += ['\\hline', '\\end{tabular}']
    (TB/f'{name}.tex').write_text('\n'.join(lines) + '\n')

def savefig(fig, name):
    fig.savefig(FG/f'{name}.png'); fig.savefig(FG/f'{name}.pdf'); plt.close(fig)

def load_rows():
    frames = []
    for g in GRIDS:
        p = EV/f'rows_{g}.csv'
        if p.exists(): frames.append(pd.read_csv(p))
    df = pd.concat(frames, ignore_index=True)
    df['solved'] = df['solved'].astype(bool)
    return df

def add_refs(df):
    pm = df[df.method == 'PM-IPOPT'].set_index(['grid', 'scenario_id'])
    mp = df[df.method == 'MATPOWER-MIPS'].set_index(['grid', 'scenario_id'])
    key = list(zip(df.grid, df.scenario_id))
    df['pm_solved'] = [bool(pm.solved.get(k, False)) for k in key]
    df['pm_obj'] = [pm.objective.get(k, np.nan) for k in key]
    df['mp_solved'] = [bool(mp.solved.get(k, False)) for k in key]
    df['mp_obj'] = [mp.objective.get(k, np.nan) for k in key]
    df['cost_gap'] = np.where(df.pm_solved & df.solved, (df.objective - df.pm_obj).abs() / df.pm_obj.abs(), np.nan)
    df['pm_mp_agree'] = df.pm_solved & df.mp_solved & ((df.mp_obj - df.pm_obj).abs() / df.pm_obj.abs() <= 1e-3)
    df['load_factor'] = df.load_MW / df.grid.map(BASE_LOAD)
    return df

def q(x, p):
    x = pd.Series(x).dropna(); return float(x.quantile(p)) if len(x) else np.nan

def table_speed(df, timing):
    rows = []
    for g in GRIDS:
        for m in EXACT + GS:
            d = df[(df.grid == g) & (df.method == m)]
            if d.empty: continue
            t = d[d.solved].solve_time.astype(float)
            r = dict(grid=g, method=m, n=len(d), converged=int(d.solved.sum()), conv_rate=d.solved.mean(),
                     bulk_median_s=q(t, .5), bulk_IQR_s=q(t, .75) - q(t, .25), bulk_p95_s=q(t, .95))
            if timing is not None:
                tt = timing[(timing.grid == g) & (timing.method == m) & timing.solved]
                if len(tt):
                    r.update(pinned_n=len(tt), pinned_median_s=q(tt.solve_time, .5), pinned_IQR_s=q(tt.solve_time, .75) - q(tt.solve_time, .25),
                             pinned_p95_s=q(tt.solve_time, .95))
            rows.append(r)
    out = pd.DataFrame(rows)
    # speedup of GridSFM Z0 vs PM, pinned if available
    write(out, 'table1_speed'); return out

def table_accuracy(df):
    rows = []
    for g in GRIDS:
        for m in ['MATPOWER-MIPS', 'pandapower-PIPS'] + GS + ['DC-OPF']:
            d = df[(df.grid == g) & (df.method == m) & df.pm_solved & df.solved]
            if d.empty: continue
            lo, hi = boot_ci(d.cost_gap)
            r = dict(grid=g, method=m, n=len(d), cost_gap_median_pct=100 * d.cost_gap.median(), ci95_lo_pct=100 * lo, ci95_hi_pct=100 * hi,
                     cost_gap_mean_pct=100 * d.cost_gap.mean(), cost_gap_p90_pct=100 * q(d.cost_gap, .9),
                     V_mae_pu=d.V_mae_pu.mean(), ang_mae_deg=d.ang_mae_deg.mean(),
                     Pg_mae_MW=d.get('Pg_mae_MW', pd.Series(dtype=float)).mean(), Qg_mae_MVAr=d.get('Qg_mae_MVAr', pd.Series(dtype=float)).mean())
            rows.append(r)
    out = pd.DataFrame(rows); write(out, 'table2a_accuracy'); return out

def table_violations(df):
    rows = []
    for g in GRIDS:
        for m in EXACT + GS + ['DC-OPF']:
            d = df[(df.grid == g) & (df.method == m) & df.solved & df.pm_solved]
            if d.empty: continue
            r = dict(grid=g, method=m, n=len(d),
                     share_any_V_viol=(d.v_viol_n > 0).mean(), V_viol_max_pu_med=d.v_viol_max_pu.median(),
                     share_any_thermal_viol=(d.th_viol_n > 0).mean(), thermal_viol_n_med=d.th_viol_n.median(),
                     overload_max_pct_med=d.th_overload_max_pct.median(),
                     share_any_angle_viol=(d.ang_viol_n > 0).mean(),
                     bal_P_max_MW_med=d.bal_P_max_MW.median(), bal_Q_max_MVAr_med=d.bal_Q_max_MVAr.median(),
                     share_any_Pg_viol=(d.pg_viol_n > 0).mean() if d.pg_viol_n.notna().any() else np.nan,
                     share_any_Qg_viol=(d.qg_viol_n > 0).mean() if d.qg_viol_n.notna().any() else np.nan)
            rows.append(r)
    out = pd.DataFrame(rows); write(out, 'table2b_violations'); return out

def feas_metrics(y_inf, score_inf, pred_inf):
    y = np.asarray(y_inf, bool); p = np.asarray(pred_inf, bool)
    tp = int((p & y).sum()); fp = int((p & ~y).sum()); tn = int((~p & ~y).sum()); fn = int((~p & y).sum())
    prec = tp / (tp + fp) if tp + fp else np.nan; rec = tp / (tp + fn) if tp + fn else np.nan
    f1 = 2 * prec * rec / (prec + rec) if (prec == prec and rec == rec and prec + rec) else np.nan
    tnr = tn / (tn + fp) if tn + fp else np.nan
    bal = np.nanmean([rec, tnr]) if not (np.isnan(rec) and np.isnan(tnr)) else np.nan
    auc = np.nan
    if y.any() and (~y).any():
        auc = stats.mannwhitneyu(np.asarray(score_inf)[y], np.asarray(score_inf)[~y]).statistic / (y.sum() * (~y).sum())
    return dict(TP=tp, FP=fp, TN=tn, FN=fn, precision=prec, recall=rec, F1=f1, balanced_acc=bal, ROC_AUC=auc)

def table_feasibility(df):
    rows = []
    for g in GRIDS:
        for m in GS:
            d = df[(df.grid == g) & (df.method == m) & df.feas.notna()]
            if d.empty: continue
            score_inf = 1 - d.feas.astype(float)  # probability infeasible
            for lab in ['IPOPT', 'IPOPT+MIPS consensus']:
                if lab == 'IPOPT':
                    y = ~d.pm_solved; mask = np.ones(len(d), bool)
                else:
                    mask = (d.pm_solved == d.mp_solved).values; y = ~d.pm_solved
                r = dict(grid=g, method=m, label=lab, n=int(mask.sum()), n_infeasible=int(y[mask].sum()))
                r.update(feas_metrics(y[mask], score_inf[mask], (d.feas.astype(float) < 0.5)[mask]))
                rows.append(r)
    out = pd.DataFrame(rows); write(out, 'table3_feasibility'); return out

def table_agreement(df):
    rows = []
    piv = {m: df[df.method == m].set_index(['grid', 'scenario_id']) for m in EXACT}
    for g in GRIDS:
        for a, b in [('PM-IPOPT', 'MATPOWER-MIPS'), ('PM-IPOPT', 'pandapower-PIPS'), ('MATPOWER-MIPS', 'pandapower-PIPS')]:
            A = piv[a].xs(g, level=0); B = piv[b].xs(g, level=0)
            ids = A.index.intersection(B.index)
            A = A.loc[ids]; B = B.loc[ids]
            both = A.solved & B.solved
            rel = ((A.objective - B.objective).abs() / A.objective.abs())[both]
            r = dict(grid=g, pair=f'{a} vs {b}', n_common=len(ids), both_converged=int(both.sum()),
                     converge_disagree=int((A.solved != B.solved).sum()),
                     obj_rel_median=rel.median(), obj_rel_p95=q(rel, .95), obj_rel_max=rel.max(), share_obj_gt_0p1pct=(rel > 1e-3).mean())
            if b == 'MATPOWER-MIPS' or a == 'MATPOWER-MIPS':
                pass
            rows.append(r)
        d = df[(df.grid == g) & (df.method == 'MATPOWER-MIPS') & df.pm_solved & df.solved]
        rows.append(dict(grid=g, pair='MATPOWER vs PM: V/Pg (evaluator)', n_common=len(d), both_converged=len(d),
                         obj_rel_median=d.cost_gap.median(), obj_rel_max=d.cost_gap.max(),
                         V_max_pu_median=d.V_max_pu.median(), Pg_mae_MW_median=d.Pg_mae_MW.median()))
        d3 = df[(df.grid == g)].pivot_table(index='scenario_id', columns='method', values='solved', aggfunc='first')
        if set(EXACT) <= set(d3.columns):
            all3 = d3[EXACT].fillna(False).astype(bool).all(axis=1)
            ob = df[(df.grid == g)].pivot_table(index='scenario_id', columns='method', values='objective', aggfunc='first')
            rel_all = ob[EXACT].max(axis=1).sub(ob[EXACT].min(axis=1)).abs() / ob['PM-IPOPT'].abs()
            rows.append(dict(grid=g, pair='all three converged', n_common=len(d3), both_converged=int(all3.sum()),
                             obj_rel_median=rel_all[all3].median(), share_obj_gt_0p1pct=(rel_all[all3] > 1e-3).mean()))
    out = pd.DataFrame(rows); write(out, 'table5_solver_agreement'); return out

def warm_start():
    rows = []
    sets = {'ACTIVSg2000': ('powermodels_cold_repeat', 'powermodels_warm', 'v1 runner: IPOPT warm options, start not applied (control)')}
    extra = ROOT/'full/results_warm'
    for g in GRIDS:
        conds = []
        if g in sets: conds.append((RES_DIR/g/sets[g][0], RES_DIR/g/sets[g][1], sets[g][2]))
        if extra.exists():
            for w in sorted((extra/g).glob('warm_*')) if (extra/g).exists() else []:
                conds.append((extra/g/'cold_same_opts', w, w.name.replace('warm_', '') + ' (pinned)'))
        for cdir, wdir, label in conds:
            if not wdir.exists() or not cdir.exists(): continue
            for f in wdir.glob('*.json'):
                if f.name.startswith('WARM'): continue
                w = json.loads(f.read_text()); cp = cdir/f.name
                if not cp.exists(): continue
                c = json.loads(cp.read_text())
                rows.append(dict(grid=g, condition=label, scenario_id=w.get('scenario_id', f.stem), cold_s=c.get('solve_time'), warm_s=w.get('solve_time'),
                                 cold_obj=c.get('objective'), warm_obj=w.get('objective'), cold_ok=c.get('solved'), warm_ok=w.get('solved'),
                                 warm_timed_out=w.get('timed_out'), cold_iter=c.get('iterations'), warm_iter=w.get('iterations')))
    per = pd.DataFrame(rows)
    if per.empty: return per, per
    per['speedup'] = per.cold_s / per.warm_s
    per['same_obj'] = (per.cold_obj - per.warm_obj).abs() / per.cold_obj.abs() <= 1e-4
    per.to_csv(TB/'warm_start_per_scenario.csv', index=False)
    summ = []
    for (g, cnd), d in per.groupby(['grid', 'condition']):
        ok = d[d.cold_ok.astype(bool) & d.warm_ok.astype(bool)]
        sp_ = ok.speedup.astype(float)
        try: wil = stats.wilcoxon(ok.cold_s, ok.warm_s).pvalue
        except Exception: wil = np.nan
        summ.append(dict(grid=g, condition=cnd, n=len(d), both_converged=len(ok), warm_timeouts=int(d.warm_timed_out.fillna(False).astype(bool).sum()),
                         same_obj_within_1e4=int(ok.same_obj.sum()), geo_mean_speedup=float(np.exp(np.log(sp_).mean())) if len(sp_) else np.nan,
                         median_speedup=sp_.median(), win_rate=(sp_ > 1).mean(),
                         median_iter_cold=pd.to_numeric(ok.cold_iter, errors='coerce').median(), median_iter_warm=pd.to_numeric(ok.warm_iter, errors='coerce').median(), cold_median_s=ok.cold_s.median(), warm_median_s=ok.warm_s.median(), wilcoxon_p=wil))
    s = pd.DataFrame(summ); write(s, 'table6_warm_start'); return per, s

RES_DIR = ROOT/'full/results'

def ft_tables(df, acc):
    rows = []
    for g in GRIDS:
        for m in GS + ['GridSFM-FT1000-final', 'GridSFM-FT10-S1only', 'GridSFM-FT100-S1only', 'GridSFM-FT10-commonval']:
            d = df[(df.grid == g) & (df.method == m) & df.pm_solved & df.solved]
            if d.empty: continue
            lo, hi = boot_ci(d.cost_gap); f = df[(df.grid == g) & (df.method == m) & df.feas.notna()]
            fm = feas_metrics(~f.pm_solved, 1 - f.feas, f.feas < 0.5) if len(f) else {}
            n = FTN[m]
            sp = (ROOT/'full/ft_models'/f'{g}_ft{n}' if 'S1only' in m else (ROOT/'full/ft_models_strat'/f'{g}_ft{n}_commonval' if 'commonval' in m else ROOT/'full/ft_models_strat'/f'{g}_ft{n}'))/f'ft{n}_summary.json'
            sj = json.loads(sp.read_text()) if sp.exists() else {}
            rows.append(dict(grid=g, n_finetune=n, method=m, subset='S1 only (manifest order)' if 'S1only' in m else ('none' if n == 0 else ('family-stratified, final epoch' if 'final' in m else ('family-stratified, S6/S7 val' if 'commonval' in m else 'family-stratified'))), n_test=len(d), cost_gap_median_pct=100 * d.cost_gap.median(), ci95_lo_pct=100 * lo, ci95_hi_pct=100 * hi,
                             cost_gap_mean_pct=100 * d.cost_gap.mean(), V_mae_pu=d.V_mae_pu.mean(), ang_mae_deg=d.ang_mae_deg.mean(), Pg_mae_MW=d.Pg_mae_MW.mean(), Qg_mae_MVAr=d.Qg_mae_MVAr.mean(),
                             bal_P_max_MW_med=d.bal_P_max_MW.median(), thermal_viol_n_med=d.th_viol_n.median(), feas_F1=fm.get('F1'), feas_AUC=fm.get('ROC_AUC'),
                             val_median_gap_pct=100 * ((sj.get('best') or {}).get('val') or {}).get('median_cost_gap', np.nan) if sj else np.nan,
                             best_epoch=(sj.get('best') or {}).get('epoch') if sj else None, train_time_min=(sj.get('elapsed_s') if sj.get('elapsed_s') is not None else np.nan) / 60 if sj else np.nan))
    out = pd.DataFrame(rows); write(out, 'table4_finetune_curve'); return out

def table_texas_vs_sc(df):
    rows = []
    for m in GS + ['MATPOWER-MIPS', 'pandapower-PIPS']:
        A = df[(df.grid == 'ACTIVSg2000') & (df.method == m) & df.pm_solved & df.solved]
        B = df[(df.grid == 'ACTIVSg500') & (df.method == m) & df.pm_solved & df.solved]
        if A.empty or B.empty: continue
        a = A.cost_gap.dropna().values; b = B.cost_gap.dropna().values
        ia = RNG.integers(0, len(a), (NBOOT, len(a))); ib = RNG.integers(0, len(b), (NBOOT, len(b)))
        ratio = np.median(a[ia], axis=1) / np.median(b[ib], axis=1)
        r = dict(method=m, texas_median_gap_pct=100 * np.median(a), sc_median_gap_pct=100 * np.median(b), ratio_texas_over_sc=np.median(a) / np.median(b),
                 ratio_ci95_lo=np.percentile(ratio, 2.5), ratio_ci95_hi=np.percentile(ratio, 97.5),
                 texas_V_mae=A.V_mae_pu.mean(), sc_V_mae=B.V_mae_pu.mean(),
                 texas_Pg_mae_per_GW_load=A.Pg_mae_MW.mean() / (A.load_MW.mean() / 1000) if 'Pg_mae_MW' in A and A.Pg_mae_MW.notna().any() else np.nan,
                 sc_Pg_mae_per_GW_load=B.Pg_mae_MW.mean() / (B.load_MW.mean() / 1000) if 'Pg_mae_MW' in B and B.Pg_mae_MW.notna().any() else np.nan,
                 texas_balP_max_per_GW=A.bal_P_max_MW.median() / (A.load_MW.mean() / 1000), sc_balP_max_per_GW=B.bal_P_max_MW.median() / (B.load_MW.mean() / 1000))
        if m.startswith('GridSFM'):
            for g, tag in [('ACTIVSg2000', 'texas'), ('ACTIVSg500', 'sc')]:
                f = df[(df.grid == g) & (df.method == m) & df.feas.notna()]
                r[f'{tag}_feas_F1'] = feas_metrics(~f.pm_solved, 1 - f.feas, f.feas < 0.5)['F1'] if len(f) else np.nan
        rows.append(r)
    out = pd.DataFrame(rows); write(out, 'table7_texas_vs_sc'); return out

def table_by_family(df):
    d = df[df.method.isin(GS + ['MATPOWER-MIPS', 'pandapower-PIPS']) & df.pm_solved & df.solved]
    t = d.groupby(['grid', 'method', 'family']).cost_gap.median().mul(100).unstack('family').reset_index()
    write(t, 'tableS1_costgap_by_family_median_pct')
    conv = df.groupby(['grid', 'method', 'family']).solved.mean().unstack('family').reset_index()
    write(conv, 'tableS2_convergence_by_family')
    s1 = df[(df.family == 'S1') & df.method.isin(GS) & df.pm_solved & df.solved].copy()
    s1['load_band'] = pd.cut(s1.load_factor, [0, 0.8, 1.0, 1.25], labels=['<0.80 (below training range)', '0.80-1.00', '1.00-1.20+'])
    lb = s1.groupby(['grid', 'method', 'load_band'], observed=True).cost_gap.agg(['count', 'median']).reset_index()
    lb['median'] *= 100; lb = lb.rename(columns={'median': 'cost_gap_median_pct'}); write(lb, 'tableS3_costgap_by_loadband_S1')

def figures(df, ft, per_warm, timing):
    cols = {'MATPOWER-MIPS': '#1f77b4', 'pandapower-PIPS': '#ff7f0e', 'GridSFM-Z0': '#d62728', 'GridSFM-FT10': '#9467bd',
            'GridSFM-FT100': '#8c564b', 'GridSFM-FT1000': '#2ca02c', 'DC-OPF': '#7f7f7f'}
    # Fig 1: cost-gap CDFs
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6), sharey=True)
    for ax, g in zip(axes, GRIDS):
        for m in ['MATPOWER-MIPS', 'pandapower-PIPS', 'DC-OPF'] + GS:
            x = df[(df.grid == g) & (df.method == m) & df.pm_solved & df.solved].cost_gap.dropna().sort_values().values
            if not len(x): continue
            ax.plot(np.maximum(x * 100, 1e-8), np.arange(1, len(x) + 1) / len(x), label=m.replace('GridSFM-', 'GridSFM '), color=cols.get(m), lw=1.2)
        ax.set_xscale('log'); ax.set_xlabel('Cost gap vs. PowerModels/IPOPT (%)'); ax.set_title(GNAME[g]); ax.grid(True, which='both', ls=':', alpha=.4)
    axes[0].set_ylabel('Share of scenarios'); axes[1].legend(loc='lower right', ncol=1)
    savefig(fig, 'fig1_cost_gap_cdf')
    # Fig 2: FT curve
    if ft is not None and len(ft):
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 2.0))
        for g, mk in zip(GRIDS, ['o-', 's--']):
            d = ft[(ft.grid == g) & (ft.subset.isin(['none', 'family-stratified']))].sort_values('n_finetune'); x = d.n_finetune.replace(0, 1)
            for ax, col, lab in zip(axes, ['cost_gap_median_pct', 'V_mae_pu', 'Pg_mae_MW', 'feas_F1'], ['Median cost gap (%)', 'V MAE (p.u.)', 'Pg MAE (MW)', 'Infeasibility F1']):
                ax.plot(x, d[col], mk, label=GNAME[g].split(' (')[0], ms=3.5)
                if col == 'cost_gap_median_pct':
                    ax.fill_between(x, d.ci95_lo_pct, d.ci95_hi_pct, alpha=.2)
                ax.set_xscale('log'); ax.set_xticks([1, 10, 100, 1000]); ax.set_xticklabels(['0', '10', '100', '1k']); ax.set_title(lab, fontsize=8); ax.grid(True, ls=':', alpha=.4)
        for ax in axes: ax.set_xlabel('Fine-tune scenarios')
        axes[0].set_yscale('log'); axes[0].legend()
        fig.tight_layout(); savefig(fig, 'fig2_finetune_curve')
    # Fig 3: warm start
    if per_warm is not None and len(per_warm):
        fig, ax = plt.subplots(figsize=(3.5, 2.4))
        labs = []; data = []
        for (g, c), d in per_warm.groupby(['grid', 'condition']):
            ok = d[d.cold_ok.astype(bool) & d.warm_ok.astype(bool)]
            if len(ok): data.append(ok.speedup.astype(float).values); labs.append(f"{g.replace('ACTIVSg', '')}: {c}")
        ax.boxplot(data, vert=False, tick_labels=labs, showfliers=True); ax.axvline(1, color='k', ls=':', lw=.8)
        ax.set_xscale('log'); ax.set_xlabel('IPOPT speedup t_cold / t_warm'); ax.tick_params(axis='y', labelsize=6.5)
        savefig(fig, 'fig3_warm_start_speedup')
    # Fig 4: speed
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4), sharey=False)
    src = timing if timing is not None and len(timing) else df
    for ax, g in zip(axes, GRIDS):
        data, labs = [], []
        for m in EXACT + ['GridSFM-Z0']:
            t = src[(src.grid == g) & (src.method == m) & src.solved].solve_time.dropna().astype(float).values
            if len(t): data.append(t); labs.append(m.replace('-', '\n', 1))
        ax.boxplot(data, tick_labels=labs, showfliers=False); ax.set_yscale('log'); ax.set_title(GNAME[g]); ax.tick_params(axis='x', labelsize=7)
        ax.grid(True, axis='y', which='both', ls=':', alpha=.4)
    axes[0].set_ylabel('Solve / inference time (s)')
    savefig(fig, 'fig4_speed')
    # Fig 5: violations (GridSFM conditions)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4))
    for ax, (col, lab) in zip(axes, [('bal_P_max_MW', 'Max active-power mismatch (MW)'), ('th_viol_n', 'Overloaded branches (count)')]):
        data, labs = [], []
        for g in GRIDS:
            for m in GS:
                v = df[(df.grid == g) & (df.method == m) & df.solved & df.pm_solved][col].dropna().values
                if len(v): data.append(np.maximum(v, 1e-3)); labs.append(f"{g.replace('ACTIVSg', '')} {m.replace('GridSFM-', '')}")
        if data:
            ax.boxplot(data, tick_labels=labs, showfliers=False); ax.set_yscale('log'); ax.set_title(lab, fontsize=8); ax.tick_params(axis='x', labelsize=6, rotation=60)
    savefig(fig, 'fig5_violations')

def main():
    df = add_refs(load_rows())
    df.to_csv(EV/'rows_all_with_refs.csv', index=False)
    timing = None
    tp = EV/'timing_rows.csv'
    if tp.exists(): timing = pd.read_csv(tp); timing['solved'] = timing.solved.astype(bool)
    counts = df.groupby(['grid', 'method']).agg(rows=('scenario_id', 'count'), converged=('solved', 'sum')).reset_index()
    write(counts, 'table0_counts')
    sp = table_speed(df, timing); acc = table_accuracy(df); vio = table_violations(df); fe = table_feasibility(df)
    ag = table_agreement(df); per_warm, ws = warm_start(); ft = ft_tables(df, acc); tx = table_texas_vs_sc(df); table_by_family(df)
    figures(df, ft, per_warm, timing)
    md = ['# GridSFM benchmark: tables (auto-generated)', '']
    for name in ['table0_counts', 'table1_speed', 'table2a_accuracy', 'table2b_violations', 'table3_feasibility', 'table4_finetune_curve',
                 'table5_solver_agreement', 'table6_warm_start', 'table7_texas_vs_sc', 'tableS1_costgap_by_family_median_pct',
                 'tableS2_convergence_by_family', 'tableS3_costgap_by_loadband_S1']:
        p = TB/f'{name}.md'
        if p.exists(): md += [f'## {name}', p.read_text(), '']
    (EV/'TABLES.md').write_text('\n'.join(md)); print('wrote', EV/'TABLES.md')

if __name__ == '__main__':
    main()
