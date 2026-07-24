# Storage-hybrid debug tracker

Living tracker for storage-hybrid bugs: status, evidence, and validation runs.
Last updated: 2026-07-24 (fix pass complete; nlval6 GREEN — all solves optimal,
checker 33/33, wrapper opres live, RTE 0.999, mandate floor exact at 2035).

**2026-07-24 fix pass (validated in nlval6_mk_boak_lo):**
- SH-11 FIXED: CSP carve-out restored in base VOM (c_supplyobjective.gms:168) + gen_objcoef replica (e_report.gms).
- SH-12 FIXED: `ramprate(wrapper)` = storage component's (b_inputs.gms ~5036); dead `ramprate_storage_hybrid` param removed; reserve_frac follows.
- SH-29 FIXED: `storage_eff(wrapper)` = plant-charging efficiency (reg-loss terms no longer bill standalone TES RTE).
- SH-30 FIXED: eq_storage_opres credits reactor headroom (avail·CAP − GEN_PLANT) as reserve backing for dispatchable wrappers.
- SH-31 FIXED per user rule: TES takes CSP's cost_opres (reg 3.24 $/MWh — NOT 0; flagged to user); wrappers take storage component's cost unconditionally.
- SH-32 FIXED (user: both gross): PTC and REC/CES credited on GEN_PLANT for wrappers; TES plant-charge eff 0.99 → 0.999.
- SH-10 FIXED: `reg_cap_cost_diff(wrapper,r)` inherited from gen tech in GAMS (b_inputs, next to financing_risk_mult); cloner skips reg_cap_cost_diff*/incentives* (incl. root names; fixed `ref_`→`reg_` skip-list typo that let the wide file be column-cloned). Post-launch discovery: the wide run-copy is actually named `regional_cap_cost_diff.csv` — added to the skip list after nlval6 launched, so nlval6's CSV still carries the 528 legacy nuclear-wrapper rows; harmless because the GAMS inheritance overwrites/fills all 8 wrappers (verify SMR-wrapper parity in the checklist).
- SH-28 FIXED: `tc_phaseout_mult_t(wrapper)` inherited from gen tech each solve year (d1_financials.gms).
- SH-13 FIXED: dead cap_hyb block removed from capacity_credit.py (with explanatory note).
- SH-14 FIXED: missing hybrid_config row now a hard `error()` in process_storage_hybrids (was silent @error+continue).
- SH-15 FIXED: checker demo check maps wrapper prescriptions through wrapper_gentech when pooling is on.
- nlval6 config (user): cases_nlvaltest5.csv = moderate TES, mckinsey mandate as FLOOR (GSw_NuclearCapMandate=1), demo plants on.

Legend: **FIXED** = implemented + validated in a run · **OPEN** = confirmed, not yet fixed ·
**DECISION** = needs a design call before fixing · **LATENT** = inactive in current
nuclear/TES configs, will bite future configs · **NO-OP** = code present but ineffective.

---

## 1. Fixed and validated

