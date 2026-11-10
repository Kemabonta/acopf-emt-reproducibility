#!/usr/bin/env python3
"""Fine-tune GridSFM-Open on ACTIVSg labeled .pyg.json nested sets (CPU)."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import torch
from torch_geometric.loader import DataLoader
from gridsfm import load_model, finetune_opfdata, predict
from pyg_ft_dataset import PygJsonFTDataset, nested_paths

def collate(batch):
    from gridsfm import batch_data_list
    return batch_data_list(batch)

def eval_cost_mape(model, paths, device="cpu", limit=50):
    gaps = []
    for p in paths[:limit]:
        raw = json.loads(Path(p).read_text())
        ref = raw.get("metadata", {}).get("objective")
        if ref is None or not raw.get("metadata", {}).get("feasible", True):
            # skip unlabeled/infeasible for cost mape
            status = str(raw.get("metadata", {}).get("termination_status", ""))
            if status not in ("LOCALLY_SOLVED", "OPTIMAL", "ALMOST_LOCALLY_SOLVED") and not raw.get("metadata", {}).get("feasible"):
                continue
            if ref is None:
                continue
        out = predict(model, str(p))
        gens = raw["grid"]["nodes"]["generator"]
        Pg = out["Pg"].detach().cpu().numpy()
        cost = 0.0
        for i, g in enumerate(gens):
            cp2, cp1, cp0 = float(g[8]), float(g[9]), float(g[10])
            pg = float(Pg[i])
            cost += cp2 * pg * pg + cp1 * pg + cp0
        gaps.append(abs(cost - float(ref)) / abs(float(ref)))
    if not gaps:
        return None
    import statistics as st
    return {"n": len(gaps), "median_cost_gap": st.median(gaps), "mean_cost_gap": st.mean(gaps)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", required=True)
    ap.add_argument("--labeled-dir", required=True)
    ap.add_argument("--order-csv", required=True, help="manifest/cases order for nesting")
    ap.add_argument("--n-train", type=int, required=True)
    ap.add_argument("--n-val", type=int, default=100)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=1)  # large graphs -> 1 on CPU
    ap.add_argument("--ckpt", default="checkpoints/gridsfm_open_v1.1.pt")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--lr", type=float, default=1e-4)
    args = ap.parse_args()

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    # Nested: take n_train+n_val from order; first n_train train, next n_val val
    # Prefer only feasible labeled files
    all_paths = nested_paths(Path(args.labeled_dir), args.n_train + args.n_val + 200, Path(args.order_csv))
    feas_paths = []
    for p in all_paths:
        meta = json.loads(p.read_text()).get("metadata", {})
        st = str(meta.get("termination_status", ""))
        if meta.get("feasible") or st in ("LOCALLY_SOLVED", "OPTIMAL", "ALMOST_LOCALLY_SOLVED"):
            # require non-zero solution
            sol = json.loads(p.read_text()).get("solution", {}).get("nodes", {}).get("bus") or []
            if sol and (abs(sol[0][1] - 1.0) > 1e-9 or abs(sol[0][0]) > 1e-12 or len(sol) > 1):
                feas_paths.append(p)
    # Fallback: if solution zeros check too strict, use status only
    if len(feas_paths) < args.n_train + min(20, args.n_val):
        feas_paths = []
        for p in all_paths:
            meta = json.loads(p.read_text()).get("metadata", {})
            st = str(meta.get("termination_status", ""))
            if meta.get("feasible") or st in ("LOCALLY_SOLVED", "OPTIMAL", "ALMOST_LOCALLY_SOLVED"):
                feas_paths.append(p)

    train_paths = feas_paths[: args.n_train]
    val_paths = feas_paths[args.n_train : args.n_train + args.n_val]
    print(f"FT{args.n_train}: train={len(train_paths)} val={len(val_paths)} from {len(feas_paths)} feasible labeled")
    if len(train_paths) < max(1, args.n_train // 2):
        raise SystemExit(f"Not enough feasible labeled scenarios: {len(train_paths)}")

    device = "cpu"
    model = load_model(args.ckpt, device=device)
    # zero-shot baseline on val
    zs = eval_cost_mape(model, val_paths or train_paths, device=device)
    print("zero_shot_val", zs)

    train_ds = PygJsonFTDataset(train_paths)
    val_ds = PygJsonFTDataset(val_paths) if val_paths else None
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                              collate_fn=collate, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                            collate_fn=collate, num_workers=0) if val_ds and len(val_ds) else None

    t0 = time.time()
    log = finetune_opfdata(model, train_loader, val_loader, epochs=args.epochs,
                           lr=args.lr, weight_decay=1e-4, grad_clip=5.0,
                           loss_kwargs={})
    # Note: infeas_prob may not be a compute_loss kwarg — use defaults
    elapsed = time.time() - t0
    # pick best epoch by val_cost_mape if present else last
    best = log[-1]
    for e in log:
        key = "val_cost_mape" if "val_cost_mape" in e else None
        if key and e.get(key) is not None:
            if best.get(key) is None or e[key] < best[key]:
                best = e
    ckpt_out = out / f"gridsfm_ft{args.n_train}_{args.grid}.pt"
    torch.save({"model": model.state_dict(), "log": log, "n_train": args.n_train,
                "grid": args.grid, "best": best}, ckpt_out)
    # Also save raw state_dict for load_model compatibility if needed
    torch.save(model.state_dict(), out / f"gridsfm_ft{args.n_train}_{args.grid}_state.pt")
    ft = eval_cost_mape(model, val_paths or train_paths, device=device)
    summary = {"grid": args.grid, "n_train": args.n_train, "n_val": len(val_paths),
               "epochs": args.epochs, "elapsed_s": elapsed, "zero_shot_val": zs,
               "ft_val": ft, "best_epoch": best, "log": log, "ckpt": str(ckpt_out)}
    (out / f"ft{args.n_train}_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: summary[k] for k in summary if k != "log"}, indent=2, default=str))

if __name__ == "__main__":
    main()
