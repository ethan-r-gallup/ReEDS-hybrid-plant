# Handoff: upstream update, wave 0 replan, and the storage-hybrid PR

To the Claude agent on the lab machine. Claude wrote this on Ethan's laptop on 2026-11-17. It records Ethan's decisions and the plan.

**What to do first.** Read this whole file. Then write a plan for Phases A to F below, show it to Ethan, and wait for his approval before you change anything. Delete this file and `HANDOFF_wave0_PR_draft.md` in the last commit of Phase F.

## 1. Working rules

- **Phase gates.** After each phase, report the result to Ethan and wait for his go-ahead before you push or start the next phase.
- **Branches.**
  - Paper work goes only on `nuclear-tes-paper`, never on `storage-hybrid-pr`. `storage-hybrid-pr` becomes the upstream PR.
  - Merges flow one way: upstream `main` → `storage-hybrid-pr` → `nuclear-tes-paper`.
  - This file lives only on `nuclear-tes-paper`.
- **No endogenous learning code** on either branch.
- **Python env.** Use the conda env `reeds`; `reeds2` is rejected.
- **Ask Ethan first** in these cases:
  - before you implement any OBBBA change (Phase C);
  - before any PR decision: test level, charge code, reviewers, draft or ready (Phase F). Ethan wants to settle these with you while you work, after the fork is up to date.
- **Project hub.** Ethan tracks this project as `nuclear-tes` in the private repo `ethan-r-gallup/todo-time-management`. Update `status/nuclear-tes.md` there when the project's state changes, following `status/README.md`.

## 2. Where things stand

**Branches** (as of 2026-11-17)

| Branch | Tip | Notes |
|---|---|---|
| `storage-hybrid-pr` | `73cfa977` | Merge base with upstream is `6c175c4f`. |
| upstream `ReEDS-Model/ReEDS` `main` | `3499d916` | 372 commits ahead of `storage-hybrid-pr`. |
| `nuclear-tes-paper` | this commit | `storage-hybrid-pr` plus the paper commits below. |

**Paper-only changes on `nuclear-tes-paper`.** Keep all of them through the merges. `TESTS_nuclear_tes_paper.md` lists them with commits.

| Commit | Change |
|---|---|
| `d0e060a5` | `GSw_interpolate_mandates`: piecewise-linear national generation mandates, for example `2035-0.1_2050-0.25`. |
| `a5611142` | The `Nuke` column in `inputs/national_generation/nat_gen_tech_frac.csv`. |
| `8a148ad1` | `GSw_NuclearCapMandate` and the trajectory files in `inputs/capacity_mandate/`. |
| `1338ca45` | The `tes_threshold_modrte_*` cost files. These are no longer used by the casefiles. |
| `e2ee8679` | The `hourly_load.py` build-twice gate. |
| `3e4a1fc4` | `GSw_NuclearFirstYear`, in `reeds/input_processing/copy_files.py`. |
| `f6257725`, `3a5942ed` | Split TES wrapper costing: `GSw_StorageHybrid_TESCostSplit`, `_TESStorShare` and `_TESAddonMult` in `b_inputs.gms`, `2_financials.gms` and `reeds/checks.py`, plus the docs section in `docs/source/storage_hybrid.md`. |
| `c7ae8e86` | `GSw_NuclearLarge`, which bans new large nuclear only. |

**Fixes that may belong upstream.** Raise these with Ethan in Phase F.

- **`runreeds.py -s` order bug.** Commit `97c8db39` is on the paper branch only. Before the fix, `runreeds.py -s` paired case names with switches by position.
- **pcm path bug.** It is still present on upstream `main` at `3499d916`. `runreeds.py` writes `python reeds/postprocessing/run_pcm.py`, but the script is at `postprocessing/run_pcm.py`, so `pcm=1` fails. Keep `pcm=0`.
- **TES credit mismatch.** On `storage-hybrid-pr`, `incentives_noira.csv` gives TES a 30% ITC through 2050, while BATTERY drops to 0 after 2024.

**Superseded.** No one ran the 48-case `cases_nuclearstor_paper_v5_wave0.csv`. Delete it in Phase D. Step 3 of `TESTS_nuclear_tes_paper.md` describes that superseded design, so rewrite Step 3.

## 3. Decisions

Ethan and Wesley (NLR) made these decisions. Ethan confirmed them with Claude on 2026-11-17.

1. **Mandates.**
   - Waves 0–2 use national generation-share mandates only (`GSw_interpolate_mandates`).
   - The sensitivity wave adds a few capacity-mandate runs.