| ID | Bug | Fix | Validated |
|----|-----|-----|-----------|
| SH-01 | 100% CF: `eq_hybrid_plant_energy_limit` capped dispatchable plant at raw CAP without `avail` | `avail(i,r,h)*CAP` term (c_supplymodel.gms ~3462-3477) | nlval4: wrapper CF 0.85-0.90, no 0.999 |
| SH-02 | TES financing multiplier = 0: tes_ms missing from techs/ivt/tech-subset-table keying gates + all financials CSVs (lost in nuclear-stor merge) | Restored from upstream ReEDS-2.0: techs_default, ivt_*, TES column in tech-subset-table + i_subtech, financials_tech_*, construction_times, cap_penalty, incentives_*, reg_cap_cost_diff `TES\|CSP` header, degradation. Minimal scope: tes_ms NOT standalone-buildable | nlval4/5: ccmult(tes_ms)=1.0247, risk mult ~0.98, TES capex billed; standalone tes_ms cap = 0 |
| SH-03 | PRAS modeled wrappers as full-CAP grid-charged Batteries (reactor invisible to adequacy) | GeneratorStorage split: prep_data writes `hybrid_config_{t}.csv`; reeds2pras `process_storage_hybrids` (inflow=CAP, chg=dis=bcr·CAP, energy=CAP_ENERGY, grid_inj=(1+bcr)·CAP, chg_eff 0.99); 5-frame `split_generator_types`; keyed energy dict in `process_storages` | nlval5 .pras: 19 wrapper GeneratorStorages, Natrium p21 exact (345/172/1035/518), 0 wrappers in storages/generators |
| SH-04 | Outage files battery-first: wrappers carried FOR 0.02/SOR 0.006/MTTR 24 | Gen-first precedence in copy_files for outage_forced/scheduled_static, mttr, unitsize(_atb) | nlval5 .pras λ/μ → FOR 0.03, MTTR 298 (reactor values) |
| SH-05 | `eq_plant_capacity_limit` `+STORAGE_IN_PLANT` double-counted charging (2 MW envelope per MW charged); anti-simultaneity already enforced twice on storage side | Sign flip to `-STORAGE_IN_PLANT` | nlval4/5 optimal; envelope no longer binds spuriously |
| SH-06 | TES wrappers: free/unbacked opres (cost_opres overwritten to 0), zero cc_storage, minduration double-stack (~4x forced TES energy) | cost_opres nonzero-stortech guard; `cc_storage$storage_hybrid=1`; `mintesduration$[tes$(not storage_hybrid)]` | nlval4/5: cap_firm wrapper rows populated (hot = (1+bcr)·CAP); durations 4-9h not forced ~2.75h |
| SH-07 | Policy/lifecycle gaps: state nuclear ban bypass, CES ineligibility, no endogenous retirement (incl. nuclear protections), hybrid_cc_derate=0 for VRE wrappers, winter_cap_ratio missing | b_inputs extensions keyed on `storage_hybrid_gentech` | nlval4/5: winter uprate visible in cap_firm cold |
| SH-08 | Reporting: stor_energy_cap=0, stor_inout booked total gen as discharge, emissions on net GEN, LCOE energy multiplier | e_report/e_powfrac fixes (CAP_ENERGY-based, GEN_STORAGE-based, GEN_PLANT emissions, `_s` multiplier) | nlval5: in/out ratio = 0.9900 = charge_eff; storage loss accounting closes to the MWh; 0 wrapper emit rows |
| SH-09 | Power-only prescription of a storage-hybrid infeasible: `eq_forceprescription_energy` forced INV_ENERGY=0 pre-firstyear (no MWh prescribed, EXTRA_PRESCRIP_ENERGY gated on firstyear_pcat) vs `eq_battery_minduration` floor. Found via Natrium demo → CPLEX conflict refiner (5-row minimal conflict) | c_supplymodel.gms ~972-980: EXTRA_PRESCRIP_ENERGY slack also active when a nonzero cumulative POWER prescription exists at (pcat,r,t) — MW exogenous, MWh endogenous | nlval5: 2032 solved straight optimal; Natrium built 345 MW + 1035 MWh (6h, 4x the floor, chosen voluntarily) |

## 2. Open findings — active in current runs (from 2026-07-24 final review)

