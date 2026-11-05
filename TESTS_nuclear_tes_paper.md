# Test checklist for the `nuclear-tes-paper` branch

This branch adds the nuclear+TES paper inputs to `storage-hybrid-pr`. The machine that wrote the branch has too little memory for ReEDS, GAMS or Julia runs. So no run on this branch has been done yet. A machine with enough memory runs the steps below and records each result in the table at the end.

## What the branch changes

The branch adds these commits on top of `storage-hybrid-pr` at `73cfa977`:

| Commit | Change |
|---|---|
| `d0e060a5` | `GSw_interpolate_mandates`: the national generation mandate follows a piecewise-linear trajectory, for example `2035-0.1_2050-0.15` |
| `a5611142` | `Nuke` column in `nat_gen_tech_frac.csv`: only `Nuclear` and `Nuclear-SMR` count toward the mandate |
| `8a148ad1` | `GSw_NuclearCapMandate`: a national floor on nuclear capacity (`eq_nuclear_cap_mandate`), with trajectories in `inputs/capacity_mandate/` |
| `1338ca45` | `tes_threshold_modrte_{pct}pct.csv`: TES cost sensitivity files at 10–200% of ATB 2024 moderate |
| `e2ee8679` | `hourly_load.py`: builds the load twice, compares the two builds, and validates the result before it writes `load.h5` |
| `923f48c5`, `401e1622` | The v5 casefiles: core (18 cases), core OBBBA sensitivity (18) and broad TES sweep (63) |
| (latest) | `GSw_NuclearFirstYear`: overrides the first year new nuclear can be built; the v5 casefiles set 2031 |

## Setup

1. Check out the branch: `git fetch origin && git checkout nuclear-tes-paper`.
2. Activate the conda env `reeds` (pandas 3). The env `reeds2` fails the version check.
3. Make sure Julia is set up and `Manifest.toml` exists at the repo root. The casefiles set `GSw_PRM_StressIterateMax=3`, so the runs need ReEDS2PRAS.

## Step 1: storage-hybrid regression test

```
python runreeds.py -b hybtest -c hybridtest -r 7
python runreeds.py -b ntpci -c test -s github_StorageHybrid -r 1
```

This step checks that the PR base still compiles and builds wrappers on this branch.

Pass criteria:
- All 7 `hybridtest` cases finish, and every solve is optimal.
- The `hybridtest` results match the Phase 9c runs for `storage-hybrid-pr` (`p9c_*`). This branch does not change any input those cases use, so a difference points to a bug in the port. Since Phase 9b, the `hyb_*` cases build no wrappers. That is expected, and it is not a failure.
- `github_StorageHybrid` (the CI case, `GSw_StorageHybrid_CostMult=0.5`) solves to 2030 and builds upv+battery wrappers: about 55 GW in 6 regions at Phase 9c. This is the case that checks wrapper builds. `pytest tests/test_outputs.py --casepath runs/ntpci_github_StorageHybrid` passes, except for the local plotting PNG.

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

## Step 3: the full batch

After Step 2 passes, run the OBBBA sensitivity and the sweep:

```
python runreeds.py -b v5obbba -c nuclearstor_paper_v5_core_obbba
python runreeds.py -b v5sweep -c nuclearstor_paper_v5_sweep
```

The OBBBA file uses upstream `incentives_obbba.csv` without changes. That file gives full credit to projects that start construction through 2032. It leaves out the statutory 2033–2035 phase-down. This is a known limitation, and the paper's Methods section states it.

## Results

| Step | Result | Notes |
|---|---|---|
Run 2026-10-30 to 2026-11-04 on a 24-core, 253 GB machine. Step 2 first ran as batch `v5core` with `-r 6`. Only 5 of 18 cases finished: `capm_eo25_{base,ctrl}` and `ctrl_n{15,25,50}`. The other 13 were rerun as `v5core_r2` with `-r 3` and `-s`, and all of them finished. The final Step 2 results combine the two batches.

**The folder names of 4 `v5core_r2` cases are swapped.** `runs/v5core_r2_capm_cop28_{base,ctrl}` ran the `mckinsey` trajectory, and `runs/v5core_r2_capm_mck_{base,ctrl}` ran `cop28`. Check `GSw_NuclearCapMandateScen` in each case's `inputs_case/switches.csv`. Within each pair, this is the only switch that differs, so the runs are valid with their labels swapped. The cause is a bug in `runreeds.py`. With `-s`, `caseSwitches` and `caseList` stay in casefile order, but `casenames = single.split(',')` puts the folder names in the order given to `-s`. If the `-s` order differs from the casefile order, each folder gets another case's switches. The `-s` list for the rerun put cop28 before mck. Until the bug is fixed, pass `-s` cases in casefile order.

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
| 3. OBBBA and sweep batches | Not run here | Left for NLR. Step 3 has 81 cases (18 OBBBA + 63 sweep). At `-r 3` and about 14 hours per case, that's about 16 days. No full-US case has built a nuclear+TES wrapper on this branch yet, so the first `ts_mr20_*` results are the first test of that path at scale. |
