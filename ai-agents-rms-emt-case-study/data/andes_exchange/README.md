# ANDES transient exchange

ANDES 2.0.0 results for the full ACTIVSg2000 network, exported for the EMT study area. Criteria SHA-256 `ebf6e9fde748c2ea8d937dea150563b79ed912ef121b57d3e5e136005bab191a`.

* `S1_T*_poi.csv`: point-of-interconnection and battery quantities for scenario S1, events T1, T2, T4, T5, T7 and T8.
* `S1_powerflow.json`, `S2_powerflow.json`: bus voltage and angle at t = 0.
* `boundary/`: boundary-branch flow and boundary-bus voltage CSVs for each event, recompressed as `S1_T*_boundary.tar.xz`.
* `member_sha256.txt`: SHA-256 of each CSV and JSON file, including the files inside `boundary/`.

Time column `t_s` is the simulation clock in seconds. The fault is applied at t = 1.0 s, so `t_from_fault_s` is zero at fault inception. The time step is 0.002083 s.

Voltages are per unit on the bus base. Angles are radians. Power is MW and Mvar. A boundary-branch flow is the power entering the retained network (buses within two branches of 6255, plus the project buses 90001 and 90002); positive flow is into the retained network. A tripped line carries zero after its clearing time. Numeric columns have six significant digits. Battery current `Ip` and `Iq` with the `_sys_pu` suffix is on the 100 MVA system base, and with the `_mach_pu` suffix on the 133 MVA battery base. Positive P and Q on the battery are out of the battery. LCL P and Q are the commanded load, positive as consumption. `poi_P_leaving_6255_MW` and `poi_Q_leaving_6255_Mvar` are the power leaving bus 6255 into the in-service project transformer (GSU1 in S1), positive out of the transmission bus into the project. The battery reactive schedule, about 26.4 Mvar, is `bess_Q_Mvar`.

The power-flow JSON is the t = 0 sample of that scenario's T1 trace.