| ID | Sev | Bug | Where | Impact / failure scenario | Status |
|----|-----|-----|-------|---------------------------|--------|
| SH-10 | HIGH | SMR wrappers get `reg_cap_cost_diff = 0`: propagation matches literal tech-name headers, but the file is keyed by tech GROUPS (`NUCLEAR`, `TES\|CSP`); "Nuclear" wrappers match by name-luck, `nuclear-smr` wrappers match nothing | copy_files.py:2251-2264; verified nlval5 inputs_case/reg_cap_cost_diff.csv (528 wrapper rows, none for storage-hybrid-1..4-nuclear-smr; base Nuclear-SMR has 132 via group expansion) | SMR wrappers escape regional capital-cost adders standalone SMR pays (e.g. +10.8% at p1) → hybrid-vs-standalone economics tilted pro-hybrid. Affects nlval5's 5.4 GW endogenous hybrid result and all NREL sweeps | **FIXED 2026-07-24, nlval6-validated** |
| SH-11 | HIGH | CSP variable O&M free in objective: base VOM excludes all `hybrid_plant(i)`; re-add terms cover only pvb + storage_hybrid, never CSP (carve-out lost in `hybrid_plant` rename) | c_supplyobjective.gms:168 (re-adds 172-185); e_report.gms:1469 still bills it → objective/report disagree; e_report.gms:2084 replicates omission | Any run with CSP (incl. existing fleet) dispatches CSP with free VOM | **FIXED 2026-07-24, nlval6-validated** (carve-out restored in objective + gen_objcoef) |
| SH-12 | MED | Wrapper TES cannot provide opres: `ramprate(wrapper)` = gen tech's → nuclear's tiny `reserve_frac` → `eq_ORCap_small_res_frac` caps OPRES ~0. `ramprate_storage_hybrid` (storage-side) is defined but NEVER referenced (dead code). Defeats the deliberate storage-side cost_opres + eq_storage_opres work | b_inputs.gms:5036 (gen inherit), 5038-5039 (dead param), 5047 (reserve_frac); confirmed in nlval5 outputs: 0 wrapper opres rows | TES-backed reserves impossible; opres value of hybrids invisible to the optimizer | **FIXED 2026-07-24, nlval6-validated**: `ramprate(wrapper)` from `storage_hybrid_stortech` (design: whole plant takes storage's flexibility); dead param removed; nlval6 wrappers provide combo reserves (config-2: 1036 MWh, config-4: 1063 MWh at 2035) |
| SH-13 | MED | `capacity_credit.py` cap_hyb block (added 2026-07-23) is a NO-OP: feeds cap_stor/cap_stor_agg but only consumers are an `rte` column never created (try→`cc_default_rte`) and unused `cap_stor_ccreg`; sdbin sizes come entirely from peak-reduction geometry | ReEDS_Augur/capacity_credit.py:138-152, 264-277 | Intended sdbin correction for wrapper TES never happens (harmless otherwise) | **FIXED 2026-07-24**: block removed (verified no-op) |
| SH-14 | MED | Missing hybrid_config row silently drops the ENTIRE plant (reactor included) from PRAS: `@error` doesn't throw in Julia; `continue` skips. Realistic trigger: prep_data falls back to empty tech list if gdx lacks `storage_hybrid` symbol → header-only config while tech-subset-table still routes wrappers to storage_hybrid_capacity | reeds2pras/src/utils/reeds_data_parsing.jl:922-928 | Adequacy silently loses GW-scale capacity | **FIXED 2026-07-24**: hard error() |
| SH-15 | LOW-MED | Learning checker demo check (5) filters to base techs only — Natrium wrapper's 345 MW excluded from `expected`; check passes silently if wrapper-prescription experience ever fails to record | nuclear_learning.py:542 | Check can't catch the failure it exists for (engine itself correct: wrappers in `nuclear_learning_exptech`) | **FIXED 2026-07-24**: mapped when pooling on |

## 2b. Directional scan 2026-07-24: errors DISADVANTAGING nuclear/SMR wrappers

Scan question: where do wrappers pay more, earn less, or face tighter constraints than
standalone nuclear/SMR + equivalent storage? (Advantaging bugs already in §2.)

| ID | Sev | Bug | Where | Standalone comparison / failure scenario | Status |
|----|-----|-----|-------|------------------------------------------|--------|
| SH-28 | MED (latent) | SMR wrappers got NO incentive rows → `safe_harbor=0` → tax credits phase out up to 6 years earlier. Same group-label root cause as SH-10: the cloner skips `incentives_*.csv` by name but the run-copy is `incentives.csv` (escapes skip); "Nuclear" literally matches the NUCLEAR group row (wrappers 5-8 cloned, safe_harbor 6) while "Nuclear-SMR"/tes_ms match nothing (wrappers 1-4 empty). Verified nlval5: `safe_harbor.csv` SMR wrappers 0.0 vs Nuclear-SMR 6.0. ITC path repaired in GAMS (d1_financials rebuilds from components) but the PTC term (c_supplyobjective.gms:374-378) uses the wrapper's OWN `tc_phaseout_mult` — never overridden from gen tech | copy_files.py:2090-2098 (skip list), reeds/financials.py:230-243, tc_phaseout.py:112-185, b_inputs.gms:1639 | Zero realized impact in OBBBA cases (nuclear PTC=0, ITC-only) but wrong under any nuclear-PTC incentive suffix (IRA 45Y); also makes cloning of incentive files nondeterministic | **FIXED 2026-07-24**: GAMS tc_phaseout_mult_t inheritance + cloner skips incentives; nlval6-validated |
| SH-29 | LOW-MED | Reg-reserve energy losses billed at TES round-trip RTE (0.55 advanced / 0.47 moderate) on ALL wrapper reserves: `storage_eff(wrapper)` = tes_ms rte (b_inputs.gms:6002) feeds the `(1-storage_eff)/2·reg_energy_frac` terms, while the wrapper's actual modeled charge efficiency is 0.99 (b_inputs.gms:6018). Wrapper pays (1-0.55)/2 = 0.225/MW — 3x a battery's charge; standalone nuclear pays zero | c_supplymodel.gms:3202-3207, 3228-3231; b_inputs.gms:6002 vs 6018 | Wrapper reg reserves overpriced vs both parents; currently masked by SH-12 (reserves ~0) but binds as soon as SH-12 is fixed | **FIXED 2026-07-24**: storage_eff(wrapper)=plant-charging eff (0.999) |
| SH-30 | LOW-MED | ALL wrapper reserves must be pre-stored in TES: eq_storage_opres requires STORAGE_LEVEL ≥ hours×(total OPRES) with a single OPRES variable per wrapper — reactor-headroom reserves are conflated with storage reserves. Violates the 2026-07-24 design principle's own asymmetry: the generator can't run out of energy, so reactor headroom (avail·CAP − GEN_PLANT) should count as reserve backing without stored energy | c_supplymodel.gms:3213-3237 | Standalone nuclear provides reserves with no energy backing; nuclear+battery pair only backs the battery share; wrapper must bank TES energy for all of it | **FIXED 2026-07-24**: eq_storage_opres credits avail·CAP−GEN_PLANT for dispatchable wrappers |
| SH-31 | LOW | Wrapper pays nuclear's reg cost (10.13 $/MWh) on ALL reserves incl. TES-provided ones: tes_ms has no cost_opres row so the SH-06 nonzero guard (correctly) keeps the gen value — but a standalone pair pays 10.13 only on the nuclear share; battery-provided reg is free | inputs_case cost_opres_default.csv; b_inputs.gms:5074-5075; c_supplyobjective.gms:233-234 | Small standing cost bias against wrapper reserves | **FIXED 2026-07-24** (user rule): TES takes CSP cost_opres (reg 3.24, NOT 0); wrappers take storage cost unconditionally |
| SH-32 | LOW | PTC and CES credited on NET GEN — wrapper loses credit on the 1% TES charging loss; standalone nuclear is credited on gross output regardless of a separately-metered battery | c_supplymodel.gms:3450-3462 (eq_plant_total_gen); c_supplyobjective.gms:374-378 | ~1% of cycled energy; nil in nlval5 (no nuclear PTC); CES effect only where CES binds | **FIXED 2026-07-24** (user: both gross; PTC+REC on GEN_PLANT), nlval6-validated |

Design observations (deliberate code, but wrapper pays more than the sum of its parts — flag to NREL):
- **Capex premium widens with nuclear learning**: wrapper OCC = learned-gen-OCC·(1−powerblock share) + (1+bcr)·TES-island cost (b_inputs.gms:6144-6147; verified exact in nlval5 cost_cap: wrapper-1 = 3,753,194 vs standalone SMR+0.25·tes = 3,507,765, +7.0%). The TES island doesn't learn with nuclear, so the hybrid premium grows every learning step. Confirm intended under GSw_NuclearLearning.
- **TES share financed at nuclear risk**: storage-side fin mult scaled by gen/storage financing-risk ratio ≈ +5.8% vs standalone tes_ms (d1_financials.gms:166-174). Deliberate (whole-plant financing) but systematic.
- **Min TES duration 1.5h per MW storage power** vs battery_li's 0.2h (7.5x forced energy vs a nuclear+battery comparator; looser than standalone TES's 2h).

