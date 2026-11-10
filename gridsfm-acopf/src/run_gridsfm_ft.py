#!/usr/bin/env python3
"""Run GridSFM-Open inference on .pyg.json scenarios."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
from gridsfm import load_model, predict

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True, help="CSV sid,pyg_path")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", default="checkpoints/gridsfm_open_v1.1.pt")
    ap.add_argument("--state", default=None, help="fine-tuned state_dict (.pt) loaded on top of --ckpt")
    ap.add_argument("--tool", default="GridSFM-Open")
    ap.add_argument("--threads", type=int, default=0)
    args = ap.parse_args()
    import torch
    if args.threads: torch.set_num_threads(args.threads)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    device = "cpu"
    t0 = time.time()
    model = load_model(args.ckpt, device=device)
    if args.state:
        model.load_state_dict(torch.load(args.state, map_location="cpu"))
        model.eval()
    model_load_s = time.time() - t0
    print(f"model_load_s={model_load_s:.3f} device={device}", flush=True)
    # one discarded warm-up if list non-empty (JIT/caches)
    lines = [ln.strip() for ln in Path(args.list).read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    if lines:
        _, warm_path = lines[0].split(",", 1)
        tw = time.time(); _ = predict(model, warm_path); print(f"warmup_infer_s={time.time()-tw:.3f}", flush=True)
    for line in lines:
        sid, path = line.split(",", 1)
        if (out / f"{sid}.json").exists():
            print(f"GS {sid} skip", flush=True); continue
        print(f"GS {sid}", flush=True)
        try:
            t1 = time.time()
            pred = predict(model, path)
            infer = time.time() - t1
            meta = json.loads(Path(path).read_text())
            baseMVA = float(meta["grid"]["context"][0][0][0])
            gens = meta["grid"]["nodes"]["generator"]
            # cost = cp2*Pg_pu^2 + cp1*Pg_pu + cp0  (PowerModels-scaled coeffs)
            Pg = pred["Pg"].detach().cpu().numpy()
            Qg = pred["Qg"].detach().cpu().numpy()
            cost = 0.0
            for i, g in enumerate(gens):
                cp2, cp1, cp0 = float(g[8]), float(g[9]), float(g[10])
                pg = float(Pg[i])
                cost += cp2 * pg * pg + cp1 * pg + cp0
            bus_ids = meta["metadata"]["bus_id_map"]
            V = pred["V"].detach().cpu().numpy()
            th = pred["theta"].detach().cpu().numpy()
            bus = {str(int(bid)): {"vm": float(V[i]), "va": float(th[i]),
                                   "va_deg": float(th[i] * 180 / 3.141592653589793)}
                   for i, bid in enumerate(bus_ids)}
            gen_ids = meta["metadata"]["gen_id_map"]
            gen = {str(int(gid)): {"pg": float(Pg[i]), "qg": float(Qg[i]),
                                   "pg_mw": float(Pg[i]) * baseMVA,
                                   "qg_mvar": float(Qg[i]) * baseMVA}
                   for i, gid in enumerate(gen_ids)}
            # voltage limit violations from prediction
            vmin = [float(b[2]) for b in meta["grid"]["nodes"]["bus"]]
            vmax = [float(b[3]) for b in meta["grid"]["nodes"]["bus"]]
            v_lo = int(sum(float(V[i]) < vmin[i] - 1e-6 for i in range(len(V))))
            v_hi = int(sum(float(V[i]) > vmax[i] + 1e-6 for i in range(len(V))))
            r = {
                "tool": args.tool, "state": args.state,
                "scenario_id": sid,
                "solved": True,
                "termination_status": "PREDICTED",
                "objective": cost,
                "solve_time": infer,          # inference only (excludes model load)
                "wall_time": infer,
                "model_load_s": model_load_s, # same for all rows; recorded once per process
                "feas": float(pred["feas"]),
                "feas_logit": float(pred["feas_logit"]),
                "baseMVA": baseMVA,
                "bus": bus,
                "gen": gen,
                "n_V_below": v_lo,
                "n_V_above": v_hi,
                "cost_units_note": "cp2/cp1/cp0 act on Pg in per-unit (PowerModels scaling)",
            }
        except Exception as e:
            r = {"tool": args.tool, "state": args.state, "scenario_id": sid, "solved": False,
                 "termination_status": "ERROR", "error": str(e),
                 "objective": None, "solve_time": None, "wall_time": None,
                 "model_load_s": model_load_s}
        (out / f"{sid}.json").write_text(json.dumps(r))
        print(f"  feas={r.get('feas')} cost={r.get('objective')} infer_s={r.get('solve_time')}", flush=True)

if __name__ == "__main__":
    main()
