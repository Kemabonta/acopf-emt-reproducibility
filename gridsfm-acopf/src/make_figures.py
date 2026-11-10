"""Redraw the three figures ONLY from saved benchmark data (no model or solver is run).
Inputs: eval/tables/table4_finetune_curve.csv, table2b_violations.csv, warm_start_per_scenario.csv, eval/timing_rows.csv."""
import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FixedFormatter, NullFormatter, FuncFormatter
import pathlib; _H=pathlib.Path(__file__).resolve().parents[1]; R=str(_H/'eval'); OUT=str(_H/'figures')
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','Tinos','Liberation Serif','DejaVu Serif'],
  'font.size':7,'axes.labelsize':7,'axes.titlesize':7,'legend.fontsize':6.5,'xtick.labelsize':6.5,'ytick.labelsize':6.5,
  'axes.linewidth':0.6,'lines.linewidth':1.0,'savefig.dpi':300,'figure.dpi':150})
TXC,SCC='#1f77b4','#d95f02'
GR={'ACTIVSg2000':('Texas',TXC,'o','-'),'ACTIVSg500':('South Carolina',SCC,'s','--')}

# ---------------- Figure 1: 2x2 fine-tuning panels
t4=pd.read_csv(f'{R}/tables/table4_finetune_curve.csv'); t4=t4[t4.subset.isin(['none','family-stratified'])]
t2=pd.read_csv(f'{R}/tables/table2b_violations.csv')
meth={0:'GridSFM-Z0',10:'GridSFM-FT10',100:'GridSFM-FT100',1000:'GridSFM-FT1000'}
xs=[0,1,2,3]; xl=['0','10','100','1,000']
fig,axs=plt.subplots(2,2,figsize=(3.45,3.15))
panels=[('(a) Median cost gap (%)','gap'),('(b) Max. active-power mismatch (MW)','bp'),
        ('(c) Max. reactive-power mismatch (Mvar)','bq'),('(d) Cases with a thermal violation (%)','th')]
for ax,(title,key) in zip(axs.ravel(),panels):
    for g,(nm,c,mk,ls) in GR.items():
        y=[];lo=[];hi=[]
        for n in (0,10,100,1000):
            a=t4[(t4.grid==g)&(t4.n_finetune==n)].iloc[0]; b=t2[(t2.grid==g)&(t2.method==meth[n])].iloc[0]
            if key=='gap': y.append(a.cost_gap_median_pct); lo.append(a.ci95_lo_pct); hi.append(a.ci95_hi_pct)
            elif key=='bp': y.append(b.bal_P_max_MW_med)
            elif key=='bq': y.append(b.bal_Q_max_MVAr_med)
            else: y.append(100*b.share_any_thermal_viol)
        ax.plot(xs,y,marker=mk,ls=ls,color=c,ms=3.2,label=nm)
        if key=='gap': ax.fill_between(xs,lo,hi,color=c,alpha=0.22,lw=0)
    ax.set_title(title,fontsize=6.8,pad=3); ax.set_xticks(xs); ax.set_xticklabels(xl)
    ax.grid(True,ls=':',lw=0.4,alpha=0.6)
    if key in ('gap','bp','bq'): ax.set_yscale('log')
    if key=='gap': ax.set_yticks([0.3,1,3,10,30]); ax.set_yticklabels(['0.3','1','3','10','30']); ax.set_ylim(0.25,70)
    if key=='bp': ax.set_yticks([30,100,300]); ax.set_yticklabels(['30','100','300']); ax.set_ylim(25,900); ax.yaxis.set_minor_formatter(NullFormatter())
    if key=='bq': ax.set_yticks([30,100,300,1000]); ax.set_yticklabels(['30','100','300','1,000']); ax.set_ylim(20,2500); ax.yaxis.set_minor_formatter(NullFormatter())
    if key=='th': ax.set_ylim(0,108); ax.set_yticks([0,25,50,75,100])
    ax.yaxis.set_minor_formatter(NullFormatter())
for ax in axs[1]: ax.set_xlabel('Fine-tuning scenarios',labelpad=1)
axs[1,1].legend(loc='lower left',frameon=True,framealpha=0.9,borderpad=0.3,handlelength=1.8)
fig.tight_layout(pad=0.4,h_pad=0.6,w_pad=0.6)
fig.savefig(f'{OUT}/fig1_finetune_feasibility.png'); plt.close(fig)

