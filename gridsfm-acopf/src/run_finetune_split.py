#!/usr/bin/env python3
"""CPU fine-tune on family-stratified nested splits (full/ft_splits/<grid>_split.json).
Same recipe as run_finetune_simple.py (10 epochs, AdamW lr 1e-4, wd 1e-4, batch 1, clip 5,
best epoch by validation median cost gap); adds a fixed torch seed and a common validation set."""
from __future__ import annotations
import argparse, json, time, sys
from pathlib import Path
import torch
from torch_geometric.loader import DataLoader
from gridsfm import load_model, batch_data_list, predict
from gridsfm.loss import compute_loss
from gridsfm.eval import eval_pass
from pyg_ft_dataset import PygJsonFTDataset

def collate(batch):
    return batch_data_list(batch)

def cost_gap(model, paths, limit=40):
    import statistics as st
    gaps=[]
    for p in paths[:limit]:
        raw=json.loads(Path(p).read_text())
        ref=raw.get('metadata',{}).get('objective')
        if ref is None: continue
        stt=str(raw.get('metadata',{}).get('termination_status',''))
        if not (raw.get('metadata',{}).get('feasible') or stt in ('LOCALLY_SOLVED','OPTIMAL','ALMOST_LOCALLY_SOLVED')):
            continue
        out=predict(model, str(p))
        Pg=out['Pg'].detach().cpu().numpy(); cost=0.0
        for i,g in enumerate(raw['grid']['nodes']['generator']):
            cost += float(g[8])*float(Pg[i])**2 + float(g[9])*float(Pg[i]) + float(g[10])
        gaps.append(abs(cost-float(ref))/abs(float(ref)))
    if not gaps: return None
    return {'n':len(gaps),'median_cost_gap':st.median(gaps),'mean_cost_gap':st.mean(gaps)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--grid', required=True)
    ap.add_argument('--labeled-dir', required=True)
    ap.add_argument('--split', required=True)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--threads', type=int, default=0)
    ap.add_argument('--n-train', type=int, required=True)
    ap.add_argument('--n-val', type=int, default=20)
    ap.add_argument('--epochs', type=int, default=10)
    ap.add_argument('--ckpt', default='checkpoints/gridsfm_open_v1.1.pt')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--lr', type=float, default=1e-4)
    args=ap.parse_args()
    out=Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(args.seed)
    if args.threads: torch.set_num_threads(args.threads)
    split=json.loads(Path(args.split).read_text())
    lab=Path(args.labeled_dir)
    train_paths=[lab/f'{s}.pyg.json' for s in split['train_order'][:args.n_train]]
    # validation: family-stratified hold-out from the same pool (next n_val ids after the training prefix);
    # when the pool is used up (FT1000) fall back to the post-pool validation list.
    hold=split['train_order'][args.n_train:args.n_train+args.n_val]
    val_ids=hold if len(hold)>=args.n_val else split['val'][:args.n_val]
    val_paths=[lab/f'{s}.pyg.json' for s in val_ids]
    print(f'FT{args.n_train} train={len(train_paths)} val={len(val_paths)}', flush=True)
    if len(train_paths)<max(1,args.n_train//2):
        raise SystemExit('not enough labeled feasible')
    device='cpu'
    model=load_model(args.ckpt, device=device)
    zs=cost_gap(model, val_paths or train_paths)
    print('zero_shot', zs, flush=True)
    train_loader=DataLoader(PygJsonFTDataset(train_paths), batch_size=1, shuffle=True, collate_fn=collate, num_workers=0)
    val_loader=DataLoader(PygJsonFTDataset(val_paths), batch_size=1, shuffle=False, collate_fn=collate, num_workers=0) if val_paths else None
    opt=torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    log=[]; t0=time.time(); best=None
    for ep in range(args.epochs):
        model.train(); sum_loss=0.0; n=0; ep0=time.time()
        for bi, batch in enumerate(train_loader):
            batch=batch.to(device)
            model(batch)
            loss, parts=compute_loss(batch)
            if not torch.isfinite(loss):
                print(f'ep{ep} b{bi} nonfinite skip', flush=True); continue
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step(); sum_loss+=float(loss.item()); n+=1
            if bi % 5 == 0:
                print(f'ep{ep} b{bi}/{len(train_loader)} loss={float(loss.item()):.4f} t={time.time()-ep0:.1f}s', flush=True)
        entry={'epoch':ep,'train_loss': (sum_loss/n if n else float('nan')), 'epoch_s': time.time()-ep0, 'elapsed_s': time.time()-t0}
        if val_loader is not None:
            model.eval()
            # lightweight val cost mape
            entry['val']=cost_gap(model, val_paths)
            print(f'ep{ep} done train_loss={entry["train_loss"]:.4f} val={entry["val"]}', flush=True)
            if best is None or (entry['val'] and best.get('val') and entry['val']['median_cost_gap'] < best['val']['median_cost_gap']):
                best=entry
                tmp=out/f'best_state.pt.tmp'; torch.save(model.state_dict(), tmp); tmp.replace(out/f'best_state.pt')
        else:
            print(f'ep{ep} done train_loss={entry["train_loss"]:.4f}', flush=True)
            best=entry
        log.append(entry)
    tmp=out/f'gridsfm_ft{args.n_train}_{args.grid}_state.pt.tmp'; torch.save(model.state_dict(), tmp); tmp.replace(out/f'gridsfm_ft{args.n_train}_{args.grid}_state.pt')
    ft=cost_gap(model, val_paths or train_paths)
    summary={'val_ids':[p.name.replace('.pyg.json','') for p in val_paths],'split':args.split,'seed':args.seed,'threads':torch.get_num_threads(),'train_ids':[p.stem.replace('.pyg','') for p in train_paths][:1000],'grid':args.grid,'n_train':args.n_train,'n_val':len(val_paths),'epochs':args.epochs,
             'elapsed_s':time.time()-t0,'zero_shot_val':zs,'ft_val':ft,'best':best,'log':log}
    (out/f'ft{args.n_train}_summary.json').write_text(json.dumps(summary, indent=2, default=str))
    print('DONE', json.dumps({k:summary[k] for k in summary if k!='log'}, default=str), flush=True)

if __name__=='__main__':
    main()
