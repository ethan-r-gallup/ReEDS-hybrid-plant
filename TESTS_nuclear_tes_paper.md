# Test checklist for the `nuclear-tes-paper` branch

This branch adds the nuclear+TES paper inputs to `storage-hybrid-pr`. A machine with enough memory for ReEDS, GAMS and Julia runs runs the steps below and records each result in the table at the end. On 2026-11-18 the branch merged `storage-hybrid-pr`, which now includes upstream ReEDS `main` at `3499d916`.

## What the branch changes

The branch adds these commits on top of `storage-hybrid-pr`:

| Commit | Change |
|---|---|
| `d0e060a5` | `GSw_interpolate_mandates`: the national generation mandate follows a piecewise-linear trajectory, for example `2035-0.1_2050-0.15` |
| `a5611142` | `Nuke` column in `nat_gen_tech_frac.csv`: only `Nuclear` and `Nuclear-SMR` count toward the mandate |
| `8a148ad1` | `GSw_NuclearCapMandate`: a national floor on nuclear capacity (`eq_nuclear_cap_mandate`), with trajectories in `inputs/capacity_mandate/` |
| `1338ca45` | `tes_threshold_modrte_{pct}pct.csv`: TES cost sensitivity files at 10–200% of ATB 2024 moderate |
| `e2ee8679` | `hourly_load.py`: builds the load twice, compares the two builds, and validates the result before it writes `load.h5` |
| `923f48c5`, `401e1622` | The v5 core casefile (18 cases) |
| `c7ae8e86` | `GSw_NuclearLarge`: turns off new large nuclear only; the paper casefiles set 0 |
| `f6257725`, `3a5942ed` | `GSw_StorageHybrid_TESCostSplit`, `_TESStorShare` and `_TESAddonMult`: split TES wrapper costing, with a multiplier on the TES add-on only |
| `3e4a1fc4` | `GSw_NuclearFirstYear`: overrides the first year new nuclear can be built; the paper casefiles set 2031 |
| `97c8db39` | `runreeds.py -s`: keeps casefile order so case names line up with their switches |
| `6f228a5a` | `incentives_obbba_phasedown.csv`: OBBBA incentives with the statutory 45Y/48E phase-down for 2033-2035 construction starts |
| `debb5275` | `cases_hybridtest.csv`: paper-only quick tests (Utah + Nevada and full-US z54) |
| (latest) | v6 wave 0 casefiles from `z-ethan/make_paper_v6_casefiles.py` |

## Setup

1. Check out the branch: `git fetch origin && git checkout nuclear-tes-paper`.
2. Activate the conda env `reeds` (pandas 3). The env `reeds2` fails the version check.
3. Make sure Julia is set up and `Manifest.toml` exists at the repo root. The casefiles use PRAS stress periods (`GSw_PRM_StressIterateMax` > 0), so the runs need ReEDS2PRAS.

## Step 1: storage-hybrid regression test

```
python runreeds.py -b hybtest -c hybridtest -r 7
python runreeds.py -b ntpci -c test -s github_StorageHybrid -r 1
python -m pytest tests/test_storage_hybrid.py
```

This step checks that the merged code compiles, solves, and builds wrappers on this branch.

`cases_hybridtest.csv` is paper-only. `storage-hybrid-pr` dropped it because upstream now rejects single-zone runs with PRAS on. Its small cases (`*_utnv`) use Utah and Nevada at z54, which is two zones joined by a transmission link. They use hierarchical clustering with 24 periods, so they pass upstream's checks without `-f`. The z54 cases cover the full US.

Pass criteria:
- All 7 `hybridtest` cases finish, and every solve is optimal.
- No `hyb_*` case builds wrappers at default costs. That has been true since Phase 9b and is not a failure.
- `github_StorageHybrid` (the CI case, `GSw_StorageHybrid_CostMult=0.5`) solves to 2030 and builds upv+battery wrappers: 55.8 GW in 8 regions after the 2026-11-17 upstream merge. This is the case that checks wrapper builds. `pytest tests/test_outputs.py --casepath runs/ntpci_github_StorageHybrid` passes, except for `bars_retirements_additions.png`, a local plotting failure that upstream `main` also has.
- The unit tests pass.

