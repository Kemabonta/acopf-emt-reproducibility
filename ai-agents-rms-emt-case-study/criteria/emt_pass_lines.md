# EMT locked pass lines and tolerances

These are the EMT pass lines and tolerances that were fixed before any EMT fault run. The SHA-256 of the EMT criteria file at that time is `66c1cc215fc34a006407456564c4be6b8e9d11ae5d804e91de5922bae4fcdef6`. The criteria file itself is not included.

## Pass lines

```
5. Locked criteria
Locked before any fault run. SHA-256 66c1cc215fc34a006407456564c4be6b8e9d11ae5d804e91de5922bae4fcdef6. The pass lines were not loosened.
Measure voltage as fundamental-frequency RMS, per phase and positive-sequence, over a 1-cycle window. Apply the voltage criteria to the minimum phase-to-ground or phase-to-phase RMS (PRC-029-1 Attachment 1 note 5). Measure the LCL at 6255 (Service Delivery Point/POIB), and the BESS at the POIB and at the main-transformer high side. BESS: ERCOT NOG 2.9.1.1 Table B (V>1.20 may trip; 1.10-1.20 for 1.0 s; 0.90-1.10 continuous; 0.70-0.90 for 6.0 s; 0.50-0.70 for 3.0 s; 0.25-0.50 for 1.2 s; 0.095625-0.25 for (V+0.084375)/0.5625 s; <0.095625 for 0.32 s; cumulative over 10 s). No momentary cessation in the mandatory region. Current blocking is allowed only in the permissive region (<0.10 pu, PRC-029-1 R2.3), and current exchange must restart within <=5 cycles of leaving it. Active power is restored within <=1.0 s (NOG 2.9.1.1(4); PRC-029-1 R2.5). Reactive current is injected on the affected phases during symmetrical and asymmetrical faults (PRC-029-1 R2.2). No PLL loss-of-synchronism trip. IEEE 2800-2022 cl. 7 dynamic reactive-current response: report rise and settling times. The numeric targets (step response <=2.5 cycles, settling <=4 cycles) are taken from secondary summaries and must be confirmed against a licensed copy before they are used for PASS/FAIL. Until then, report them as INFORMATIONAL. LCL: ERCOT NOG 2.15 Table A (V>1.20 may trip; 1.10-1.20 for 1.0 s; 0.90-1.10 continuous; 0.80-0.90 for 2.0 s; 0.50-0.80 for 0.5 s; 0.35-0.50 for 0.25 s; <0.35 for 0.15 s). It must stay connected and return to >=90% of pre-disturbance P within 2 s of V>0.9 pu. If it uses load transfer, it begins returning within <=0.25 s and reaches >=90% within <=0.5 s. Current <=150% of maximum normal current for <=0.5 s. Survives six sags within 90 s. Over-voltage trip is allowed only above 1.08 pu lasting >=5 s (before 2028, 2.15(3)(f)). System (reduced model only): voltage at retained buses >100 kV recovers to >=0.90 pu within 5 s of clearing (P1) or 10 s (delayed clearing), per ERCOT PG 4.1.1.5. No sustained oscillation: any mode in the 0.2-2 Hz band damped >=3% (PG 4.1.1.6). Report and flag any sub-synchronous or control interaction (5-55 Hz). Verdicts: PASS / FAIL / NOT APPLICABLE / INFORMATIONAL, with margins.
```

## Cross-tool tolerances

```
2. Tolerances
Section 9.1, locked with the pass lines. SHA-256 66c1cc215fc34a006407456564c4be6b8e9d11ae5d804e91de5922bae4fcdef6. These tolerances were not loosened.
All quantities are computed by the common post-processor from each tool's raw traces, at the POI (6255 / POIB) unless stated. Agree means |DPsim − ParaEMT| within the tolerance. Pre-fault POI V (RMS, pos-seq): ±0.005 pu. Pre-fault BESS and LCL P, Q: ±1% of rating (±1.3 MW / Mvar). During-fault POI RMS V, minimum phase and pos-seq, mean over the fault window excluding the first and last cycle: ±0.03 pu. Fault-window negative-sequence V (unbalanced cases): ±0.02 pu. Peak instantaneous phase current, BESS terminals and 6255 fault-side line: ±10%. BESS RMS current during fault (Id, Iq separately, mean over the window above): ±0.05 pu on 140 MVA. LCL current peak (vs the 150% limit): ±5% of maximum normal current. Post-clearing overvoltage peak (RMS, 1-cycle): ±0.02 pu. Voltage recovery time (clearing to V first ≥ 0.90 pu and stays ≥ 0.90 pu): ±1 cycle (16.7 ms) or ±10%, whichever is larger. BESS P recovery time (to 90% of pre-fault P): ±0.05 s or ±10%, whichever is larger. LCL return time (to 90% of pre-disturbance P) and UPS transfer instants: ±0.05 s. Number of UPS transfers / counting-scheme lockouts (E7): exact match. Criterion verdict (PASS/FAIL/NA/INFO) and the sign of each margin: exact match. These tolerances are fixed before any run and are never loosened. A quantity outside its tolerance is a disagreement, even if both verdicts match.
Quantity || Tolerance
Pre-fault POI V (RMS, pos-seq) || ±0.005 pu
Pre-fault BESS and LCL P, Q || ±1% of rating (±1.3 MW / Mvar)
During-fault POI RMS V: minimum phase and pos-seq, mean over the fault window excluding the first and last cycle || ±0.03 pu
Fault-window negative-sequence V (unbalanced cases) || ±0.02 pu
Peak instantaneous phase current, BESS terminals and 6255 fault-side line || ±10%
BESS RMS current during fault (Id, Iq separately, mean over the window above) || ±0.05 pu on 140 MVA
LCL current peak (vs the 150% limit) || ±5% of maximum normal current
Post-clearing overvoltage peak (RMS, 1-cycle) || ±0.02 pu
Voltage recovery time (clearing → V first ≥ 0.90 pu and stays ≥ 0.90 pu) || ±1 cycle (16.7 ms) or ±10%, whichever is larger
BESS P recovery time (to 90% of pre-fault P) || ±0.05 s or ±10%, whichever is larger
LCL return time (to 90% of pre-disturbance P) and UPS transfer instants || ±0.05 s
Number of UPS transfers / counting-scheme lockouts (E7) || exact match
Criterion verdict (PASS/FAIL/NA/INFO) and the sign of each margin || exact match
```
