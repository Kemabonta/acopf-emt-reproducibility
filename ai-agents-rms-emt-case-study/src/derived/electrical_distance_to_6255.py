# DERIVED from saved case tables bus.pkl + branch.pkl (made by parse_case.py from the ACTIVSg2000 files) (ACTIVSg2000 case tables). Not a simulation.
# Shortest series-impedance path (sum of |r+jx| per branch, pu on 100 MVA, in-service branches only) and hop counts from bus 6255.
import pandas as pd, heapq
from pathlib import Path
base = Path(__file__).resolve().parents[2] / 'data' / 'third_party' / 'ACTIVSg2000'
from collections import deque
bus=pd.read_pickle(base/'bus.pkl'); br=pd.read_pickle(base/'branch.pkl')
g={}
for r in br[br.status>0].itertuples():
    z=abs(complex(r.r,r.x)); g.setdefault(int(r.f),[]).append((int(r.t),z)); g.setdefault(int(r.t),[]).append((int(r.f),z))
def dij(s):
    d={s:(0.0,0)}; pq=[(0.0,0,s)]
    while pq:
        c,h,u=heapq.heappop(pq)
        if d[u][0]<c: continue
        for v,z in g.get(u,[]):
            if v not in d or c+z<d[v][0]: d[v]=(c+z,h+1); heapq.heappush(pq,(c+z,h+1,v))
    return d
def bfs(s):
    d={s:0}; q=deque([s])
    while q:
        u=q.popleft()
        for v,_ in g.get(u,[]):
            if v not in d: d[v]=d[u]+1; q.append(v)
    return d
d=dij(6255); b=bfs(6255)
print('bus,name,kV,min_series_abs_z_pu100,hops_on_min_z_path,min_hops')
for k in [3105,5363,5360,6268,6215,6254,6257]:
    r=bus[bus.bus==k].iloc[0]; print(f'{k},{r["name"]},{r.baseKV},{d[k][0]:.4f},{d[k][1]},{b[k]}')