Directional scan verified clean: cost_fom = gen + bcr·tes + fom_energy (matches standalone pair); VOM structure = pvb pattern, no double-billing; fuel/heat-rate/emissions on gen basis (b_inputs.gms:4883 heat-rate override); fin-mult blend weights = capex composition weights; maxage 80yr via GAMS override; retirement protections mirror nuclear; wrappers in nuclear tg only (growth/queue parity at reactor MW); gen side gets full winter uprate in PRM; sdbin chain has no wrapper-zeroing term — **cold-season zero storage credit for config-4 is system-wide duration-bin geometry (standalone batteries got 0.000 cold firm credit in every checked BA; longer-duration wrapper TES actually out-earns batteries: p13 cold bins 6/12/24 populated for wrapper, none for battery)**; interday-linkage equations handle CAP_ENERGY correctly if ever enabled.

## 3. Latent findings — inactive in current nuclear/TES configs

| ID | Sev | Bug | Where | Trigger |
|----|-----|-----|-------|---------|
| SH-16 | MED | VRE-paired wrappers can't generate: no `cf_tech` → m_cf=0 → GEN_PLANT forced 0; excluded from VRE cc terms (eq_reserve_margin:1752,1759) and eq_curt_gen_balance | d1_temporal_params.gms:568-572; c_supplymodel.gms:1283,1295,3475 | Any upv/wind GSw_StorageHybrid_GenTechs config |
| SH-17 | MED | CAP_ENERGY has no retirement path: `eq_cap_energy_new_noret` strict equality; wrappers retirable under Sw_Retire=3/5 → retired wrapper's TES energy + fom_energy persist forever | c_supplymodel.gms:732-744; b_inputs.gms:6611-6615 | First endogenous wrapper retirement |
| SH-18 | MED | Fossil-paired wrappers bypass gas supply curves (eq_gasused), CAA max-CF; CSAPR NOx priced on net GEN (understates by RTE losses); billed static fuel_price regardless of Sw_GasCurve | c_supplymodel.gms:2970-2982, 2607, 2513/2532; c_supplyobjective.gms:241-246 | gas-cc pairing (documented in switch help) |
| SH-19 | LOW-MED | Min-loading on net GEN not GEN_PLANT (eq_minloading, eq_mingen_lb/ub); wrappers have minloadfrac data (0.2-0.7). **Direction decided 2026-07-24**: net GEN should be minload-free (storage modulates to zero); reactor min load binds GEN_PLANT (as eq_mingen_fixed already does) | c_supplymodel.gms:1503-1511, 1322-1346 | Sw_MinLoading=1 or Sw_Mingen=1 (defaults 0) |
| SH-20 | LOW | PRM sees winter cap swing (ccseason_cap_frac_delta) that dispatch never sees (eq_hybrid_plant_energy_limit has no seas_cap_frac_delta) | c_supplymodel.gms:1785 vs 3477 | Always (small) |
| SH-21 | LOW | Wrapper TES outage-free in LP: storage_hybrid branch of eq_storage_capacity drops `avail`; TES can discharge at full bcr·CAP during full-plant outage — inconsistent with gen-first outage coupling in PRAS. **Resolved by 2026-07-24 design principle**: all output flows through the shared powerblock → apply plant `avail` to the wrapper storage branch | c_supplymodel.gms:3115-3116, 3501 | Always (small) |
| SH-22 | LOW | Dangling INV_ENERGY/CAP_ENERGY columns for pvb/CSP (eq_cap_energy_new_noret widened to hybrid_plant; not in objective; not tfix-fixed) — degenerate free columns | c_supplymodel.gms:732; d2_varfix.gms:36 | Cosmetic/solver hygiene |
| SH-23 | LOW | Sw_StartCost=5 bills reactor start costs on TES dispatch swings of net GEN; =1/2 exempt wrapper while standalone nuclear pays. **Direction decided 2026-07-24**: wrappers are storage-like for start/ramp costs — exempt net-GEN swings (reactor runs flat underneath) | b_inputs.gms:5149-5154 | Non-default GSw_StartCost |
| SH-24 | LOW | Reporting-only: costnew/no_credits bill wrapper INV_ENERGY at blended `cost_cap_fin_mult` instead of `_s` (objective + lcoe correct) | e_report.gms:1188-1190, 1345 | Diagnostics only |
| SH-25 | LOW | `process_storages` direct dict indexing → KeyError crash on standalone storage with MW above cutoff but MWh=0 (energy_cap>0 filter drops the key); hybrid path uses get(...,0.0) | reeds2pras/src/utils/reeds_data_parsing.jl:804; prep_data.py:489 | Edge-case standalone storage |
| SH-26 | LOW | capacity_credit cap_hyb: wrapper missing from bcr map keeps MWh with MW=0 (moot while SH-13 open) | ReEDS_Augur/capacity_credit.py:143-152 | With SH-13 fixed |
| SH-27 | LOW | Wrappers absent from outage_forced_temperature / outage_scheduled_monthly (fallback cloning failed) — wrapper hourly FOR flat 0.03 vs nuclear's temp-shaped mean ~0.04 | inputs_case outage files; outage_rates.py "missing" log lines | PRAS fidelity (small) |