## Step 2: v5 core smoke test

```
python runreeds.py -b v5core -c nuclearstor_paper_v5_core -r 3
```

Memory: each full-US case peaks at about 60 GB in ReEDS2PRAS. On a 253 GB machine, `-r 6` failed with Julia `OutOfMemoryError` and `CPLEX Error 1001`, and `-r 3` ran clean. Set `-r` to about the machine's memory divided by 80 GB.

To rerun only some cases, pass them with `-s`. Before the fix in this branch, `runreeds.py` paired `-s` case names with switches by position, so a `-s` list out of casefile order ran cases under the wrong names. After any `-s` run, check `inputs_case/switches.csv` in each run folder.

The core file has 18 cases:
- `main_test_{base,n15,n20,n25,n50}` and `ctrl_{base,n15,n20,n25,n50}`: no mandate, then energy mandates that rise to 15, 20, 25 and 50% of generation in 2050. `main_test_*` has hybrids on. `ctrl_*` has hybrids off.
- `capm_{atb,mck,cop28,eo25}_{base,ctrl}`: capacity mandates (floor mode). `_base` has hybrids on. `_ctrl` has hybrids off.

Each case solves 12 years: 2010, 2015, 2020, 2025, 2030, 2032, 2035, 2038, 2041, 2044, 2047 and 2050.

Pass criteria, in order:

1. **GAMS compile.** Each case gets past `b_inputs.gms` and `c_model.gms` without a compile error. The new code is the `$include` of `nuclear_cap_trajectory`, the set `nuclear_storage_hybrid(i)`, and the equations `eq_nuclear_cap_mandate` and `eq_nuclear_cap_mandate_ub`.
2. **Load gate.** Each case's log prints `Load builds 1 and 2 agree` (or a later pair of builds). If a case prints `WARNING: load builds ... disagree` 12 times and stops, the load build is not deterministic on that machine. Record the case name and the message.
3. **Optimal solves.** Every solve year in every case is optimal.
4. **Capacity floor.** In each `capm_*` case, total nuclear capacity is at or above the trajectory in each solve year from 2032 to 2050. Total nuclear capacity counts `nuclear`, `nuclear-smr` and the `storage-hybrid-*-nuclear*` wrappers. The casefiles set `GSw_NuclearFirstYear=2031`, so new nuclear can be built from 2031, the year the trajectories start to rise. 2032 is the first solve year at or after 2031. Without the switch, the base inputs give 2034 (`this_year` 2026 + 8 years in `years_until_endogenous.csv`). In the `_ctrl` cases the floor should bind in most years.
   Also check that `firstyear` in `inputs_case/inputs.h5` is 2031 for `Nuclear` and `Nuclear-SMR`.
5. **Energy mandate.** In `n15`, `n20`, `n25` and `n50`, the 2050 nuclear share of generation is close to 15, 20, 25 and 50%. The mandate's base is bus-bar load, not total generation. So the share of total generation can sit up to about 1–2 percentage points below the target.
6. **Hybrids only in the test cases.** The `ctrl_*` and `capm_*_ctrl` cases build no `storage-hybrid-*` capacity. The test cases may or may not build wrappers: the paper studies exactly that. Record the 2050 wrapper capacity in each test case.
7. **No demo plants.** No case builds the prescribed nuclear demonstration plants (`GSw_NuclearDemo=0`).

### Feasibility risk to watch

New nuclear can be built from 2031, and 2032 is the first solve year that the mandate applies to. The 2032 solve covers new builds for 2031 and 2032:

