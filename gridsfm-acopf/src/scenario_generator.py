#!/usr/bin/env python3
"""Seeded scenario generator for GridSFM vs AC-OPF benchmark.

Designed for pilot (20/grid) and full runs (500/grid + fine-tune 10/100/1000).
Master seeds from plan v1.1:
  Texas test 20261104, Texas FT 20261105, control test 20261106, control FT 20261107.
Per-scenario seed = first 8 bytes of SHA-256(master_seed, family, index) as uint64.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

FAMILIES_FULL = {
    "S1": 125,  # load scaling
    "S2": 75,   # per-bus perturbation
    "S3": 100,  # N-1 branch
    "S4": 50,   # N-1 gen
    "S5": 50,   # rating derates
    "S6": 75,   # renewable/hydro
    "S7": 25,   # combined stress
}
# Pilot 20 = proportional-ish coverage of all families
FAMILIES_PILOT = {"S1": 5, "S2": 3, "S3": 4, "S4": 2, "S5": 2, "S6": 3, "S7": 1}
# 1100 = 1000 train + 100 val (nested 10 ⊂ 100 ⊂ 1000)
FAMILIES_FT = {"S1": 275, "S2": 165, "S3": 220, "S4": 110, "S5": 110, "S6": 165, "S7": 55}

MASTER_SEEDS = {
    ("texas", "test"): 20261104,
    ("texas", "finetune"): 20261105,
    ("control", "test"): 20261106,
    ("control", "finetune"): 20261107,
}


def scenario_seed(master: int, family: str, index: int) -> int:
    h = hashlib.sha256(f"{master}|{family}|{index}".encode()).digest()
    return int.from_bytes(h[:8], "little", signed=False)


def parse_mpc(path: Path) -> dict:
    """Minimal MATPOWER case parser for bus/gen/branch/gencost matrices."""
    text = path.read_text()
    base = float(re.search(r"mpc\.baseMVA\s*=\s*([0-9.eE+-]+)", text).group(1))

    def matrix(name: str) -> np.ndarray:
        m = re.search(rf"mpc\.{name}\s*=\s*\[(.*?)\];", text, re.S)
        if not m:
            return np.zeros((0, 0))
        rows = []
        for line in m.group(1).splitlines():
            s = line.strip()
            if not s or s.startswith("%"):
                continue
            s = s.rstrip(";")
            parts = re.split(r"\s+", s)
            rows.append([float(p) for p in parts if p])
        if not rows:
            return np.zeros((0, 0))
        width = max(len(r) for r in rows)
        arr = np.zeros((len(rows), width), dtype=float)
        for i, r in enumerate(rows):
            arr[i, : len(r)] = r
        return arr

    return {
        "text": text,
        "baseMVA": base,
        "bus": matrix("bus"),
        "gen": matrix("gen"),
        "branch": matrix("branch"),
        "gencost": matrix("gencost"),
    }


def write_matrix(name: str, arr: np.ndarray) -> str:
    lines = [f"mpc.{name} = ["]
    for row in arr:
        vals = "\t".join(f"{v:.10g}" for v in row)
        lines.append(f"\t{vals};")
    lines.append("];")
    return "\n".join(lines)


def replace_matrix(text: str, name: str, arr: np.ndarray) -> str:
    block = write_matrix(name, arr)
    return re.sub(rf"mpc\.{name}\s*=\s*\[.*?\];", block, text, count=1, flags=re.S)


def parse_genfuel(path: Path):
    text = path.read_text()
    m = re.search(r"mpc\.genfuel\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        return None
    return re.findall(r"'([^']+)'", m.group(1))


def classify_gens(gen: np.ndarray, bus: np.ndarray, grid: str, fuels=None) -> Dict[str, np.ndarray]:
    """Tag generators from mpc.genfuel when available; else heuristic fallback."""
    n = gen.shape[0]
    if fuels is not None and len(fuels) == n:
        mapping = {
            'wind': 'wind', 'solar': 'solar', 'hydro': 'hydro', 'synccond': 'thermal',
            'nuclear': 'thermal', 'coal': 'thermal', 'ng': 'thermal', 'oil': 'thermal',
            'geothermal': 'thermal', 'biomass': 'thermal', 'other': 'thermal',
        }
        tags = np.array([mapping.get(str(f).lower(), 'thermal') for f in fuels], dtype=object)
        renew = np.isin(tags, ['wind', 'solar', 'hydro'])
        return {"tags": tags, "renew_mask": renew}
    pmax = gen[:, 8]
    pmin = gen[:, 9]
    status = gen[:, 7]
    renew = (np.isclose(pmin, 0.0) & (status > 0) & (pmax > 0))
    tags = np.array(["thermal"] * n, dtype=object)
    if grid == "texas":
        idx = np.where(renew)[0]
        if len(idx):
            order = idx[np.argsort(-pmax[idx])]
            wind_n = min(87, len(order))
            tags[order[:wind_n]] = "wind"
            rem = order[wind_n:]
            if len(rem):
                hydro_cut = max(1, int(0.6 * len(rem)))
                tags[rem[:hydro_cut]] = "hydro"
                tags[rem[hydro_cut:]] = "solar"
    else:
        idx = np.where(renew)[0]
        if len(idx):
            order = idx[np.argsort(-pmax[idx])]
            if len(order) == 1:
                tags[order[0]] = "hydro"
            else:
                tags[order[:-1]] = "hydro"
                tags[order[-1]] = "solar"
    return {"tags": tags, "renew_mask": renew}


@dataclass
class ScenarioMeta:
    scenario_id: str
    grid: str
    family: str
    index: int
    seed: int
    params: dict
    case_file: str
    sha256: str


def apply_scenario(mpc: dict, grid: str, family: str, rng: np.random.Generator, gen_info: dict) -> Tuple[dict, dict]:
    bus = mpc["bus"].copy()
    gen = mpc["gen"].copy()
    branch = mpc["branch"].copy()
    params = {"family": family}

    # Ensure angmin/angmax already +/-60 in master; keep them.
    branch[:, 11] = -60.0
    branch[:, 12] = 60.0

    pd0 = bus[:, 2].copy()
    qd0 = bus[:, 3].copy()

    if family == "S1":
        # Milder load range for feasibility under fixed limits (plan allowed 0.8-1.2 training-like)
        g = float(rng.uniform(0.85, 1.10))
        jitter = rng.uniform(0.95, 1.05, size=pd0.shape)
        bus[:, 2] = pd0 * g * jitter
        # constant PF
        with np.errstate(divide="ignore", invalid="ignore"):
            pf = np.ones_like(pd0)
            mask = np.abs(pd0) > 1e-9
            pf[mask] = qd0[mask] / pd0[mask]
        bus[:, 3] = bus[:, 2] * pf
        params.update({"global_load": g, "jitter_mean": float(jitter.mean())})

    elif family == "S2":
        g = float(rng.uniform(0.95, 1.05))
        jitter = rng.normal(1.0, 0.08, size=pd0.shape)
        jitter = np.clip(jitter, 0.85, 1.15)
        bus[:, 2] = pd0 * g * jitter
        with np.errstate(divide="ignore", invalid="ignore"):
            pf = np.ones_like(pd0)
            mask = np.abs(pd0) > 1e-9
            pf[mask] = qd0[mask] / pd0[mask]
        bus[:, 3] = bus[:, 2] * pf
        params.update({"global_load": g})

    elif family == "S3":
        # N-1 branch outage with connectivity check (networkx); retry up to 80 draws
        import networkx as nx
        status = branch[:, 10] > 0
        cand = np.where(status)[0]
        rate = branch[cand, 5]
        w = 1.0 / np.maximum(rate, 1.0)
        w = w / w.sum()
        # Build base graph of in-service branches
        def connected(br):
            G = nx.Graph()
            buses = set(bus[:, 0].astype(int).tolist())
            G.add_nodes_from(buses)
            for row in br:
                if row[10] > 0:
                    G.add_edge(int(row[0]), int(row[1]))
            # ignore islands of size 0; require single component on energized buses with degree>0 or load/gen
            return nx.is_connected(G) if G.number_of_nodes() > 0 and G.number_of_edges() > 0 else False
        picked = None
        for _ in range(80):
            k = int(rng.choice(cand, p=w))
            branch2 = branch.copy()
            branch2[k, 10] = 0
            if connected(branch2):
                picked = k
                branch = branch2
                break
        if picked is None:
            # fall back: no outage (record skipped) — keeps scenario feasible rather than invalid
            params["outaged_branch_row"] = None
            params["outage_skipped"] = True
        else:
            params["outaged_branch_row"] = int(picked)
            params["outaged_fbus"] = int(mpc["branch"][picked, 0])
            params["outaged_tbus"] = int(mpc["branch"][picked, 1])

    elif family == "S4":
        status = gen[:, 7] > 0
        # exclude slack: bus type 3
        slack_buses = set(bus[bus[:, 1] == 3, 0].astype(int).tolist())
        cand = [i for i in np.where(status)[0] if int(gen[i, 0]) not in slack_buses]
        pmax = np.array([gen[i, 8] for i in cand])
        w = pmax / pmax.sum()
        k = int(rng.choice(cand, p=w))
        gen[k, 7] = 0
        params["outaged_gen_row"] = k
        params["outaged_gen_bus"] = int(gen[k, 0])

    elif family == "S5":
        status = branch[:, 10] > 0
        cand = np.where(status)[0]
        n_derate = max(1, int(0.05 * len(cand)))  # 5% of in-service branches
        chosen = rng.choice(cand, size=n_derate, replace=False)
        severe = rng.random() < 0.15
        lo, hi = (0.75, 0.90) if severe else (0.88, 0.98)
        factors = rng.uniform(lo, hi, size=len(chosen))
        for i, f in zip(chosen, factors):
            for c in (5, 6, 7):  # rateA/B/C
                if branch[i, c] > 0:
                    branch[i, c] *= f
        params.update({"n_derated": int(n_derate), "severe": bool(severe), "factor_mean": float(factors.mean())})

    elif family == "S6":
        tags = gen_info["tags"]
        if grid == "texas":
            # wind CF per "area": use gen bus area from bus matrix
            bus_area = {int(b[0]): int(b[6]) for b in bus}
            areas = sorted(set(bus_area.get(int(g[0]), 1) for g, t in zip(gen, tags) if t == "wind"))
            area_cf = {a: float(rng.uniform(0.30, 1.0)) for a in areas}
            for i, t in enumerate(tags):
                if t == "wind" and gen[i, 7] > 0:
                    a = bus_area.get(int(gen[i, 0]), 1)
                    cf = area_cf[a] * float(rng.uniform(0.90, 1.10))
                    cf = float(np.clip(cf, 0.0, 1.0))
                    gen[i, 8] = gen[i, 8] * cf  # scale Pmax
                    gen[i, 9] = 0.0
                elif t == "solar" and gen[i, 7] > 0:
                    cf = float(rng.uniform(0.20, 1.0))
                    gen[i, 8] *= cf
                    gen[i, 9] = 0.0
            params["wind_area_cf"] = area_cf
        else:
            for i, t in enumerate(tags):
                if t == "hydro" and gen[i, 7] > 0:
                    avail = float(rng.uniform(0.70, 1.0))
                    gen[i, 8] *= avail
                    gen[i, 9] = 0.0
                elif t == "solar" and gen[i, 7] > 0:
                    cf = float(rng.uniform(0.20, 1.0))
                    gen[i, 8] *= cf
                    gen[i, 9] = 0.0

    elif family == "S7":
        # Milder combined stress — still aims for some infeasibles (~10-30% overall)
        g = float(rng.uniform(1.02, 1.10))
        bus[:, 2] = pd0 * g
        bus[:, 3] = qd0 * g
        status = branch[:, 10] > 0
        cand = np.where(status)[0]
        k = None
        if rng.random() < 0.5 and len(cand):
            # prefer light branch + connectivity
            import networkx as nx
            rate = branch[cand, 5]
            w = 1.0 / np.maximum(rate, 1.0); w = w / w.sum()
            for _ in range(40):
                kk = int(rng.choice(cand, p=w))
                br2 = branch.copy(); br2[kk, 10] = 0
                G = nx.Graph(); G.add_nodes_from(bus[:,0].astype(int).tolist())
                for row in br2:
                    if row[10] > 0: G.add_edge(int(row[0]), int(row[1]))
                if nx.is_connected(G):
                    k = kk; branch = br2; break
        remain = np.where(branch[:, 10] > 0)[0]
        n_derate = max(1, int(0.05 * len(remain)))
        chosen = rng.choice(remain, size=n_derate, replace=False)
        factors = rng.uniform(0.85, 0.98, size=len(chosen))
        for i, f in zip(chosen, factors):
            for c in (5, 6, 7):
                if branch[i, c] > 0:
                    branch[i, c] *= f
        params.update({"global_load": g, "outaged_branch_row": k, "n_derated": int(n_derate)})

    else:
        raise ValueError(family)

    out = dict(mpc)
    out["bus"] = bus
    out["gen"] = gen
    out["branch"] = branch
    return out, params


def generate(grid_key: str, master_case: Path, out_dir: Path, mode: str = "pilot", split: str = "test") -> List[ScenarioMeta]:
    grid = "texas" if "2000" in grid_key or grid_key == "texas" else "control"
    if mode == "pilot":
        families = FAMILIES_PILOT
    elif mode == "finetune":
        families = FAMILIES_FT
    else:
        families = FAMILIES_FULL
    master_seed = MASTER_SEEDS[(grid, split)]
    out_dir.mkdir(parents=True, exist_ok=True)
    mpc0 = parse_mpc(master_case)
    fuels = parse_genfuel(master_case)
    gen_info = classify_gens(mpc0["gen"], mpc0["bus"], grid, fuels=fuels)

    metas: List[ScenarioMeta] = []
    for family, count in families.items():
        for idx in range(count):
            seed = scenario_seed(master_seed, family, idx)
            rng = np.random.default_rng(seed)
            mpc, params = apply_scenario(mpc0, grid, family, rng, gen_info)
            sid = f"{grid_key}_{family}_{idx:04d}"
            # function name must match filename stem for Octave loadcase
            fname = f"{sid}.m"
            case_path = out_dir / fname
            text = mpc0["text"]
            # rewrite function name line if present
            text = re.sub(r"function\s+mpc\s*=\s*\w+", f"function mpc = {sid}", text)
            text = replace_matrix(text, "bus", mpc["bus"])
            text = replace_matrix(text, "gen", mpc["gen"])
            text = replace_matrix(text, "branch", mpc["branch"])
            # keep gencost
            case_path.write_text(text)
            sha = hashlib.sha256(case_path.read_bytes()).hexdigest()
            meta = ScenarioMeta(
                scenario_id=sid,
                grid=grid_key,
                family=family,
                index=idx,
                seed=seed,
                params=params,
                case_file=str(case_path),
                sha256=sha,
            )
            metas.append(meta)

    manifest = out_dir / "manifest.csv"
    with manifest.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["scenario_id", "grid", "family", "index", "seed", "case_file", "sha256", "params_json"],
        )
        w.writeheader()
        for m in metas:
            w.writerow(
                {
                    "scenario_id": m.scenario_id,
                    "grid": m.grid,
                    "family": m.family,
                    "index": m.index,
                    "seed": m.seed,
                    "case_file": m.case_file,
                    "sha256": m.sha256,
                    "params_json": json.dumps(m.params, sort_keys=True),
                }
            )
    (out_dir / "manifest.json").write_text(json.dumps([asdict(m) for m in metas], indent=2))
    print(f"Wrote {len(metas)} scenarios to {out_dir} (master_seed={master_seed})")
    return metas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True, choices=["ACTIVSg2000", "ACTIVSg500"])
    ap.add_argument("--master", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--mode", default="pilot", choices=["pilot", "full", "finetune"])
    ap.add_argument("--split", default="test", choices=["test", "finetune"])
    args = ap.parse_args()
    generate(args.grid, args.master, args.out, args.mode, args.split)


if __name__ == "__main__":
    main()