# ---------------- Figure 2: timing, two panels (a) Texas (b) South Carolina
tm=pd.read_csv(f'{R}/timing_rows.csv'); tm=tm[tm.solved.astype(bool)]
order=[('PM-IPOPT','Ipopt'),('MATPOWER-MIPS','MIPS'),('pandapower-PIPS','PIPS'),('GridSFM-Z0','GridSFM\nzero-shot')]
fig,axs=plt.subplots(1,2,figsize=(3.45,2.15))
for ax,(g,title,ticks) in zip(axs,[('ACTIVSg2000','(a) Texas, ACTIVSg2000',[1,2,5,10,20]),('ACTIVSg500','(b) South Carolina, ACTIVSg500',[0.1,0.2,0.5,1,2])]):
    data=[tm[(tm.grid==g)&(tm.method==m)].solve_time.astype(float).values for m,_ in order]
    bp=ax.boxplot(data,widths=0.55,showfliers=False,medianprops=dict(color='#d95f02',lw=1.1),boxprops=dict(lw=0.6),whiskerprops=dict(lw=0.6),capprops=dict(lw=0.6))
    ax.set_yscale('log'); ax.set_yticks(ticks); ax.set_yticklabels([('%g'%v) for v in ticks]); ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xticklabels([l for _,l in order],fontsize=5.8)
    ax.set_title(title,fontsize=6.8,pad=3); ax.grid(True,axis='y',ls=':',lw=0.4,alpha=0.6)
axs[0].set_ylabel('Solve or inference time (s)',labelpad=1)
fig.tight_layout(pad=0.4,w_pad=0.8)
fig.savefig(f'{OUT}/fig3_timing.png'); plt.close(fig)

# ---------------- Figure 3: warm-start speedup distributions with geometric means
w=pd.read_csv(f'{R}/tables/warm_start_per_scenario.csv')
lab={'Z0 (pinned)':'Zero-shot','FT1000 (pinned)':'FT1000','GT (pinned)':'GT','DC (pinned)':'DC-OPF',
     'v1 runner: IPOPT warm options, start not applied (control)':'control'}
rows=[]
for g,gn in (('ACTIVSg2000','TX'),('ACTIVSg500','SC')):
    for c in ('Z0 (pinned)','GT (pinned)','FT1000 (pinned)','DC (pinned)','v1 runner: IPOPT warm options, start not applied (control)'):
        d=w[(w.grid==g)&(w.condition==c)]
        d=d[d.cold_ok.astype(bool)&d.warm_ok.astype(bool)]
        if len(d): rows.append((f'{gn} {lab[c]}',d.speedup.astype(float).values))
rows=rows[::-1]
fig,ax=plt.subplots(figsize=(3.45,2.75))
bp=ax.boxplot([r[1] for r in rows],orientation='horizontal',widths=0.55,showfliers=True,flierprops=dict(marker='o',ms=2.2,mfc='none',mec='#555555',mew=0.5),
              medianprops=dict(color='#d95f02',lw=1.1),boxprops=dict(lw=0.6),whiskerprops=dict(lw=0.6),capprops=dict(lw=0.6))
gm=[np.exp(np.log(r[1]).mean()) for r in rows]
ax.plot(gm,range(1,len(rows)+1),'D',color='#1f77b4',ms=3.4,zorder=5,label='Geometric mean (reported in text)')
ax.axvline(1,color='k',ls=':',lw=0.7)
ax.set_xscale('log'); ax.set_xticks([1e-3,1e-2,1e-1,1,10,100]); ax.set_xticklabels(['0.001','0.01','0.1','1','10','100']); ax.xaxis.set_minor_formatter(NullFormatter())
ax.set_yticklabels([r[0] for r in rows],fontsize=6.3)
ax.set_xlabel(r'Ipopt speedup, cold-start time / warm-start time',labelpad=1)
ax.grid(True,axis='x',ls=':',lw=0.4,alpha=0.6)
ax.plot([],[],color='#d95f02',lw=1.1,label='Median'); ax.legend(loc='lower right',fontsize=5.8,frameon=True,framealpha=0.9,borderpad=0.3)
fig.tight_layout(pad=0.4)
fig.savefig(f'{OUT}/fig2_warm_start.png'); plt.close(fig)
print('ok'); print([(r[0],len(r[1]),round(g,3)) for r,g in zip(rows,gm)])