| Trajectory | 2032 floor (GW) | 2035 floor (GW) | Build needed by 2032 above about 97 GW existing |
|---|---|---|---|
| `abou_jaoude` (atb) | 98.8 | 100 | about 2 |
| `mckinsey` (mck) | 104 | 114.5 | about 7 |
| `cop28` | 111 | 132 | about 14 |
| `eo2025` (eo25) | 117 | 147 | about 20 |

If any `capm_*` case is infeasible in 2032 or 2035, record it and stop. Do not change the trajectories. The fix is a modeling decision for Ethan.

### Check script

Run this script after the core batch finishes, from the repo root in the `reeds` env. Edit `BATCH` if you used another batch name. The script reads `outputs/cap.csv`: `reeds.io.read_output(path, 'cap_out')` returns an empty table in this fork. It checks each floor against the trajectory the run actually used, `inputs_case/nuclear_cap_trajectory.csv`, so a mislabeled run folder can't hide a violation.

```python
import os
import pandas as pd

BATCH = 'v5core'
TARGET = {'n15': 0.15, 'n20': 0.20, 'n25': 0.25, 'n50': 0.50}

def is_nuclear(i):
    i = str(i).lower()
    return i in ('nuclear', 'nuclear-smr') or (i.startswith('storage-hybrid-') and 'nuclear' in i)

def is_wrapper(i):
    return str(i).lower().startswith('storage-hybrid-')

rows = []
for case in sorted(os.listdir('runs')):
    if not case.startswith(BATCH + '_'):
        continue
    path = os.path.join('runs', case)
    name = case[len(BATCH) + 1:]
    if not os.path.exists(os.path.join(path, 'outputs', 'cap.csv')):
        print(f'{name}: no outputs, run did not finish')
        continue
    cap = pd.read_csv(os.path.join(path, 'outputs', 'cap.csv'))
    cap.columns = ['i', 'r', 't', 'MW']
    gen = pd.read_csv(os.path.join(path, 'outputs', 'gen_ann.csv'))
    gen.columns = ['i', 'r', 't', 'MWh']
    nuc_cap = cap[cap.i.map(is_nuclear)].groupby('t').MW.sum() / 1e3
    wrap_cap = cap[cap.i.map(is_wrapper)].groupby('t').MW.sum() / 1e3
    gen50 = gen[gen.t.astype(int) == 2050]
    share = gen50[gen50.i.map(is_nuclear)].MWh.sum() / gen50.MWh.sum()
    row = {
        'case': name,
        'nuc_GW_2050': round(nuc_cap.get(2050, 0), 1),
        'wrapper_GW_2050': round(wrap_cap.get(2050, 0), 1),
        'nuc_share_2050': round(share, 3),
    }
    traj_file = os.path.join(path, 'inputs_case', 'nuclear_cap_trajectory.csv')
    switches = pd.read_csv(
        os.path.join(path, 'inputs_case', 'switches.csv'), header=None, index_col=0
    ).squeeze(1)
    if int(switches['GSw_NuclearCapMandate']) and os.path.exists(traj_file):
        row['traj'] = switches['GSw_NuclearCapMandateScen']
        traj = pd.read_csv(traj_file, index_col=0).squeeze(1) / 1e3
        years = [t for t in nuc_cap.index if int(t) >= 2032]
        row['min_floor_slack_GW'] = round(min(nuc_cap[t] - traj[int(t)] for t in years), 2)
    for k, v in TARGET.items():
        if name.endswith('_' + k):
            row['share_target'] = v
    rows.append(row)

df = pd.DataFrame(rows).set_index('case')
print(df.to_string())
ctrl = df.index.str.startswith('ctrl_') | df.index.str.endswith('_ctrl')
assert (df.loc[ctrl, 'wrapper_GW_2050'] == 0).all(), 'a control case built wrappers'
if 'min_floor_slack_GW' in df:
    assert (df['min_floor_slack_GW'].dropna() >= -0.01).all(), 'a capacity floor was violated'
print('checks passed')
```