## 4. Verified clean (final review, 2026-07-24)

- SH-09 fix safe: EXTRA_PRESCRIP_ENERGY positive-only → prescribed energy minima still enforced; d2_varfix tfix domain matches. Residual nit: pre-firstyear MW+MWh prescriptions no longer pin energy exactly (slack allows overbuild).
- Objective single-billing (INV blended mult, INV_ENERGY at `_s` once, FOM+fom_energy once, VOM plant/storage split, uranium fuel on GEN_PLANT).
- No PRM double-count (wrapper in storage(i), credited once + sdbin); d2_varfix/d2_unfix cover all six hybrid variables; growth limits, interconnection queues, nuclear/battery mandates, RGGI/state policies, e_powfrac, d3_data_dump, learning cost recomposition.
- Pipeline: lowercase keying end-to-end; ivt extension; tech-subset-table/`STORAGE-HYBRID` column; writecapdat demo concat; runchecks header-only tolerance; flex_geo detection on stortech (correct — flex_geo is the storage side).
- Numerical audit (nlval5 outputs): RTE 0.9900 exact; Σ(IN−out)=losses_ann STORAGE to the MWh; ~1 cycle/day; durations 4-9h ≥ 1.5h floor; ITC 32.5% = capex-weighted gen(29.7%)/TES-battery-clone(38.5%) blend; cap_new_ann 3-yr annualization correct (cap_new_ivrt exact: 345 / 419.2 / 4952.5).

