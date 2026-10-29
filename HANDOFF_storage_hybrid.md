# Handoff: storage-hybrid-pr, Phases 1 (compile check), 2–7 and 9

> **Temporary file.** It exists only to hand work between machines. The agent on the original machine deletes it in Phase 8, before the PR. Do not delete it yourself.

## 1. Who you are working for, and how
You are continuing work for Ethan Gallup on branch `storage-hybrid-pr` of `ethan-r-gallup/ReEDS-hybrid-plant`. The goal is a branch that is ready for a pull request to `ReEDS-Model/ReEDS` `main`. Ethan opens the PR; you never open it.

**Check-in gates (mandatory).** At the end of every phase, stop and report to Ethan. The report covers:
1. **Done:** what changed, with commit hashes and files.
2. **Results:** what you verified, and what failed or was skipped, with the output.
3. **Found:** anything surprising, including any audit claim below that turned out wrong.
4. **Plan changes (optional):** suggested edits to the remaining phases, and why.
5. **Next:** what the next phase will do.

Then wait for Ethan's explicit green light before you start the next phase. A ReEDS run that is still going belongs to its phase. If Ethan changes the plan, update this file first.

**Writing style (Ethan's standing instruction):**
- Write in plain technical English, one idea per sentence, in the active voice with a named actor.
- Use one consistent term per concept.
- Gloss a term of art in a half-clause on first use.

**Hard rules:**
- No force-push and no history rewrites. Commit per phase so a regression can be bisected.
- Never add nuclear-learning or paper code (capacity mandates, `GSw_interpolate_mandates`, Natrium, `tes_threshold_*`) to this branch.
- Do not do Phase 8 (docs and PR description). The original agent does it.

## 2. Split of work
| Step | Machine |
|---|---|
| Phase 0 prep, Phase 1 merge (committed `fec9d215`) | original (done) |
| **Phase 1 compile check, Phases 2–7, Phase 9 runs** | **you** |
| Phase 8 docs + PR description, delete this file, final push | original |

When you finish Phase 9, fill in section 9 of this file ("Results for Phase 8"), commit it, and push. Then tell Ethan the original agent can resume.

## 3. Current state
- `storage-hybrid-pr` = `fec9d215` merge of `upstream/main` 6c175c4f (2026-10-26) into the old tip 49f1028e, plus one commit that adds this file and the Utah test columns.
  - Local tag `storage-hybrid-pr-pre-merge` = 49f1028e on the original machine only. Use `49f1028e` directly.
  - Merge-base with upstream before the merge: `e4870a3f`.
- The merge commit has **never been compiled or run**. The original machine ran out of memory.
- PR diff vs upstream is now 71 files, +4,043/−276. The three `financials_tech_ATB*.csv` files were restored to upstream text plus 205 appended hybrid rows each.

**Decisions Ethan made (2026-10-27):**
- **Naming:** keep the rename: `HYBRID_PLANT` = upstream's PV+battery/CSP subset (formerly `STORAGE_HYBRID`); `STORAGE_HYBRID`/`storage_hybrid(i)` = the new gen+storage wrapper techs. The PR flags it as a breaking change, and every in-repo consumer is fixed.
- **PVB/battery formulation changes:** keep them. These are the PV+battery equation changes, battery energy-capacity retirement and prescription slack. They are justified in the PR, and their base-case effect is measured on Utah (Phase 9).
- **Fix, not just document:**
  - ban unused standalone `tes_ms`/`flex_geo*`
  - an explicit row-cloning registry
  - PRAS unit disaggregation
  - VRE wrappers fixed properly (capacity factor + shared supply curve)
- **Tests:** a CI scenario, `check_inputs` YAML entries, and pytest unit tests.
- **Small calls:**
  - Reject H2-fueled gen techs in validation, because wrappers do not draw on the H2 balance.
  - Leave the `GSw_StorageHybrid_*` list defaults unchanged.
- **Input CSVs:** minimal appends only. Never round-trip a repo CSV through pandas.

**Plan changes Ethan accepted after Phase 1 (2026-10-28):**
- Keep the two upstream single-region fixes from Phase 1 (`utils.jl` empty-lines guard in `make_pras_interfaces`, and the empty-`FLOW` guard in `report_calcs.py`) in this PR. The PR description flags them as upstream bug fixes.
- Phase 4 adds `storage_hybrid(i)` to the energy-capital fin-mult correction in `report.gms` `error_check('z')`, which today sums only `(battery(i) or tes(i))`.
- Phase 9: every new Utah column sets `GSw_gopt=2`, because CPLEX barrier with `barcolnz 30` reports the Utah 2030 LP infeasible (upstream fails identically). Phase 9 also adds a Utah case that builds a grid-charging wrapper, so `storage_in_grid_h` is non-empty.
- Phase 6 (PRAS unit disaggregation) is high priority. In `hyb_ut`, PRAS models the 3.9 GW gas-cc wrapper fleet as one GeneratorStorage unit, and NEUE rises to 200–400 ppm.

**Plan changes Ethan accepted after Phase 3 (2026-10-28):**
- Phases 5–6: VRE wrappers must not take outage inputs from their storage tech. Today upv and wind have no rows in `outage_forced_static`, `outage_scheduled_static` or `mttr`, so the registry falls back to battery_li or tes_ms values. Make those entries gen-only (no storage fallback), and check the result in the LP and in PRAS.
- Phase 9: section 9 notes that `hyb_z54` results from code before Phase 3 (`6c494147`) include phantom prescribed SMR builds. The old cloner copied the X-energy and Natrium rows of `demonstration_plants.csv` to every nuclear-SMR wrapper (2.66 GW over 4 wrappers).

**Plan changes Ethan accepted after Phase 4 (2026-10-28):**
- `error_check('z')` excludes wrappers from the energy-capital fin-mult correction. This replaces the Phase 1 item that added `storage_hybrid(i)`. The objective and the report both bill wrapper energy capital at `cost_cap_fin_mult_storage_hybrid_s`, so the correction for wrappers is zero.
- Phase 5: check whether the objective double counts supply-curve cost for wrappers that share a parent supply curve (`rsc_agg` includes the self-pair). Do this before VRE wrappers share supply curves.
- Phase 9: find the cause of `error_check` z = 0.000286 in `hyb_ut` (base is −0.000019), and of the +2 LP variables per solve against upstream in `base_ut`.

**Plan changes Ethan accepted after Phase 5 (2026-10-28):**
- Phase 9 `hyb_vre_ut` pairs upv and wind-ons with battery-li (already in `cases_hybridtest.csv`), not wind-ons with tes-ms. Validation now rejects TES on VRE gen techs.
- Phase 9 VRE build check: VRE wrappers are not economic in Utah, and Utah has no onshore-wind supply curve. Section 9 records the Phase 5 sandbox runs (wrapper capital cost cut in the run-local GAMS copy only) as the evidence for builds, `m_cf` and the shared supply-curve bound. One z54 column also gets a wind-ons wrapper type, so wind wrappers can be built for real.
- Phase 6: a VRE wrapper's PRAS inflow comes from its gen tech's capacity-factor profile, not a constant nameplate inflow.

**Plan changes Ethan accepted after Phase 7 (2026-10-28):**
- New Phase 7b, before Phase 9: wrappers take their first build year from the gen tech (`years_until_endogenous.csv` and `firstyear` switch to gen precedence). Today they copy the storage tech's 0-year lead time, so nuclear wrappers can be built from 2026 while standalone nuclear waits until 2034. Phase 7b also audits the other storage-first registry entries (construction times, `heat_rate_adj`, `minloadfrac0`, `ramprate`, `startcost`, `mingen_fixed`, `minCF_input` and similar) and fixes each one that reaches the model with the storage tech's value where the gen tech's belongs.
- Phase 7: CI also runs `pytest tests/test_storage_hybrid.py`.
- Phase 7: `github_StorageHybrid` keeps `github_Pacific`'s end year of 2030, so its nuclear wrapper exercises setup only.

**Plan changes Ethan accepted during Phase 9 (2026-10-29):**
- New Phase 9a, before hand-back: connect gas-cc wrappers to the gas, Clean Air Act and capacity-credit outage rules they skip today, and reject coal, biopower and BECCS gen techs. Details are in section 7.
- The Phase 9.1 placeholder becomes Phase 9b. It is a sanity check, scoped with Ethan in conversation, and it starts after Phase 9a.

## 4. Environment setup
1. **Python:** upstream's `runreeds.py` rejects any env except one named `reeds` with pandas 3.x. Build it with `conda env create -f environment.yml` and run with `conda run --no-capture-output -n reeds python runreeds.py ...`.
2. **Julia:** `Project.toml` pins `julia = "=1.12.1"` and PRAS ~0.9. Run `juliaup add 1.12.1`, then `julia +1.12.1 --project=. instantiate.jl` from the repo root. This creates `Manifest.toml` (git-ignored), which `runreeds.py` requires whenever `pras=2` or `GSw_PRM_StressIterateMax>0`.
3. **Sub-national runs need `GSw_GasCurve=2`**, which `runreeds.py` enforces.
4. **Commands:**
   - dry run: `python runreeds.py -b <batch> -c hybridtest -s <case> --dryrun --forcelocal`
   - real run: drop `--dryrun`
   - outputs land in `runs/<batch>_<case>/`; watch `gamslog.txt`

## 5. Phase 1 — compile check (finish this first)
**Governing rule for every GAMS edit:** upstream's old `storage_hybrid(i)` meant PVB/CSP. On this branch it means wrappers. Any upstream-style `storage_hybrid(i)$(not csp(i))` must become `hybrid_plant(i)` or `pvb(i)`. A scan after the merge found no surviving upstream `storage_hybrid` line.

1. Run `base_ut` and `hyb_ut` from `cases_hybridtest.csv` to at least the first solve year. Fix compile and execution errors in a follow-up commit, then let them run to 2040.
2. Post-merge greps already came back clean for `CURT`, `cost_curt`, `Sw_CurtMarket`, `degrade(`, `h2_combustion` (outside its own definition), 5-argument `m_cf(` and `'FUEL_CELL'`.
3. Things I resolved by judgment that you should confirm compile and behave:
   - `c_model.gms` `eq_hybrid_plant_energy_limit` now reads `sum{c$i_c(i,c), m_cf(i,c,v,r,h,t)} * CAP$(pvb(i) or storage_hybrid_vre(i))` plus the dispatchable `avail` term.
   - `report.gms` `gen_ivrt_uncurt`, `gen_new_uncurt` and the uncurtailed sum use `(vre(i) or pvb(i))` with class-indexed `m_cf`.
   - `6_data_dump.gms` keeps upstream's `distpv` in `cap_ivrt` plus the hybrid `cap_energy_ivrt` for `battery or tes or storage_hybrid`.
   - `plantcostprep.py` runs upstream's battery mid-life refurbishment block, then reads `plantchar_tes` and `plantchar_flex_geo`.

## 6. Phases 2–7 (details from two read-only audits)
Line numbers were taken before the merge, so they may have shifted by a few lines. Verify every claim before you act on it, and report any claim that is wrong.

### Phase 2 — remaining upstream-driven adaptations
- **Interconnection queue (#226):** `cap_limit` became `queue_limit` in `inputs.h5`, and `cap_penalty` is now an h5-loaded GAMS parameter. Both must never get wrapper rows; mark them no-clone in the Phase 3 registry. Wrappers inherit `tg_i` from their gen tech, so wrapper power capacity counts against that tech's queue limit. This is intended; document it in your report.
- **Clone from the gen tech first:** `i_c` (resource class, #203) and `employment_factor_plant` (now an h5 parameter).
- **Battery refurbishment (#176):** `plantcostprep.py` adds one discounted energy refurbishment at `batt_years_until_refurb` (15) years to battery `capcost_energy`. Battery-storage wrappers inherit it, but they live for their gen tech's `maxage` (e.g. nuclear, 60+ years), so they would need several refurbishments. Decide between scaling the refurbishment count to the wrapper's life and documenting the limitation, then report the choice.
- **`inputs/userinput/futurefiles.csv`:** add entries for the per-case hybrid files. `forecast.py` raises for unlisted inputs_case files when `endyear > 2050`. The files are `storage_hybrid_{config,bcr,gridcharging,storagetechs,gentechs,rsc_agg}.csv`, `plantchar_tes`, `plantchar_flex_geo`, `heaterchar(s)` and `storage_hybrid_powerblock_share`.
- **Input docs:** upstream moved input documentation from `docs/sources.csv` into per-folder `inputs/*/README.md`. Add entries for:
  - `tes_ATB_2024_*`, `flex_geo_placeholder` and `heater_sams_2020` (in `inputs/plant_characteristics/README.md`)
  - the new `i` members (in `inputs/sets/README.md`)
  - `storage_hybrid_powerblock_share.csv`, which sits in `inputs/` with no README, so consider moving it into a documented folder
- **Default timing:** upstream shifted the defaults to `this_year`=2026, a 5-year `yearset` and `GSw_StartMarkets`=2027. Nuclear and SMR now first build in 2034, so the z54 cases in `cases_hybridtest.csv` with `endyear=2035` get one solve year. Raise them to 2040.
- **MGA (#162, low priority):** `d_mga.gms` weights `CAP` by every `i_subtech` a tech belongs to, so wrappers are weighted for each of their subsets. Note it; fix only if trivial.

### Phase 3 — replace the heuristic row cloner
- **Current behavior:** `propagate_storage_hybrid_tech_rows` (`reeds/input_processing/copy_files.py` ~1781–2136) walks every CSV in `inputs_case` and every `inputs.h5` key. It treats a column as tech names if it has at least 5 values and at least 60% of them match `i`, then rewrites the file through pandas.
- **Problems:**
  - pandas reformatting (e.g. `0` → `0.0`)
  - `comment='#'` truncation
  - files containing "storage-hybrid" are skipped
  - the h5 loop ignores `skip_files` and the gen-first rule. Example: `tg_rsc_upvagg` has two tech columns, so a wrapper on `upv_N` would become PVB's supply-curve parent. The same risk applies to `i_geotech`, `ofstype_i`, `forced_retirements` and `noretire`.
  - range rows like `upv_1*upv_10` never match class members
- **Replace it with an explicit registry:** a module-level table in `copy_files.py` that gives, for each entry, the file or h5 key, its tech column(s), and the precedence (gen-first or storage-first).
  - Append new CSV rows as text lines and leave existing lines untouched.
  - Apply the same registry to h5 keys.
  - Expand range rows for class members.
  - Keep the family-root fallback.
  - Never clone into upgrade-link files, `cap_penalty` or `queue_limit`.
- **Build the registry from evidence:** log which files and columns the current heuristic touches in a `hyb_ut` run. Then diff the old and new `inputs_case` to prove the two match, except for the intended fixes.
- **Delete dead code:** the unreachable CSV fallback for `i` (~87–103, ~431–444) and the legacy `storage-hybridN` label translator (`translate_legacy_storage_hybrid_labels`, ~481–529, called ~1790–1796).

### Phase 4 — correctness fixes
- **Standalone `tes_ms` and `flex_geo*` appear in every base run.** They are in `i.csv`, `techs_default.csv`, the `ivt_*` files, the tech-subset table and many per-tech files. Only flex-geo is banned (`b_inputs.gms` ~763), and `Sw_Storage=0` does not ban `tes_ms` because it bans only `storage_standalone`.
  - Fix: block investment and capacity for the standalone techs after the wrappers inherit their parameters. Do not use `ban(i)`, because many parameters are set only where `not ban(i)`.
  - Confirm that the base LP loses the tes_ms/flex_geo variables, and that wrapper costs are unchanged.
- **Component bans don't reach wrappers.** `Sw_Nuclear=0` (~498), `Sw_NuclearSMR=0` (~502), `Sw_Storage=0` (~592), `Sw_GasFuelCell`/`Sw_H2FuelCell` and state bans hit only the component techs. Add one rule: ban a wrapper if its gen tech or storage tech is banned, for example `ban(i)$[storage_hybrid(i)$sum{ii$storage_hybrid_gentech(i,ii), ban(ii)}]`, plus the same for the storage tech.
- **`GSw_HybridPlant` dependency.** Wrappers are in `HYBRID_PLANT`, so `GSw_HybridPlant ∈ {0,1}` silently bans them (`b_inputs.gms` ~547–553), and wrapper equations are gated on `Sw_HybridPlant`. Validation must raise in that case. Also make `c_model.gms` ~2803, the one line gated on `Sw_StorageHybrid` instead, consistent with the rest.
- **Zero heat rate.** The wrapper's heat rate is copied from the gen tech at the same (v,r,t) (`b_inputs.gms` ~3905). But the gen tech's heat rate exists only where the gen tech is `valcap`. Wherever the gen tech cannot be built, the wrapper gets zero fuel cost (`d_objective.gms` ~257) and possibly zero emissions. Copy from the gen tech's heat rate before `valcap` filtering, and check `emit_rate`.
- **Validation.** Replace `runreeds.py` ~418–428 with one function that runs only when `GSw_StorageHybrid=1`. It checks:
  - matching list lengths (a single value broadcasts)
  - every GenTech and StorageTech resolves against `i`
  - every StorageTech is in `STORAGE`
  - no GenTech is an upgrade, cooling-variant, storage or H2-fueled tech
  - BCR > 0, and 0 ≤ GridCharging ≤ BCR
  - `GSw_HybridPlant` is compatible

  The current check runs even when the feature is off, crashes on non-numeric types, wrongly limits type IDs to 1–8, and accepts `caes`, which is not in `i`.
- **Financials:**
  - The cost-weighting for the multiplier (`2_financials.gms` ~224–273) subtracts the shared-powerblock cost for non-thermal storage, but `cost_cap` does not (`b_inputs.gms` ~5009). Make the two consistent.
  - Guard the `(p+s)=0` division (~247–260).
  - Compute `rsc_fin_mult` for geothermal supply-curve wrappers after the composed multiplier.
  - Wrapper VOM skips regional multipliers (`b_inputs.gms` ~3712); use `cost_vom`.
- **`error_check('z')`.** The energy-capital fin-mult correction (`report.gms` ~1791–1877) sums only `(battery(i) or tes(i))`; add `storage_hybrid(i)`.
- **LCOE.** `lcoe_built`/`lcoe_pieces` (`report.gms` ~269–313) sum energy capital and energy FOM only over `battery or tes`, so battery-backed wrappers miss them.
- **H2 gen techs.** Reject them in validation (see section 3).
- **Cleanup:**
  - Delete `inputs/sets/storage_hybrid_config.csv` (empty), its `runfiles.csv` row and the unused GAMS set `storage_hybrid_config` (`b_inputs.gms` ~789).
  - Delete the commented-out blocks: `b_inputs.gms` ~580–589, ~3711 and ~4957–4963; `2_financials.gms` ~85–103; `c_model.gms` ~318.
  - Fix stale references in comments (old file names such as `d1_financials.gms`, `e_report.gms`, `d3_data_dump.gms`, and "~L1064"-style line pointers).
  - Remove the private "SH-13 in debug_storage-hybrid.md" reference (`capacity_credit.py` ~136).
  - Rename the "Nuclear+Storage Cost Model" header in `plantcostprep.py`.
  - Remove the `"tes"` key from `pcm_defaults.json`.
  - Revert whitespace-only hunks (`plantcostprep.py`, `capacity_credit.py` ~131, `c_model.gms`, `d_objective.gms` ~235, `report.gms` ~31/311).
  - Add missing final newlines (`storage_hybrid_powerblock_share.csv`, `Gen_Storage.jl`).
  - In `cases.csv`, the `heaterscen` description says "subtract" but the code adds heater cost. Give `plantchar_tes` and `heaterscen` regex Choices, and move the `GSw_StorageHybrid*` and `plantchar_*` switches next to their peers.
  - Add `tech_map`/`tech_style` rows for `tes_ms` and `flex_geo*` in `postprocessing/bokehpivot/in/reeds2/`.

### Phase 5 — VRE wrappers (upv, wind-ons, wind-ofs)
- **The problem today:** a VRE wrapper gets no capacity factor, because `cf_in`/`cf_vre` have no wrapper columns and wrappers are not in `cf_tech`. So it never generates. It also has no resource limit.
- Clone `cf_in(ii,c,r,h)` per class to each VRE wrapper (see `2_temporal_params.gms` ~450–466), add VRE wrappers to `cf_tech`, and confirm that `i_c` gives each wrapper its gen tech's class.
- Generalize `storage_hybrid_geo_rsc_agg` (`b_inputs.gms` ~957–975) to every resource-supply-curve family, so VRE wrappers share the parent supply curve the way PVB shares UPV's via `tg_rsc_upvagg`. The per-case `storage_hybrid_rsc_agg.csv` writer in `copy_files.py` must emit the VRE pairs.
- Check the capacity-credit derate (`hybrid_cc_derate`) for VRE wrappers.
- Remove the "experimental" warning in `docs/source/storage_hybrid.md` ~51–53. That is a one-line doc edit you may make; the rest of the docs are Phase 8.

### Phase 6 — PRAS unit disaggregation
- `process_storage_hybrids` (`reeds/resource_adequacy/reeds2pras/src/utils/reeds_data_parsing.jl` ~837–967) builds one PRAS GeneratorStorage per (wrapper, region). A multi-GW fleet therefore fails as one unit, which skews LOLE and stress-period selection.
  - Split each fleet into units sized by the gen tech's `unitsize`, the way thermal units are split.
  - Each unit gets its share of energy and storage capacity.
- Guard the `FOR_dict[lowercase(tech)]` (~928) and `mttr_dict[tech]` (~936) lookups so they fall back to the gen tech. Today, egs/geohydro wrappers would raise `KeyError`.
- The LP caps charge + discharge jointly at bcr × CAP (`c_model.gms` ~3570–3587), but PRAS gets separate charge and discharge caps. Map the GeneratorStorage `gridinjection`/`gridwithdrawal` capacities so that grid withdrawal is at most `gridcharge_ratio × CAP`. Report any remaining approximation; the original agent documents it.
- The audit found no PRAS 0.8→0.9 API break: the positional constructors are unchanged, and `GeneratorStorageEnergy` still returns `(mean, std)`.

### Phase 7 — tests
- **CI scenario:** add a `github_StorageHybrid` column to `cases_test.csv`. Start from `github_Pacific` and add `GSw_StorageHybrid=1` with nuclear+tes-ms, gas-cc+battery-li with grid charging, and upv+battery-li. Add it to the matrix in `.github/workflows/python-app.yaml`.
- **`tests/objective_function_params.yaml`:** add entries for `cost_vom_storage_hybrid_s`, `cost_cap_fin_mult_storage_hybrid_s`, `bcr`, `gridcharge_ratio`, `heat_rate`, and `cost_cap_energy`/`cost_fom_energy` on `storage_hybrid`. `reeds/input_processing/check_inputs.py` checks these on every case.
- **New `tests/test_storage_hybrid.py`:** follow the `tests/test_read_h5_files.py` pattern with a tiny temporary `inputs_case`. Test:
  - `build_storage_hybrid_configs`: broadcasting, family expansion, duplicate and length errors
  - the ivt append
  - the registry cloner: exact rows, range expansion, precedence, original lines left unchanged
  - the validation function

## 7. Phase 9 — verification runs (you), results to section 9
Run one case at a time.
1. **Static:** `pytest tests/test_storage_hybrid.py`. Byte-compile the Python you touched. Check `git diff upstream/main --stat` for unexpected files or large CSV diffs.
2. **Add two Utah columns** to `cases_hybridtest.csv`, next to the existing `base_ut` and `hyb_ut`:
   - `hyb_cc_ut`: `hyb_ut` with `GSw_PRM_CapCredit=1`
   - `hyb_vre_ut`: upv+battery-li and wind-ons+tes-ms
   - a grid-charging case (or a `hyb_ut` change) that builds at least one wrapper with `GridCharging > 0`
   - every new column sets `GSw_gopt=2`
3. **Base equivalence:** run `base_ut` on a git worktree of `upstream/main` and on this branch. Compare `systemcost`, `cap`, `gen_ann`, and the LP equation and variable counts (from the GAMS listing).
   - Differences should come only from the kept PVB/battery changes.
   - Any difference from `tes_ms`/`flex_geo` is a bug.
   - Record the numbers.
4. **Each hybrid Utah case must:**
   - finish all solve years
   - show `error_check` z ≈ 0
   - pass `pytest tests/test_outputs.py --casepath <case>`
   - produce non-empty `gen_plant_h`, `storage_in_grid_h` and `cap_energy_ivrt`
   - build wrappers in at least one config
   - run PRAS with disaggregated GeneratorStorage units
   - give VRE wrappers non-zero `m_cf` and supply-curve-bounded builds
5. **Old bugs as checks:**
   - `Sw_Nuclear=0` bans the nuclear wrappers
   - `GSw_HybridPlant=0` raises in validation
   - mismatched list lengths raise
6. **z54:** run `hyb_z54`, `hyb_cc_z54` and `base_z54` (endyear 2040).
7. **Hand back:** fill in section 9, commit, push (normal push), and tell Ethan.

### Phase 9a — tech-group rules that skip wrappers (added 2026-10-29)
A wrapper belongs only to the STORAGE, HYBRID_PLANT and STORAGE-HYBRID tech groups, so every rule keyed on its gen tech's groups skips it. The z54 runs showed the cost: `hyb_cc_z54` builds 117 GW of gas-cc wrappers, and `hyb_z54` (stress periods) builds none. Copying the group flags wholesale is wrong, because a wrapper's `GEN` includes storage discharge, which burns no fuel. Each rule needs its own wrapper term that uses `GEN_PLANT`.
1. **Gas:** add a set of wrappers whose gen tech is in `gas`. Count their `GEN_PLANT` gas burn in:
   - `eq_gasused` (`GSw_GasCurve` 0 and 3)
   - `eq_gasaccounting_regional` and `eq_gasaccounting_national` (`GSw_GasCurve` 1)
   - the gas objective terms for `GSw_GasCurve` 1 and 2, including `gasprice_adj_r`

   Take these wrappers out of the fixed `fuel_price` term. Mirror the changes in `report.gms` and `6_data_dump.gms` (gas quantity, gas price, fuel cost).
2. **Clean Air Act 111:** `eq_caa_max_cf` limits gas wrappers' `GEN_PLANT`.
3. **Capacity-credit outages:** `capacity_credit.py` gives each wrapper whose gen tech is in `TEMP_DERATE` its gen tech's hourly forced-outage column. Today the wrapper gets a `mean_forced_outage_rate` of 0, while gas-cc gets 3.5%. `b_inputs.gms` sets wrapper `ccseason_cap_frac_delta` from the gen tech.
4. **Rejections:** `check_storage_hybrid` rejects gen techs in `coal` (`eq_caa_rate_standard`, forced coal retirement), `bio` or `cofire` (`eq_bioused`, `eq_biousedlimit`, biomass cost) and `beccs` (`eq_cdr_cap`), until those rules have wrapper terms.
5. **Tests:** unit tests for the rejections and for the outage inheritance.
6. **Reruns:** `hyb_ut`, `hyb_cc_ut` and `hyb_cc_z54`. Check that z stays at its earlier level, that wrapper gas burn appears in `repgasquant`, that the wrapper's `mean_forced_outage_rate` equals gas-cc's, and that new gas wrappers stay within `caa_gas_max_cf`.

### Phase 9b — sanity check (placeholder, added 2026-10-28)
A sanity check that wrapper behavior in the Phase 9 runs is realistic and faithful to actual systems. Ethan and the agent scope it in conversation after Phase 9a is complete; do not start it before then.

## 8. Things the original agent will do in Phase 8 (do not do them)
- Fix every stale path and every claim in `docs/source/storage_hybrid.md` that contradicts the code: inputs.h5 `i`, powerblock subtraction, ramprate source, TES efficiency 0.999, the dispatchable limit, the sign of local charging, PTC, "IDs 1–8".
- Add the "Changes to existing behavior" section: the rename, the PVB equation changes, battery energy-capacity retirement, prescription slack and reporting.
- Draft the PR description.
- Delete this file and push.

If you change something these docs describe, note it in section 9 so the original agent documents the final behavior.

## 9. Results for Phase 8 (fill in)
Filled in 2026-10-28 by the second agent, and updated 2026-10-29 for Phase 9a. All runs are on this machine (Windows, `reeds` env, CPLEX via `GSw_gopt=2` for Utah). Runs went concurrently rather than one at a time, because this machine has 250 GB of memory.

### Commits by phase
| Phase | Commit | Summary |
|---|---|---|
| setup | `74faa48e` | Utah test cases and this file |
| 1 | `7a1a2aea` | single-region PRAS and reporting fixes; CPLEX op2 for Utah |
| 2 | `65ac225b` | upstream-driven adaptations (queue limits, gen-first clones, battery refurbishment, futurefiles, READMEs, z54 to 2040) |
| 3 | `6c494147` | explicit row-cloning registry replaces the heuristic cloner |
| 4 | `20b2cb28` | bans, validation, heat rate, VOM/FOM vintages, financials, LCOE, cleanup |
| 5 | `d0ad2c3a` | VRE wrappers (capacity factors, shared supply curve, RPS, capacity credit) |
| 6 | `0c2f8aed` | PRAS unit disaggregation, outage fallbacks, VRE inflow |
| 7 | `ebfb7bb7` | CI scenario, `check_inputs` entries, unit tests |
| 7b | `5518eb3b` | gen-first timing inputs for wrappers; unit tests in CI |
| 9 | `db5975eb` | Phase 9 case columns |
| 9a | `c0193adb` | gas, Clean Air Act and capacity-credit outage rules cover wrappers; coal, biopower and BECCS gen techs rejected |

Plan-change records: `d8a0ec17`, `308bc18a`, `d349eec3`, `cdb8e736`, `1146328b`, `72a991b6`.

### Phase 1 compile fixes
- The merged code compiled and ran with no GAMS changes.
- Two upstream bugs in single-region runs, both fixed and kept (they belong in the PR as upstream fixes):
  - `make_pras_interfaces` raised `BoundsError` with no lines;
  - `report_calcs.py` raised `KeyError` on an empty `FLOW`.
- CPLEX barrier with `barcolnz 30` reports the Utah 2030 LP infeasible; upstream fails identically. The Utah columns use `GSw_gopt=2`.

### Base equivalence (`base_ut`, upstream `6c175c4f` vs branch `db5975eb`)
- `systemcost`, `cap` and `gen_ann`: identical in every year. `error_check` z = −1.9e-05 in both.
- LP equations: identical in every solve.
- LP variables and nonzeros: +2 each in every solve. The two extra columns are `CAP_ABOVE_LIM(tes,UT,t)` and `CAP_ABOVE_LIM(geo-storage,UT,t)`: the queue-overflow slacks for the two tech groups this branch adds to `cap_penalty.csv`. In a base run no tech uses those groups, so each column has only its objective coefficient. It is harmless.
- `tes_ms` and `flex_geo`: no trace in the base LP.

### Hybrid Utah results
All runs solve every year (model status 1). `test_outputs` fails only on `bars_retirements_additions.png` for every Utah run, base included (see open issues).

Results with the Phase 9a code (`p9a_*` runs, commit `c0193adb`):

| Case | Wrappers built (2040) | `error_check` z | PRAS units | NEUE ppm (2030 last iteration / 2035 / 2040) | Other checks |
|---|---|---|---|---|---|
| `base_ut` | none | −1.9e-05 | — | 0.59 / 0 / 0.041 | identical to upstream; identical to the pre-9a branch, including LP size |
| `hyb_ut` | none | −1.9e-05 | — | 0.59 / 0 / 0.041 | results equal `base_ut` to 1e-16 |
| `hyb_cc_ut` | none | 0 (not written; see open issues) | — | 257 / 332 / 315 (PRAS is diagnostic only in capacity-credit mode) | wrapper `mean_forced_outage_rate` equals gas-cc's (UT 2040: 3.74% cold, 2.95% hot) |
| `hyb_vre_ut` | none (not economic) | −1.9e-05 | — | same as base | results equal `base_ut` to 1e-16 (pre-9a run; no gas wrappers, so 9a does not change it) |
| `nukeban_ut` (`GSw_Nuclear=0`, `GSw_NuclearSMR=0`) | — | — | — | — | nuclear and SMR wrappers inherit `bannew`/`ban` and have no valid new capacity (pre-9a run) |
| `p9s_hyb_ut` (sandbox: `hyb_ut` with gas-wrapper capital × 0.7 and energy capital × 0.5 in the run-local GAMS copy only) | gas-cc+battery (type 5, 0.25 grid charging) 6,317 MW | −2.2e-05 | 26 units | 0.36 / 0.065 / 0 | see below |

- **Pre-9a results, for the record.** Before Phase 9a, `hyb_ut` built 5,016 MW of the type-5 gas-cc wrapper (z 0.000216, 21 PRAS units), and `hyb_cc_ut` built 2,805 MW (12 units). Those builds came from the gaps Phase 9a closed. In Utah (`GSw_GasCurve=2`, static gas prices), plain gas-cc pays the seasonal gas-price multiplier `gasprice_adj_r` and the wrapper did not. A diagnostic run of `hyb_ut` with `GSw_Clean_Air_Act=0` under the 9a code also builds no wrappers, so the price multiplier was the deciding gap there.
- **Wrapper builds now need the sandbox.** With the 9a code, no Utah case builds a wrapper on its own economics. The sandbox run `p9s_hyb_ut` provides the evidence for the build paths. In 2040:
  - every new gas-wrapper vintage runs at exactly `caa_gas_max_cf` = 0.40 of plant-side capacity, and `eq_caa_max_cf` has a positive marginal, so the cap binds;
  - `repgasquant_irt` reports 0.1471 quads for the wrapper. The LP's plant-side burn over all hours is 0.1473 quads. The gap is the stress hours the report drops (see the z note below).
  - the wrapper pays nothing in the fixed-price fuel term, and its gas cost goes through the gas terms ($595M in `op_fuelcosts_objfn`);
  - `gen_plant_h`, `storage_in_grid_h` (grid charging), `gen_storage_h` and `cap_energy_ivrt` are non-empty, and PRAS splits the fleet into 26 units.
- The pre-9a `hyb_ut` run is also valid evidence for the dispatch, grid-charging and PRAS paths. Phase 9a changed none of them.

- **z is stress-period operating cost.** `report.gms` drops stress hours (`h(h)$[not h_rep(h)] = no`, line 122) before it rebuilds costs, but the objective includes operating cost in those hours. In the pre-9a `hyb_ut` 2040, objective fuel in stress hours is $626,924, exactly the fuel gap. The VOM and CO2 gaps are the same kind and also occur in base. `hyb_cc_ut` has no stress periods and z is exactly 0. Every wrapper cost category (capital, FOM, fuel, VOM) matches the objective exactly.
- **VRE wrappers** are not economic in Utah: they cost about the same as separate upv plus battery. Utah and Wyoming also have no onshore-wind supply curve in the current upstream inputs; upstream's Utah run has none either. As agreed, the Phase 5 sandbox runs are the evidence for VRE builds. Those runs cut wrapper capital cost in the run-local GAMS copy only; they are `p5x2_hyb_vre_ut`, `p5y2_cc_vre_ut`, `p5w_vre_wy` and `p6x_hyb_vre_ut`. In them:
  - `m_cf`, `avail`, ILR, CF adjustment, supply-curve data, `rsc_fin_mult` and RPS multipliers equal the gen tech's;
  - plant output stays within `m_cf` × CAP in every hour, and grid charging peaks at exactly 0.25 × CAP;
  - the gen tech's `eq_rsc_INVlim` row includes the wrapper's `INV_RSC`, and no bin is exceeded;
  - PRAS gets the gen tech's inflow profile (mean/capacity = the upv CF, peak/capacity = 1/ILR).
- **Spur lines** (`GSw_SpurScen=1`, Utah to 2030): solves, z = 8.2e-05, and wrappers map to the same spur sites as their gen techs.
- **Validation old bugs:** `runreeds.py` stops before creating a run folder for `GSw_HybridPlant=0` and for mismatched list lengths.
- **CI scenario** `github_StorageHybrid` (run locally, before and after 9a): solves to 2030, z = −0.000188, and builds a 574 MW upv+battery wrapper on its own economics. Its PRAS unit gets the upv_3 inflow profile.

### z54 results
All z54 runs solve every year (model status 1), with `endyear=2040`.

| Case | Code | Wrappers built (2040) | `error_check` z | PRAS wrapper units | NEUE ppm (2020 / 2025 / 2030 / 2035 / 2040) |
|---|---|---|---|---|---|
| `base_z54` | pre-9a (`db5975eb`) | — | 0 (not written) | — | 710 / 55 / 0.40 / 20 / 51 |
| `hyb_z54` (stress periods) | pre-9a | none, including the wind-ons type 9 wrapper | 4.6e-05 | — | 710 / 55 / 0.001 / 0 / 0.02 |
| `hyb_cc_z54` | pre-9a | gas-cc+battery (type 2) 117.0 GW in 22 regions | 0 (not written) | e.g. PA 32.5 GW in 132 units | 710 / 55 / 0.74 / 23 / 59 |
| `hyb_cc_z54` | 9a (`c0193adb`) | none | 0 (not written) | — | 710 / 55 / 0.41 / 24 / 56 |

- **The pre-9a `hyb_cc_z54` build came from the gaps 9a closed.** Its switches match the 9a run, so the comparison is clean. The 117 GW of wrappers replaced 110 GW of plain gas-cc and about 70 GW of upv, wind and battery. They cut reported system cost by $53.4B (2.2%), almost all of it investment.
  - The capacity-credit gap mattered most. Wrappers had a `mean_forced_outage_rate` of 0, while gas-cc had about 3.5%. With 9a the two are equal (PA 2040: 3.50% cold, 3.42% hot).
  - The gas gap shifted the fuel price. Wrapper gas burn was missing from the gas supply curves, so the national gas price was understated ($2.89 against $3.11 per MMBtu in 2040), even though total gas burn was higher.
  - The Clean Air Act gap let new wrappers run at a 0.63 capacity factor against the 0.40 cap.
- **The stress-period run `hyb_z54` built no wrappers even before 9a**, because stress periods and PRAS already applied the gen tech's outages. Phase 9a only tightens the rules for gas wrappers, so I did not rerun it.
- **`base_z54` is not a matched base for either hybrid z54 case** (see open issues). It uses capacity credit like `hyb_cc_z54`, but the retirement settings of `hyb_z54`. Comparisons against it mix wrapper effects with those settings.
- `hyb_z54` results from code before Phase 3 (`6c494147`) include phantom prescribed SMR builds. The old cloner copied the X-energy and Natrium rows of `demonstration_plants.csv` to every nuclear-SMR wrapper (2.66 GW over 4 wrappers). The runs above use current code.

### Behavior changes the docs must describe
- **Refurbishment (Phase 2):** battery-backed wrappers get one battery energy refurbishment every `batt_years_until_refurb` years over their gen tech's `maxage`. The discounted cost beyond battery_li's single refurbishment goes into `storage_hybrid_refurb_energy.csv`.
- **Row-cloning registry (Phase 3, 7b):** `STORAGE_HYBRID_ROW_CLONES` in `copy_files.py` lists every copied input with `storage`, `gen` or `gen_only` precedence.
  - Outage inputs are `gen_only`.
  - `years_until_endogenous`, `firstyear`, `degradation_annual`, `nat_gen_tech_frac`, `maxage`, `unitsize`, `i_c` and `employment_factor_plant` are gen-first.
  - `ramprate` is storage-first on purpose: GAMS sets it from the storage tech, and it only sets `reserve_frac`.
  - GAMS also sets wrapper `firstyear`, `degrade_annual`, `min_retire_age`, `maxage`, outage rates and `nat_gen_tech_frac` from the gen tech, so the copies only keep the case inputs consistent.
- **Bans (Phase 4):** a wrapper inherits `ban`, `bannew` and `tech_banned` from either component. Standalone `tes_ms` and `flex_geo*` are `bannew`.
- **Validation rules (`reeds/checks.py` `check_storage_hybrid`):**
  - requires `GSw_HybridPlant` 2 or 3;
  - Types must be non-empty, alphanumeric and unique;
  - each list needs 1 or N values;
  - BCR > 0 and 0 ≤ GridCharging ≤ BCR;
  - gen techs must be in GENTECH and not an upgrade, cooling variant, storage, H2-fueled, hydro or distributed PV;
  - gen techs may not burn coal or biomass (`coal`, `cofire`, `bio`, `beccs`; Phase 9a), because the Clean Air Act coal rules, biomass supply curve and carbon-removal limits have no wrapper terms;
  - storage techs must be in STORAGE and not hybrid_plant, demand_flex or RSC;
  - TES may not pair with a VRE gen tech; flex-geo needs a geothermal gen tech.
- **Costs (Phase 4):**
  - heat rate, VOM and FOM are vintage-averaged from the gen tech;
  - wrappers inherit the gen tech's emissions, capture and upstream methane;
  - gas wrappers carry the gas cost-recovery penalty;
  - the shared-powerblock cost is no longer subtracted for battery wrappers;
  - LCOE includes energy capital and energy FOM.
- **VRE wrappers (Phase 5):**
  - copy the gen tech's `cf_in` in GAMS;
  - take the gen tech's `cf_tech` and `RSC` flags;
  - share its supply curve through `storage_hybrid_rsc_agg` (formerly geothermal-only);
  - take the UPV ILR (so wrapper CAP and BCR are DC-based, like PVB);
  - pay the gen tech's `rsc_fin_mult`;
  - join its spur lines;
  - inherit every RPS/CES category, voluntary RECs and the CCS partial CES credit;
  - get capacity credit from their own resources, which reuse the gen tech's profile.
- **Supply-curve cost (Phase 5):** a wrapper's supply-curve investment is charged once in the objective, through its own `rsc_agg` entry.
- **Spur-site limit (Phase 5):** with endogenous spur lines, only a wrapper's `GEN_PLANT` counts against site availability.
- **PRAS mapping (Phase 6):**
  - each wrapper fleet becomes `GeneratorStorage` units of the gen tech's unit size, capped at the regional PRM-based maximum (`pras_max_unitsize_prm`);
  - fleets with no forced outages stay one unit;
  - per unit of capacity U: charge = discharge = BCR × U, energy = CAP_ENERGY × U/CAP, grid withdrawal = GridCharging × U, grid injection = (1+BCR) × U;
  - inflow = U for dispatchable gen techs, or the gen tech's available output for VRE;
  - outage lookups fall back from the wrapper to its gen tech;
  - approximation: the LP caps charge plus discharge jointly at BCR × CAP, while PRAS caps each separately. PRAS gains nothing by doing both in the same hour, so they should agree in practice.
- **Reporting fix (Phase 5):** `report.gms` no longer multiplies energy-capacity FOM by ILR.
- **Upstream fix (Phase 5):** `writecapdat.py` no longer matches wrapper vintage rows by substring; that had doubled upv/wind prescribed builds whenever a VRE wrapper was configured.
- **Tests (Phase 7):**
  - CI runs `github_StorageHybrid` and `tests/test_storage_hybrid.py`;
  - the new scenario keeps `github_Pacific`'s end year of 2030, so its nuclear wrapper exercises setup only;
  - `check_inputs` checks the wrapper parameters;
  - `gridcharge_ratio` is not checked, because zero is a valid value that GAMS does not store.
- **Tech-group rules (Phase 9a):** a wrapper belongs only to the STORAGE, HYBRID_PLANT and STORAGE-HYBRID groups, so a rule keyed on its gen tech's group skips it unless the rule has a wrapper term. Copying group flags wholesale would be wrong, because a wrapper's `GEN` includes storage discharge, which burns no fuel. Phase 9a adds these wrapper terms:
  - `storage_hybrid_gas(i)` (`b_inputs.gms`) holds wrappers whose gen tech is in `gas`.
  - Their plant-side burn (`GEN_PLANT`) counts in `eq_gasused`, `eq_gasaccounting_regional`, `eq_gasaccounting_national` and the gas objective terms for `GSw_GasCurve` 1 and 2, including the seasonal multiplier `gasprice_adj_r`. They are out of the fixed-price fuel term.
  - `eq_caa_max_cf` limits their `GEN_PLANT` to `caa_gas_max_cf` of CAP, unless the gen tech is CCS.
  - `6_data_dump.gms` (`repgasquant`, which sets next year's gas price) and `report.gms` (gas quantity, price, gas share and fuel cost) count the same burn.
  - Capacity credit keeps the gen tech's forced-outage rates for wrappers (`reeds.techs.add_storage_hybrid_gentech_members`, used on the `TEMP_DERATE` list in `capacity_credit.py`). Before 9a, the wrapper's `mean_forced_outage_rate` was 0.
  - Wrappers take the gen tech's `quarter_cap_frac_delta` and `ccseason_cap_frac_delta` (seasonal capacity changes). Under default settings these are zero for new vintages.

### Audit claims that turned out wrong
- Wrapper VOM did not skip regional multipliers (`cost_vom` has none); the real gap was vintage averaging, and power FOM had it too.
- Geothermal `rsc_fin_mult` needed no composition (it is 1).
- The PRAS `KeyError` risk applied only to wrappers without outage rows, which after Phase 5 are the VRE wrappers. Gas-cc wrappers already had their gen tech's hourly rates.
- Nuclear wrappers were never buildable before 2034. GAMS already sets wrapper `firstyear` from the gen tech (`b_inputs.gms` line 1195). Only the case-input copies disagreed (fixed in 7b).
- The Phase 1 plan to add wrappers to `error_check('z')`'s energy-capital correction was wrong. Wrapper energy capital uses the storage-side multiplier in both the objective and the report, so wrappers are excluded instead.

### Open issues
- **Local plotting crash:** `single_case_plots.py` segfaults in this Windows environment when `map_zone_capacity` opens `report.xlsx` with `openpyxl`. It does this for base runs and for upstream's script too, and it stops the script before `bars_retirements_additions.png`. CI on Linux is the real check.
- **`check_error.py` fragility (upstream):** it raises `KeyError` when z rounds to exactly 0 (capacity-credit runs).
- **`test_read_h5_files.py::test_read_h5py_file` fails on upstream too.**
- **PVB supply-curve double count (upstream, not changed):** the objective charges PVB's supply-curve investment through both upv's and its own `rsc_agg` entries, while the report counts it once.
- **`base_z54` matches neither hybrid z54 case.** It sets `GSw_PRM_CapCredit=1` (like `hyb_cc_z54`), but `GSw_Retire=5`, `GSw_NukeNoRetire=1` and `GSw_RetirePenalty=1` (like `hyb_z54`). `hyb_cc_z54` sets `GSw_Retire=4` and the other two to 0 (commit `d41cafeb`). A matched base needs one more column, or `hyb_cc_z54` back on the `hyb_z54` retirement settings.
- **No dispatchable wrapper is economic in the test cases with 9a.** Wrapper builds are exercised by the gas sandbox run `p9s_hyb_ut`, the VRE sandbox runs from Phase 5, the CI scenario's upv+battery wrapper, and the pre-9a runs, which used the same dispatch and PRAS code.
- **Coal, biopower and BECCS wrappers** are rejected rather than supported (Phase 9a). Supporting them needs wrapper terms in `eq_caa_rate_standard` and the forced coal retirement, `eq_bioused`, `eq_biousedlimit` and the biomass cost, and `eq_cdr_cap`.
- **Seasonal derate on the storage side:** wrappers apply `seas_cap_frac_delta` to storage discharge as well as plant output (`c_model.gms` storage capacity limit). That fits TES, which discharges through the shared powerblock. For a battery it is approximate, and it only matters when `thermal_summer_cap_delta` is nonzero (a climate-heuristics setting).
- **POI sizing** counts wrapper CAP but not storage discharge (BCR × CAP).
- **VRE wrappers** add no operating-reserve requirement (unlike PV/PVB), and curtailment reports leave them out.
- **LCOE** VOM omits the storage-side VOM.
- **`hybrid_cc_derate`** is always 1, for PVB and wrappers alike (never computed).
- **MGA** weights wrappers once for each subset they belong to (Phase 2 note; not changed).