## Step 3: wave 0, the time-resolution test

The paper runs in waves. Every wave uses the same wrapper set: nuclear-SMR with molten-salt TES at BCR 0.1, 0.25, 0.5, 0.75 and 1.0 (wrapper types 1 to 5). New large nuclear is off in every case, controls included (`GSw_NuclearLarge=0`), so the SMR is the only new reactor option; existing large nuclear remains. The paper studies what onsite TES adds to an SMR, not which reactor size gets built. The core file above used an older set of 6 types and the older costing, so its test cases are not part of any wave.

1. **Wave 0** picks the time resolution for all later waves. It is described below.
2. **Wave 1** is a broad TES add-on sweep (20, 40, 60, 80 and 100%) on the generation-share mandates (base, n15, n20, n25, n50), at the resolution wave 0 selects.
3. **Wave 2** is a fine sweep around each mandate's breakeven TES add-on cost.
4. **Wave 3** holds the sensitivities around the breakeven: a few capacity-mandate runs (`GSw_NuclearCapMandate`), new large nuclear allowed (`GSw_NuclearLarge=1`), and others to be chosen.

`z-ethan/make_paper_v6_casefiles.py` writes the wave 0 casefiles and pins every switch the paper fixes. The v6 pins differ from v5 in four ways:
- the default zone set, z90, instead of z54;
- OBBBA incentives with the statutory 45Y/48E phase-down (`incentives_suffix=obbba_phasedown`) instead of none;
- the Clean Air Act Section 111 rules off (`GSw_Clean_Air_Act=0`), with `GSw_CSAPR` at its default of 1;
- up to 5 stress-period iterations (`GSw_PRM_StressIterateMax=5`), because upstream now stops a run whose resource adequacy thresholds are still unmet after the last iteration.

### TES wrapper costing in all waves

All waves set `GSw_StorageHybrid_TESCostSplit=1`. The SMR keeps its own powerblock. Storage discharge adds BCR × the SMR powerblock cost (the turbine enlargement). The TES add-on is the storage-specific share (`GSw_StorageHybrid_TESStorShare=0.203`, from PNNL-33283 section 4.8.1) of the TES power capex and power FOM, plus the TES energy capex and energy FOM. `GSw_StorageHybrid_TESAddonMult` scales only the TES add-on. `plantchar_tes` stays at `tes_ATB_2024_moderate`.

### Wave 0 design

Wave 0 runs the n25 generation-share mandate (`GSw_interpolate_mandates=2035-0.1_2050-0.25`) at three dispatch timeslice lengths. Each resolution has a control (`_ctrl`, hybrids off) and the TES add-on at 20, 40 and 60% (`_ta20`, `_ta40`, `_ta60`; `GSw_StorageHybrid_TESAddonMult` = 0.2, 0.4, 0.6). `GSw_HourlyChunkLengthRep` and `GSw_HourlyChunkLengthStress` are equal in every case.

All 12 cases are in one casefile, `cases_nuclearstor_paper_v6_wave0.csv`, which NLR runs:
- `w0_h3_n25_*` (first 4): 3-hour timeslices, the current setting.
- `w0_h2_n25_*` (next 4): 2-hour timeslices.
- `w0_h1_n25_*` (last 4): 1-hour timeslices.

Interday linkage stays off, because TES wrappers can't use it. `pcm=0`, because the dispatch-mode rerun fails: `runreeds.py` calls `reeds/postprocessing/run_pcm.py`, but the script is at `postprocessing/run_pcm.py`.

### Run

```
python runreeds.py -b v6w0 -c nuclearstor_paper_v6_wave0
```

Memory per case, **estimated, not measured**. The z54, 3-hour core runs peaked at about 60 GB. z90 has about 1.7 times as many zones, and the 2-hour and 1-hour cases have 1.5 and 3 times as many timeslices:
- `w0_h3_*`: about 100 GB.
- `w0_h2_*`: about 150 GB.
- `w0_h1_*`: about 300 GB or more. Their solves will also take several times longer.