2. **Wave 0 is a time-resolution test on n25 only.** The n25 mandate is `2035-0.1_2050-0.25`.
   - It covers a control (hybrids off) and the TES add-on at 20, 40 and 60% (`GSw_StorageHybrid_TESAddonMult` = 0.2, 0.4, 0.6).
   - Each of the 3-hour, 2-hour and 1-hour dispatch blocks gets all four cases. The block length is set by `GSw_HourlyChunkLengthRep` and `GSw_HourlyChunkLengthStress`.
3. **Two wave 0 casefiles.**
   - **Lab casefile:** the 3-hour cases (4 runs), run on the lab machine.
   - **NLR casefile:** the 2-hour and 1-hour cases (8 runs). Wesley runs it on the NLR cluster and posts each run's outputs h5 to OneDrive. NLR has no agent.
4. **Spatial resolution.** Use the default zone set, `z90` on current `main`, instead of `z54`. Remove the `GSw_ZoneSet` pin.
   - Runs take longer.
   - The lab machine (24 cores, 253 GB) runs 2 cases at a time.
5. **Incentives.** Use the OBBBA incentives (`incentives_suffix=obbba`, the upstream default) in every run, not `none`. OBBBA's battery credits affect how competitive hybrid nuclear is.
   - **The OBBBA phase-down must be modeled accurately.** See Phase C.
6. **Clean Air Act.** Set `GSw_Clean_Air_Act=0` in every casefile. This turns off the Section 111 rules for existing coal and new gas. Leave `GSw_CSAPR` at its default of 1.
   - Section 111: EPA's repeal of the 2024 power plant carbon rule took effect on 2026-11-16, and Wesley said the remaining provisions are ending.
   - CSAPR: ReEDS models the 2011 CSAPR Phase 2 ozone-season NOx budgets, which are still in force. EPA's 2026 rollback proposal targets the 2023 Good Neighbor Plan, which the Supreme Court stayed in 2024 and ReEDS does not model.
7. **Unchanged from v5.**
   - Wrapper set and costing:
     - five nuclear-SMR + molten-salt TES wrapper types at BCR 0.1, 0.25, 0.5, 0.75 and 1.0, with grid charging 0;
     - split TES costing on, with `TESStorShare=0.203`;
     - `plantchar_tes=tes_ATB_2024_moderate`.
   - Nuclear build rules:
     - SMR-only: `GSw_NuclearLarge=0`;
     - `GSw_NuclearFirstYear=2031`;
     - `GSw_NuclearDemo=0`;
     - `GSw_NukeStateBan=1`.
   - Scenario and timing:
     - the four AEO 2026 baseline scenarios;
     - yearset `2010..2030..5_2032..2050..3`;
     - `GSw_LoadProfiles=EER2025_IRAlow`;
     - interday linkage 0;
     - `pcm=0`.
   - Recheck every pin against the defaults and switch names of the merged code.

## 4. Plan

### Phase A: update `storage-hybrid-pr` to upstream `main`

1. Merge upstream `main` into `storage-hybrid-pr`. Resolve conflicts so that upstream behavior is preserved and the storage-hybrid feature still works.
2. Run the storage-hybrid regression test and the CI case. Step 1 of `TESTS_nuclear_tes_paper.md` describes them, and `docs/source/storage_hybrid.md` describes the feature.
3. Check that the default case is unchanged with `GSw_StorageHybrid=0`.
4. Report to Ethan. Push after he approves.

### Phase B: update `nuclear-tes-paper`

1. Merge `storage-hybrid-pr` into `nuclear-tes-paper`.
2. Confirm that every paper-only change in section 2 survived.
3. Rerun the static checks: `reeds.inputs.parse_cases`, `runreeds.check_compatibility` and `reeds.checks.check_storage_hybrid` on the casefiles.

### Phase C: accurate OBBBA phase-down

Ethan wants the statutory OBBBA phase-down in the runs, even if upstream's file leaves it out.

1. **Compare upstream's `inputs/financials/incentives_obbba.csv` with the statute.** At `3499d916`, the `NUCLEAR`, `BATTERY` and `TES` rows stop at 2032 construction starts with a flat 30% ITC.
   - As Claude understands the law, the technology-neutral credits (45Y and 48E) for these techs keep 100% for construction starting through 2033. They fall to 75% in 2034, 50% in 2035, and 0 after.
   - Check this against the statute and the documentation that NLR's file cites.
   - Check also the wind and solar termination dates, the safe-harbor and placed-in-service windows (`safe_harbor`, `t_max_online`), and how storage-hybrid wrappers inherit credits. Wrappers take their gen tech's credit, and the financing weights in `2_financials.gms` blend the gen and storage parts.