## 5. Validation runs

| Run | Config | Result |
|-----|--------|--------|
| nlval3 (pre-fix) | eo_boak_lo, moderate TES | INVALID: 48.8 GW hybrids on 100%-CF + free TES; NEUE 160 ppm w/ phantom batteries |
| nlval4 (post-sweep) | eo_boak_lo, moderate TES | All optimal; ZERO hybrid builds at real TES pricing (147 GW mandate all standalone); checker 32/32; NEUE 2364 ppm (diagnostic); with-builds PRAS path unexercised |
| nlval5 | nlvaltest4 = + GSw_NuclearDemo=1 (Natrium as storage-hybrid-2-nuclear-smr BCR 0.5 @ p21/2031) + plantchar_tes=tes_ATB_2024_advanced | All optimal (2032 straight optimal); Natrium 345 MW + 1035 MWh built; ~5.4 GW endogenous SMR hybrids @ 2035 (BCR 0.75/1.0, ~18 BAs); mandate 147,000.0 exact @ 2035; checker 33/33 (build-driven learning exercised); NEUE 33.9 ppm; PRAS GeneratorStorage path validated with capacity |
| nlval6 | nlvaltest5 = moderate TES + mckinsey mandate FLOOR (GSw_NuclearCapMandate=1) + demo on; ALL 2026-07-24 fixes active | All optimal (2035 has the known benign unscaled-infeasibility acceptance); checker 33/33; Natrium 345 MW + 1035 MWh (6h chosen at MODERATE pricing); ~1.8 GW endogenous config-4 hybrids (p101 1385 MW/7.1h, p13 416 MW/8.2h); **wrapper opres live** (combo 1036/1063 MWh) with standalone nuclear also providing; RTE = 0.999 exact; mandate floor exact at 2035 (114,500.0; 2032 pre-firstyear by design); wrapper ITC 31.7% vs standalone 29.9%; FOR 0.03 gen-first; 0 emissions; NEUE 34.5 ppm; PRAS: 3 wrapper GeneratorStorages @ 0.999 eff, 0 contamination |