On HPC, `runreeds.py` asks for cases per node; use one case per node, on big-memory nodes for the 1-hour cases. A workstation with 253 GB can run 2 of the 3-hour cases at a time. If you rerun a subset with `-s`, check `inputs_case/switches.csv` in each run folder afterward.

If a run stops with "At least one resource adequacy metric failed to meet the required threshold(s) within 5 iterations", rerun that case with a higher `GSw_PRM_StressIterateMax`.

### Pass criteria

- All 12 cases solve to 2050, and every solve is optimal.
- The 2050 nuclear share of total generation is at least 0.23. The mandate's base is bus-bar load, so the share can sit up to about 2 points below the 0.25 target; the test is one-sided.
- No `_ctrl` case builds a wrapper. Hybrid cases build only `storage-hybrid-{1..5}-nuclear-smr`.
- No case builds new large nuclear: `Nuclear` capacity never rises after 2026.
- The check script below runs and writes `wave0_summary.csv`.

### Wave 0 check script

Run from the repo root in the `reeds` env. It reads each case's `outputs.h5`, either from a run folder under `runs/` or from the files NLR posts. Put the NLR files under `NLR_DIR`; each path must contain the case name (for example `wave0_nlr/v6w0_w0_h2_n25_ta20/outputs.h5` or `wave0_nlr/w0_h1_n25_ctrl.h5`).