2. **If upstream differs from the statute, stop and ask Ethan** before you implement anything. Propose how to fix it. The proposal should say:
   - whether to edit the file or add a new incentives file;
   - which branch the change goes on;
   - whether the fix should also go upstream.

### Phase D: build the wave 0 casefiles

1. Update the generator, `z-ethan/make_paper_v5_casefiles.py`. It is committed on this branch so you have it. Call the new setup v6, and write two files:
   - `cases_nuclearstor_paper_v6_wave0_lab.csv`: `w0_h3_n25_ctrl`, `w0_h3_n25_ta20`, `w0_h3_n25_ta40`, `w0_h3_n25_ta60`.
   - `cases_nuclearstor_paper_v6_wave0_nlr.csv`: the same four cases with `h2`, then the same four with `h1`.
2. Change these pins from v5:
   - remove `GSw_ZoneSet`;
   - set `incentives_suffix` to `obbba`, or to the phase-down file Ethan approves in Phase C;
   - add `GSw_Clean_Air_Act=0`;
   - leave `GSw_CSAPR` at its default.
3. Keep `GSw_HourlyChunkLengthRep` and `GSw_HourlyChunkLengthStress` equal within each case.
4. Delete `cases_nuclearstor_paper_v5_wave0.csv`.
5. Validate both files with the three checks in Phase B.
6. Rewrite Step 3 of `TESTS_nuclear_tes_paper.md` for the new wave 0, and update the wave 0 check script:
   - **Cases:** n25 only. Expect 4 cases in the lab casefile and 8 in the NLR casefile, and accept `h2` in the case-name regex.
   - **Inputs:** read the NLR outputs from their h5 files, not CSVs. Check how `report_dump.py` writes `outputs.h5`.
   - **Large nuclear:** keep the check that it never grows.
   - **Energy-share test:** keep it one-sided, with 2 points of slack.
7. **Give memory estimates, and mark them as estimates.** A `z54`, 3-hour case peaked at about 60 GB. `z90` has about 1.7 times as many zones, and 2-hour and 1-hour blocks have 1.5 and 3 times as many timeslices.
   - Measure the peak memory of the first lab run.
   - Give Ethan the figure for his email to Wesley.

### Phase E: run the lab casefile

1. Run `python runreeds.py -b v6w0 -c nuclearstor_paper_v6_wave0_lab -r 2` on the lab machine.
2. Watch the first case's peak memory, and report it to Ethan.
3. When all 4 cases finish, run the check script and report the results.

### Phase F: open the storage-hybrid PR

1. Before you fill anything in, settle these with Ethan:
   - the test level: the Pacific light test, or full-US Mid_Case and USA_decarb comparison reports against `main`, as `docs/source/developer_best_practices.md` describes;
   - the charge code;
   - the reviewers. `@wesleyjcole` (Wesley) will review; ask Ethan whether to add `@aschleif`, whom the template lists for hybrids;
   - draft or ready;
   - whether the `-s` and pcm fixes go in this PR, a separate PR, or issues.
   Ethan's own default is a draft PR. Ask Ethan anyway.
2. Fill in `.github/PULL_REQUEST_TEMPLATE.md`. Start from `HANDOFF_wave0_PR_draft.md`, an older draft written before the upstream merge, and update it to the merged code. Include the LLM-use section: Claude Code wrote most of the code under Ethan's direction.
3. Run the tests at the agreed level.
4. Open the PR from `storage-hybrid-pr` after Ethan approves the text.

**After Phase D is pushed,** Ethan emails Wesley the branch name and `cases_nuclearstor_paper_v6_wave0_nlr.csv`. Give Ethan the exact command and the memory figures for that email.

## 5. Plan after wave 0

- **Wave 1:** a broad TES add-on sweep (20/40/60/80/100%) on the generation-share mandates (base, n15, n20, n25, n50), at the resolution wave 0 selects.
- **Wave 2:** a fine sweep around each mandate's breakeven.
- **Wave 3:** sensitivities around the breakeven: a few capacity-mandate runs (`GSw_NuclearCapMandate`), new large nuclear allowed (`GSw_NuclearLarge=1`), and others to be chosen.

## 6. Open items that don't block these phases

- **PNNL heater.** Check whether the $113.5/kW "heater" in PNNL-33283 section 4.8.1 is an electric heater or a steam-to-salt exchanger. It is one of the three items in `TESStorShare=0.203`.
- **Hub status file.** `PR_BODY_storage_hybrid.md` is listed in the hub status file but no longer exists on Ethan's laptop. The draft committed here replaces it.
