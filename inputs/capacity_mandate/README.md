## Nuclear Capacity Mandate Input Files

These files define the national nuclear capacity trajectories used by `GSw_NuclearCapMandate`.
`GSw_NuclearCapMandateScen` selects one trajectory, and `runfiles.csv` copies it to `inputs_case/nuclear_cap_trajectory.csv`.
`b_inputs.gms` reads it into `nuclear_cap_trajectory(allt)`, and `eq_nuclear_cap_mandate` in `c_model.gms` enforces it.

- `nuclear_cap_trajectory_{scen}.csv`: Total national nuclear capacity in MW, existing plus new, for each year from 2024 to 2050.
  - The mandate counts all vintages of `nuclear(i)` and the gen-side capacity of nuclear storage-hybrid wrappers.
  - With `GSw_NuclearCapMandate=1` the trajectory is a floor. With `GSw_NuclearCapMandate=2` capacity must also stay at or below it.
  - `GSw_NuclearCapMandate_Scale` multiplies the trajectory for sub-national runs.
- `_generate_cap_trajectories.py`: Writes the trajectory files from the schedules listed in the script.
  - Each schedule is an index in which 100 is the 2024 US fleet (97 GW, rounded to 100).
  - The script reads the index as literal GW and subtracts a flat 3 GW to undo that rounding.

2050 national totals by scenario:

| Scenario | 2050 total (GW) | Source |
|---|---|---|
| `eia_aeo_high` | 114.3 | EIA AEO, high nuclear case |
| `abou_jaoude` | 131 | ATB Moderate (Abou-Jaoude et al.) |
| `iaea_high` | 169.3 | IAEA high case |
| `mckinsey` | 197 | McKinsey |
| `cop28` | 297 | COP28 pledge to triple nuclear capacity |
| `eo2025` | 397 | 2025 Executive Order target of 400 GW |
