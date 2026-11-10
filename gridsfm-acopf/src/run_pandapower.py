#!/usr/bin/env python3
"""Run pandapower OPF on scenario list (sid,path CSV)."""
from __future__ import annotations
import argparse, json, time, warnings, math
from pathlib import Path
import numpy as np
import pandapower as pp
from pandapower.converter.matpower import from_mpc

warnings.filterwarnings("ignore")

def _bus_id(net, idx):
    if "name" in net.bus.columns:
        val = net.bus.at[idx, "name"]
        try:
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                return int(val)
        except Exception:
            pass
    return int(idx)

def solve_one(path: Path) -> dict:
    t0 = time.time()
    net = from_mpc(str(path), f_hz=60)
    net.bus["min_vm_pu"] = 0.90
    net.bus["max_vm_pu"] = 1.10
    t_build = time.time() - t0
    t1 = time.time()
    err = None
    try:
        pp.runopp(net, verbose=False, calculate_voltage_angles=True)
        ok = True
        status = "SUCCESS"
        cost = float(net.res_cost)
    except Exception as e:
        ok = False
        status = f"FAIL:{type(e).__name__}"
        cost = float("nan")
        err = str(e)
    wall = time.time() - t1
    bus = {}
    if ok and hasattr(net, "res_bus"):
        for idx, row in net.res_bus.iterrows():
            bus[str(_bus_id(net, idx))] = {"vm": float(row.vm_pu), "va_deg": float(row.va_degree)}
    gen = {}
    if ok:
        for idx, row in net.res_gen.iterrows():
            gen[f"gen_{idx}"] = {"pg": float(row.p_mw), "qg": float(row.q_mvar)}
        for idx, row in net.res_ext_grid.iterrows():
            gen[f"ext_{idx}"] = {"pg": float(row.p_mw), "qg": float(row.q_mvar)}
    out = {
        "tool": "pandapower",
        "solved": ok,
        "termination_status": status,
        "objective": cost if ok else None,
        "solve_time": wall,
        "wall_time": wall,
        "build_time": t_build,
        "bus": bus,
        "gen": gen,
        "n_line": int(len(net.line)),
        "n_trafo": int(len(net.trafo)),
        "n_impedance": int(len(net.impedance)),
        "note": "Transformers with TAP in {0,1} and voltage change become impedance in from_mpc",
    }
    if err:
        out["error"] = err
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    for line in Path(args.list).read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        sid, path = line.split(",", 1)
        if (out / f"{sid}.json").exists():
            print(f"PP {sid} skip", flush=True); continue
        print(f"PP {sid}", flush=True)
        try:
            r = solve_one(Path(path))
        except Exception as e:
            r = {"solved": False, "termination_status": "ERROR", "error": str(e),
                 "objective": None, "solve_time": None, "wall_time": None, "tool": "pandapower"}
        r["scenario_id"] = sid
        (out / f"{sid}.json").write_text(json.dumps(r))
        print(f"  status={r.get('termination_status')} obj={r.get('objective')} t={r.get('solve_time')}", flush=True)

if __name__ == "__main__":
    main()
