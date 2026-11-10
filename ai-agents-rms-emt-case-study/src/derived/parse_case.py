from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]  # case-study folder
# Third-party ACTIVSg2000 files (Texas A&M repository) must be placed in data/third_party/ACTIVSg2000/ (not redistributed here)
TP = ROOT / 'data' / 'third_party' / 'ACTIVSg2000'
DER = ROOT / 'data' / 'derived'
import re, shlex, json, math
import pandas as pd
M=open(TP/'case_ACTIVSg2000.m').read()
def block(name):
    s=M[M.index('mpc.%s = ['%name):]; s=s[s.index('[')+1:s.index('];')]
    rows=[]
    for line in s.splitlines():
        line=line.split('%')[0].strip().rstrip(';')
        if line: rows.append([float(x) for x in line.split()])
    return rows
def cell(name):
    s=M[M.index('mpc.%s = {'%name):]; s=s[s.index('{')+1:s.index('};')]
    return re.findall(r"'([^']*)'",s)
bus=pd.DataFrame([r[:13] for r in block('bus')],columns='bus type Pd Qd Gs Bs area Vm Va baseKV zone Vmax Vmin'.split())
bus['name']=cell('bus_name')
gen=pd.DataFrame([r[:10] for r in block('gen')],columns='bus Pg Qg Qmax Qmin Vg mBase status Pmax Pmin'.split())
gen['type']=cell('gentype'); gen['fuel']=cell('genfuel')
br=pd.DataFrame([r[:11] for r in block('branch')],columns='f t r x b rateA rateB rateC ratio angle status'.split())
# aux substations and bus->sub
A=open(TP/'ACTIVSg2000.aux').read()
def auxblock(hdr):
    i=A.index('DATA (%s,'%hdr); j=A.index('{',i); k=A.index('}',j)
    return [shlex.split(l) for l in A[j+1:k].splitlines() if l.strip()]
sub=pd.DataFrame([[int(r[0]),r[1],float(r[3]),float(r[4])] for r in auxblock('Substation')],columns=['sub','subname','lat','lon'])
brec=auxblock('Bus'); b2s={int(r[0]):int(r[13]) for r in brec}
bus['sub']=bus.bus.astype(int).map(b2s)
bus=bus.merge(sub,on='sub',how='left')
bus.to_pickle(TP/'bus.pkl'); gen.to_pickle(TP/'gen.pkl'); br.to_pickle(TP/'branch.pkl')
print('buses',len(bus),'subs',len(sub),'gens',len(gen),'online',int((gen.status>0).sum()),'branches',len(br))
print('kV levels', bus.baseKV.value_counts().to_dict())
print('total load MW', bus.Pd.sum(), 'gen MW', gen[gen.status>0].Pg.sum(), 'Pmax online', gen[gen.status>0].Pmax.sum())
print(gen.groupby('fuel').agg(n=('bus','size'),Pmax=('Pmax','sum'),Pg=('Pg','sum'),online=('status','sum')))