Caveat on nlval5's hybrid adoption: SH-10 inflates it (SMR wrappers regional-cost-discounted). Re-run after SH-10 fix before quoting numbers.

## 6. Known-suspicious inputs (copied as-is from upstream, flagged for NREL)

- TES financials = CSP clones: 5-yr MACRS, 30-yr eval, and 1-yr construction time (battery-derived).
- TES incentives = battery clones: full 30% standalone-storage ITC + 10% energy-community bonus flowing into wrapper TES capex (observed: wrapper ITC 32.5% vs standalone SMR 29.7%).
- `tes_ms_power_cycle` scalar not restored (referenced by nothing in either repo).

## 7. Next actions

1. [ ] SH-10 + SH-28: group-header-aware propagation (reg_cap_cost_diff, incentives) — same root cause; cloner should skip incentives.csv entirely and handle group-keyed files explicitly; audit remaining group-keyed inputs.
2. [ ] SH-11: restore CSP carve-out in base VOM term.
3. [ ] Reserves batch (design principle 2026-07-24: plant takes storage's flexibility; reactor can't run out of energy): SH-12 (ramprate from stortech), SH-29 (reg-loss eff), SH-30 (credit reactor headroom as backing), SH-31 (reserve cost basis).
4. [ ] SH-13/14/15: robustness batch (wire or remove cap_hyb; hard-error missing hybrid config; checker wrapper-demo mapping).
5. [ ] Rerun validation (nlval6) after 1-3; compare hybrid adoption vs nlval5.
6. [ ] Ticket the latent set (SH-16..27, SH-32) before any VRE/gas wrapper configs; confirm learning-vs-TES capex premium intent with NREL.
7. [ ] Nothing committed yet — commit checkpoint after fix batches + nlval6 green.
