#!/usr/bin/env python3
"""Train/val Dataset over solved GridSFM .pyg.json files (OPFData-compatible columns).

Our .pyg.json uses the same column widths as OPFData (bus4/gen11/ac9/tr11).
This adapter loads with load_opfdata (strict widths), attaches .y labels from
the solution block, sets feasible from metadata.termination_status, and applies
prepare_for_inference (cycle + Hodge PE) — the schema finetune_opfdata expects.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional
import torch
from torch.utils.data import Dataset
from torch_geometric.data import HeteroData
from gridsfm import load_opfdata, prepare_for_inference

_SOLVED = {"LOCALLY_SOLVED", "OPTIMAL", "ALMOST_LOCALLY_SOLVED", "SUCCESS"}

class PygJsonFTDataset(Dataset):
    def __init__(self, paths: List[Path], transform=True):
        self.paths = [Path(p) for p in paths]
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx: int) -> HeteroData:
        path = self.paths[idx]
        raw = json.loads(path.read_text())
        # Strict OPFData column check — proves adapter compatibility
        data = load_opfdata(path)
        sol = raw.get("solution", {}).get("nodes", {})
        bus_sol = sol.get("bus") or []
        gen_sol = sol.get("generator") or []
        if bus_sol:
            # schema: [va, vm]
            data["bus"].y = torch.tensor(bus_sol, dtype=torch.float32)
        else:
            nb = data["bus"].x.size(0)
            data["bus"].y = torch.zeros(nb, 2)
        if gen_sol and "generator" in data.node_types:
            data["generator"].y = torch.tensor(gen_sol, dtype=torch.float32)
        elif "generator" in data.node_types:
            ng = data["generator"].x.size(0)
            data["generator"].y = torch.zeros(ng, 2)
        status = str(raw.get("metadata", {}).get("termination_status", ""))
        feas = 1 if status in _SOLVED else 0
        # Also accept explicit metadata.feasible
        if "feasible" in raw.get("metadata", {}):
            feas = 1 if raw["metadata"]["feasible"] else 0
        data.feasible = torch.tensor(feas, dtype=torch.long)
        if self.transform:
            data = prepare_for_inference(data)
        return data

def nested_paths(pyg_dir: Path, n: int, seed_order_csv: Optional[Path] = None) -> List[Path]:
    """First n paths in stable manifest order (nested 10 ⊂ 100 ⊂ 1000)."""
    pyg_dir = Path(pyg_dir)
    if seed_order_csv and Path(seed_order_csv).exists():
        ids = []
        for line in Path(seed_order_csv).read_text().splitlines():
            if not line.strip(): continue
            ids.append(line.split(",")[0])
        paths = []
        for sid in ids:
            p = pyg_dir / f"{sid}.pyg.json"
            if p.exists():
                paths.append(p)
            if len(paths) >= n:
                break
        return paths
    paths = sorted(pyg_dir.glob("*.pyg.json"))
    return paths[:n]