```python
import re
from pathlib import Path
import pandas as pd
import reeds

BATCH = 'v6w0'
NLR_DIR = 'wave0_nlr'
TARGET = 0.25
BCR = {'1': 0.1, '2': 0.25, '3': 0.5, '4': 0.75, '5': 1.0}
CASE = re.compile(r'w0_(h[123])_(n25)_(ctrl|ta\d+)')
EXPECTED = {'h3': 4, 'h2': 4, 'h1': 4}

## Sources: local run folders and NLR outputs.h5 files
sources = {}
for d in sorted(Path('runs').glob(f'{BATCH}_w0_*')):
    m = CASE.search(d.name)
    if m:
        sources[m.group(0)] = d / 'outputs' / 'outputs.h5'
if Path(NLR_DIR).exists():
    for f in sorted(Path(NLR_DIR).rglob('*.h5')):
        m = CASE.search(str(f))
        if m:
            sources[m.group(0)] = f

def read(src, key, cols):
    df = reeds.io.read_output(str(src), key)
    df.columns = cols
    df['t'] = df['t'].astype(int)
    return df

def is_nuclear(i):
    i = str(i).lower()
    return i in ('nuclear', 'nuclear-smr') or i.startswith('storage-hybrid-')

rows = []
missing = [c for c, src in sources.items() if not Path(src).exists()]
for case, src in sources.items():
    if case in missing:
        continue
    res, mandate, arm = CASE.match(case).groups()
    cap = read(src, 'cap', ['i', 'r', 't', 'MW'])
    gen = read(src, 'gen_ann', ['i', 'r', 't', 'MWh'])
    wrap = cap[cap.i.str.lower().str.startswith('storage-hybrid-')]
    row = {'case': case, 'res': res, 'mandate': mandate, 'arm': arm, 'source': str(src)}
    ## Wrapper capacity in 2050 by BCR rung, and the first year any wrapper exists
    for typ, bcr in BCR.items():
        sel = wrap[(wrap.t == 2050) & wrap.i.str.lower().str.startswith(f'storage-hybrid-{typ}-')]
        row[f'wrap_GW_2050_bcr{bcr}'] = round(sel.MW.sum() / 1e3, 2)
    row['wrap_GW_2050'] = round(wrap[wrap.t == 2050].MW.sum() / 1e3, 2)
    row['wrap_first_year'] = int(wrap.t.min()) if len(wrap) else None
    row['nuc_GW_2050'] = round(cap[(cap.t == 2050) & cap.i.map(is_nuclear)].MW.sum() / 1e3, 1)
    ## New large nuclear is off, so Nuclear capacity never rises after 2026
    large = cap[(cap.i.str.lower() == 'nuclear') & (cap.t >= 2026)].groupby('t').MW.sum()
    row['large_nuc_GW_2050'] = round(large.get(2050, 0) / 1e3, 1)
    row['large_nuc_rise_GW'] = round(max(large.diff().max(), 0) / 1e3, 2) if len(large) > 1 else 0.0
    g50 = gen[gen.t == 2050]
    row['nuc_share_2050'] = round(g50[g50.i.map(is_nuclear)].MWh.sum() / g50.MWh.sum(), 3)
    ## Wrapper energy capacity in 2050
    en = read(src, 'cap_energy_ivrt', ['i', 'v', 'r', 't', 'MWh'])
    en = en[(en.t == 2050) & en.i.str.lower().str.startswith('storage-hybrid-')]
    row['wrap_GWh_2050'] = round(en.MWh.sum() / 1e3, 1)
    ## System cost (2004$), summed over solve years, undiscounted across years
    sc = read(src, 'systemcost_bulk', ['cost', 't', 'value'])
    row['systemcost_bulk_B$'] = round(sc.value.sum() / 1e9, 3)
    ## The mandate is a floor on a bus-bar-load basis, so the share of total
    ## generation may sit up to about 2 points below the target, or above it
    row['share_minus_target'] = round(row['nuc_share_2050'] - TARGET, 3)
    row['share_ok'] = row['share_minus_target'] >= -0.02
    rows.append(row)

df = pd.DataFrame(rows).set_index('case').sort_index()
df.to_csv('wave0_summary.csv')
print(df.drop(columns='source').to_string())
for res, n in EXPECTED.items():
    print(f'{res}: {int((df.res == res).sum())} of {n} cases found')
assert not missing, f'{len(missing)} cases have no outputs.h5: {missing}'
assert (df.loc[df.arm == 'ctrl', 'wrap_GW_2050'] == 0).all(), 'a control case built wrappers'
assert (df['large_nuc_rise_GW'] <= 0.01).all(), 'a case built new large nuclear'
assert df['share_ok'].all(), 'a case missed the n25 share by more than 2 points'
print('checks passed')
```

`cases_nuclearstor_paper_v5_wave0.csv` (48 cases, never run) is withdrawn; v6 replaces it. If NLR received it, NLR runs `cases_nuclearstor_paper_v6_wave0.csv` instead.

## Results

Run 2026-10-30 to 2026-11-04 on a 24-core, 253 GB machine. Step 2 first ran as batch `v5core` with `-r 6`. Only 5 of 18 cases finished: `capm_eo25_{base,ctrl}` and `ctrl_n{15,25,50}`. The other 13 were rerun as `v5core_r2` with `-r 3` and `-s`, and all of them finished. The final Step 2 results combine the two batches.

**The folder names of 4 `v5core_r2` cases are swapped.** `runs/v5core_r2_capm_cop28_{base,ctrl}` ran the `mckinsey` trajectory, and `runs/v5core_r2_capm_mck_{base,ctrl}` ran `cop28`. Check `GSw_NuclearCapMandateScen` in each case's `inputs_case/switches.csv`. Within each pair, this is the only switch that differs, so the runs are valid with their labels swapped. The cause is a bug in `runreeds.py`. With `-s`, `caseSwitches` and `caseList` stay in casefile order, but `casenames = single.split(',')` puts the folder names in the order given to `-s`. If the `-s` order differs from the casefile order, each folder gets another case's switches. The `-s` list for the rerun put cop28 before mck. Commit 97c8db39 fixed the bug.

