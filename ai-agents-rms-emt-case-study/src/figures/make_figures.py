"""Buchanan unit 1 speed figure (S4 T8, ANDES). Reads only saved data; no simulation is run."""
import csv, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # case-study folder
D = os.path.join(ROOT, "data", "rms_results"); F = os.path.join(ROOT, "figures")
os.makedirs(F, exist_ok=True)
plt.rcParams.update({"font.family":"serif","font.serif":["Liberation Serif","Tinos","DejaVu Serif"],"font.size":7.5,"savefig.dpi":600})
W=3.45
# Buchanan unit 1 speed, S4 T8
rd=lambda n:list(csv.DictReader(open(os.path.join(D,n))))
w=rd("S4_T8_Buchanan_speed_with_project.csv"); n=rd("S4_T8_Buchanan_speed_without_project.csv")
tw=np.array([float(r["time_s"]) for r in w]); sw=np.array([float(r["speed_pu"]) for r in w])
tn=np.array([float(r["time_s"]) for r in n]); sn=np.array([float(r["speed_pu"]) for r in n])
fig,(a1,a2)=plt.subplots(1,2,figsize=(W,1.55),gridspec_kw={"width_ratios":[1.5,1]},sharey=True)
for ax,xmax in ((a1,60),(a2,4.5)):
    ax.plot(tn,sn,color="#2a7f62",lw=0.9,label="Without project"); ax.plot(tw,sw,color="#b23a3a",lw=0.9,label="With project")
    ax.axhline(1.20,color="gray",ls="--",lw=0.7); ax.set_xlim(0,xmax); ax.set_ylim(0.96,1.27)
    ax.plot(tw[-1],sw[-1],"o",ms=3,color="#b23a3a"); ax.grid(alpha=0.3); ax.set_xlabel("Time (s)")
a1.set_ylabel("Speed (pu)"); a1.text(59,1.208,"1.20 pu speed gate",fontsize=6,ha="right",color="gray")
a1.legend(loc="center right",frameon=False,fontsize=6.3)
a2.annotate(f"{sw[-1]:.3f} pu at {tw[-1]:.2f} s",(tw[-1],sw[-1]),xytext=(0.15,1.235),fontsize=6.3,color="#b23a3a")
a2.set_title("0 to 4.5 s",fontsize=6.8); a1.set_title("Full record",fontsize=6.8)
fig.tight_layout(pad=0.3); fig.savefig(os.path.join(F,"fig2_buchanan_speed_S4T8.png")); plt.close(fig)
print("ok", sw[-1], tw[-1], sn.min(), sn.max())
