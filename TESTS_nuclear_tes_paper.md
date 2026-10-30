# Test checklist for the `nuclear-tes-paper` branch

This branch adds the nuclear+TES paper inputs to `storage-hybrid-pr`. The machine that wrote the branch has too little memory for ReEDS, GAMS or Julia runs. So no run on this branch has been done yet. A machine with enough memory runs the steps below and records each result in the table at the end.

## What the branch changes

The branch adds 7 commits on top of `storage-hybrid-pr` at `73cfa977`:

| Commit | Change |
|---|---|
| `d0e060a5` | `GSw_interpolate_mandates`: the national generation mandate follows a piecewise-linear trajectory, for example `2035-0.1_2050-0.15` |
| `a5611142` | `Nuke` column in `nat_gen_tech_frac.csv`: only `Nuclear` and `Nuclear-SMR` count toward the mandate |
| `8a148ad1` | `GSw_NuclearCapMandate`: a national floor on nuclear capacity (`eq_nuclear_cap_mandate`), with trajectories in `inputs/capacity_mandate/` |
| `1338ca45` | `tes_threshold_modrte_{pct}pct.csv`: TES cost sensitivity files at 10–200% of ATB 2024 moderate |
| `e2ee8679` | `hourly_load.py`: builds the load twice, compares the two builds, and validates the result before it writes `load.h5` |
| `923f48c5`, `401e1622` | The v5 casefiles: core (18 cases), core OBBBA sensitivity (18) and broad TES sweep (63) |

## Setup

1. Check out the branch: `git fetch origin && git checkout nuclear-tes-paper`.
2. Activate the conda env `reeds` (pandas 3). The env `reeds2` fails the version check.
3. Make sure Julia is set up and `Manifest.toml` exists at the repo root. The casefiles set `GSw_PRM_StressIterateMax=3`, so the runs need ReEDS2PRAS.

## Step 1: storage-hybrid regression test

```
python runreeds.py -b hybtest -c hybridtest
```

This step checks that the PR base still compiles and builds wrappers on this branch.

Pass criteria:
- All 7 cases finish, and every solve is optimal.
- The `hyb_*` cases build at least one `storage-hybrid-*` wrapper.
- The results match the Phase 9c results for `storage-hybrid-pr`. This branch does not change any input those cases use, so a difference points to a bug in the port.

## Step 2: v5 core smoke test

```
python runreeds.py -b v5core -c nuclearstor_paper_v5_core
```

The core file has 18 cases:
- `main_test_{base,n15,n20,n25,n50}` and `ctrl_{base,n15,n20,n25,n50}`: no mandate, then energy mandates that rise to 15, 20, 25 and 50% of generation in 2050. `main_test_*` has hybrids on. `ctrl_*` has hybrids off.
- `capm_{atb,mck,cop28,eo25}_{base,ctrl}`: capacity mandates (floor mode). `_base` has hybrids on. `_ctrl` has hybrids off.

Each case solves 12 years: 2010, 2015, 2020, 2025, 2030, 2032, 2035, 2038, 2041, 2044, 2047 and 2050.

Pass criteria, in order:

1. **GAMS compile.** Each case gets past `b_inputs.gms` and `c_model.gms` without a compile error. The new code is the `$include` of `nuclear_cap_trajectory`, the set `nuclear_storage_hybrid(i)`, and the equations `eq_nuclear_cap_mandate` and `eq_nuclear_cap_mandate_ub`.
2. **Load gate.** Each case's log prints `Load builds 1 and 2 agree` (or a later pair of builds). If a case prints `WARNING: load builds ... disagree` 12 times and stops, the load build is not deterministic on that machine. Record the case name and the message.
3. **Optimal solves.** Every solve year in every case is optimal.
4. **Capacity floor.** In each `capm_*` case, total nuclear capacity is at or above the trajectory in each solve year from 2035 to 2050. Total nuclear capacity counts `nuclear`, `nuclear-smr` and the `storage-hybrid-*-nuclear*` wrappers. The mandate starts in 2035 because new nuclear can be built from 2034 (`this_year` 2026 + 8 years in `years_until_endogenous.csv`). In the `_ctrl` cases the floor should bind in most years after 2035.
5. **Energy mandate.** In `n15`, `n20`, `n25` and `n50`, the 2050 nuclear share of generation is close to 15, 20, 25 and 50%. The mandate's base is bus-bar load, not total generation. So the share of total generation can sit up to about 1–2 percentage points below the target.
6. **Hybrids only in the test cases.** The `ctrl_*` and `capm_*_ctrl` cases build no `storage-hybrid-*` capacity. The test cases may or may not build wrappers: the paper studies exactly that. Record the 2050 wrapper capacity in each test case.
7. **No demo plants.** No case builds the prescribed nuclear demonstration plants (`GSw_NuclearDemo=0`).

### Feasibility risk to watch

New nuclear can be built from 2034, and 2035 is the first solve year that the mandate applies to. The two steepest trajectories therefore need a large build in the 2032→2035 step:

| Trajectory | 2035 floor (GW) | Build needed above about 97 GW existing |
|---|---|---|
| `abou_jaoude` (atb) | 100 | about 3 |
| `mckinsey` (mck) | 114.5 | about 18 |
| `cop28` | 132 | about 35 |
| `eo2025` (eo25) | 147 | about 50 |

If `capm_eo25_*` or `capm_cop28_*` is infeasible in 2035, record it and stop. Do not change the trajectories. The fix is a modeling decision for Ethan.

### Check script

Run this script after the core batch finishes, from the repo root in the `reeds` env. Edit `BATCH` if you used another batch name.

```python
import os
import pandas as pd
import reeds

BATCH = 'v5core'
TARGET = {'n15': 0.15, 'n20': 0.20, 'n25': 0.25, 'n50': 0.50}
TRAJ = {'atb': 'abou_jaoude', 'mck': 'mckinsey', 'cop28': 'cop28', 'eo25': 'eo2025'}

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
    cap = reeds.io.read_output(path, 'cap_out')
    cap.columns = ['i', 'r', 't', 'MW']
    gen = reeds.io.read_output(path, 'gen_ann')
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
    tag = name.split('_')[1] if name.startswith('capm_') else None
    if tag in TRAJ:
        traj = pd.read_csv(
            f'inputs/capacity_mandate/nuclear_cap_trajectory_{TRAJ[tag]}.csv', index_col=0
        ).squeeze(1) / 1e3
        years = [t for t in nuc_cap.index if int(t) >= 2035]
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
| 1. `hybridtest` | | |
| 2.1 GAMS compile | | |
| 2.2 Load gate | | |
| 2.3 Optimal solves | | |
| 2.4 Capacity floor | | |
| 2.5 Energy mandate share | | |
| 2.6 Hybrids only in test cases | | |
| 2.7 No demo plants | | |
| 3. OBBBA and sweep batches | | |