| Step | Result | Notes |
|---|---|---|
| 1. `hybridtest` + CI case | Pass | `hybridtest`: all 7 cases finished to 2040 and every solve is optimal. The objective and capacity match the `p9c_*` runs exactly in the 5 cases that Phase 9c ran. `hyb_z54` matches `p9_hyb_z54` to about 3e-9 relative, and `base_z54` matches `p9_base_z54` exactly. No `hyb_*` case builds a wrapper, the same as at Phase 9c. `ntpci_github_StorageHybrid`: 5 optimal solves to 2030. It builds 55.0 GW of upv+battery wrappers (`storage-hybrid-3-upv_{1,2,3,5}`) in 6 regions, and its objective is identical to `p9d_ci_05`. `test_outputs` fails only on `figures/bars_retirements_additions.png`, the known local plotting failure. |
| 2.1 GAMS compile | Pass | All 18 cases compiled and solved at least 2010 to 2020. |
| 2.2 Load gate | Pass | All 18 cases printed `Load builds 1 and 2 agree` once. No case printed `disagree`. |
| 2.3 Optimal solves | Pass | All 18 cases solve to 2050, and every solve is optimal. No case was infeasible. The first batch at `-r 6` was short of memory. 6 cases hit Julia `OutOfMemoryError` in ReEDS2PRAS, 1 hit `CPLEX Error 1001: Out of memory` (`main_test_n20` 2047), and 6 were killed by a console Ctrl+C on 2026-11-01. The rerun at `-r 3` had no failures. **Use `-r 3` for this case set on a 253 GB machine.** |
| 2.4 Capacity floor | Pass | The minimum slack from 2032 to 2050 is 0.00 GW in all 8 `capm_*` cases, measured against each run's `inputs_case/nuclear_cap_trajectory.csv`. The floor binds in 7 of 7 solve years for mckinsey, cop28 and eo2025. For abou_jaoude it binds in 6 of 7 years, with 0.36 GW of slack in 2032. 2050 nuclear: atb 131, mck 197, cop28 297, eo25 397 GW. The `_base` and `_ctrl` cases match. `firstyear` is 2031 for `Nuclear` and `Nuclear-SMR` in all 18 `inputs.h5`. |
| 2.5 Energy mandate share | Pass | 2050 nuclear share of total generation: n15 0.150, n20 0.200, n25 0.250/0.251, n50 0.501, in both `main_test_*` and `ctrl_*`. Without a mandate, nuclear is 96.5 GW and 0.111 of generation. |
| 2.6 Hybrids only in test cases | Pass | No control case builds a wrapper. **No test case builds one either**: wrapper capacity is 0 GW in 2050 in all 9 cases with hybrids on. Each `main_test_*` and `capm_*_base` case matches its control in 2050 nuclear capacity and generation share. |
| 2.7 No demo plants | Pass | None of the 18 cases has demo-plant capacity. |
| 3a. Sweep smoke test `ts_mr20_n50` | Pass | Batch `ntpsmoke`, 12 optimal solves to 2050. At 20% TES cost the nuclear wrapper costs 3.44 M$/MW in 2035, less than plain nuclear at 3.55. At 100% it costs 4.47, which is why the core cases build none. From 2038 on, all new nuclear is built as nuclear-SMR+TES wrappers: 32.7 GW in 2038 and 337 GW of 433 GW total nuclear in 2050 (types 1/2/3: 253.7/11.4/71.8). Before 2038 the mandate is met by existing nuclear, so little new nuclear is built. 2050 nuclear share 0.501. PRAS ran with the wrapper GeneratorStorage units, and NEUE is 0 in 2050. Post-processing logs 6 tracebacks (`retail_rate_calculations.py`, `reeds_to_rev.py` on an NREL network path, `single_case_plots.py`). The core runs log the same 6, so they come from upstream and don't affect outputs. |
| 3b. Wave 0 (48 cases) | Not run | For NLR. It replaces the earlier 81-case OBBBA and sweep batches. |
