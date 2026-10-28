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

## 8. Things the original agent will do in Phase 8 (do not do them)
- Fix every stale path and every claim in `docs/source/storage_hybrid.md` that contradicts the code: inputs.h5 `i`, powerblock subtraction, ramprate source, TES efficiency 0.999, the dispatchable limit, the sign of local charging, PTC, "IDs 1–8".
- Add the "Changes to existing behavior" section: the rename, the PVB equation changes, battery energy-capacity retirement, prescription slack and reporting.
- Draft the PR description.
- Delete this file and push.

If you change something these docs describe, note it in section 9 so the original agent documents the final behavior.

## 9. Results for Phase 8 (fill in)
- Commits by phase:
- Phase 1 compile fixes:
- Base equivalence (`base_ut` upstream vs branch): systemcost, cap, gen_ann, LP sizes, and the cause of each difference:
- Hybrid Utah results (per case): wrappers built, error_check, test_outputs, PRAS:
- z54 results:
- Behavior changes the docs must describe (refurbishment choice, PRAS mapping and approximations, VRE wrapper behavior, validation rules, anything else):
- Audit claims that turned out wrong:
- Open issues:
