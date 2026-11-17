# Storage-hybrid technologies: generator + storage behind one interconnection

## Summary
This PR adds storage-hybrid technologies: one generation technology (the gen tech) paired with one storage technology behind a shared point of interconnection. Examples:
- nuclear or SMR + molten-salt thermal energy storage (TES)
- gas-cc + battery
- upv or wind + battery
- geothermal + in-reservoir pressure storage

Case switches define the pairings. For each pairing, preprocessing creates a run-specific *wrapper* technology. The wrapper takes its generation-side data from the gen tech and its storage-side data from the storage tech, and it reuses the hybrid-plant (PV+battery) dispatch equations.

The feature is off by default (`GSw_StorageHybrid=0`). With it off, a Utah test case gives results identical to `main` (see [Verification](#verification)).

Full documentation: `docs/source/storage_hybrid.md`.

## Breaking change: tech-subset rename
The tech-subset column `STORAGE_HYBRID` (PV+battery and CSP) is renamed `HYBRID_PLANT`, and the GAMS set `storage_hybrid(i)` becomes `hybrid_plant(i)`. The name `STORAGE_HYBRID`/`storage_hybrid(i)` now means the new wrappers.
- The new name matches the existing `GSw_HybridPlant` switch and the `cost_vom_hybrid_plant` naming.
- Every in-repo consumer is updated: GAMS, `prep_data.py`, `i_subtech.csv`, `tech-subset-table.csv` and `tests/objective_function_params.yaml`.
- **External tools that read the `STORAGE_HYBRID` column, such as R2X, need the same rename.**

## New switches
| Switch | Default | Meaning |
| --- | --- | --- |
| `GSw_StorageHybrid` | 0 | turn wrappers on |
| `GSw_StorageHybrid_Types` | `1_2_3_4_5_6` | configuration IDs |
| `GSw_StorageHybrid_GenTechs` | nuclear/SMR | gen techs, or families (`upv`, `wind-ons`, `wind-ofs`, `geohydro-allkm`, `egs-allkm`, `egs-nearfield`) that expand to their classes |
| `GSw_StorageHybrid_StorageTechs` | `tes-ms` ×6 | storage techs |
| `GSw_StorageHybrid_BCR` | `0.25`–`0.75` | storage power per MW of generation |
| `GSw_StorageHybrid_GridCharging` | `0.0` | grid-charging power per MW of generation |
| `GSw_StorageHybrid_CostMult` | 1 | **testing only**: scales wrapper capital cost so that the CI case builds wrappers |
| `plantchar_tes`, `plantchar_flex_geo`, `heaterscen` | | TES, geothermal-storage placeholder and heater inputs |

`reeds/checks.py` `check_storage_hybrid` validates the switches before a run starts. Among other rules, it requires `GSw_HybridPlant` 2 or 3, and it rejects gen techs that burn coal, biomass or hydrogen or that capture CO2. The model's rules for those fuels and for capture have no wrapper terms yet.

## What the PR adds
- **Preprocessing** (`copy_files.py`):
  - wrapper configurations and the generated mapping files;
  - wrapper entries in `i` (`inputs.h5`), the tech-subset table and `ivt`;
  - an explicit row-cloning registry (`STORAGE_HYBRID_ROW_CLONES`) that gives wrappers rows in per-tech inputs by gen-first, gen-only or storage-first precedence. New rows are appended as text, so existing lines stay unchanged.
- **Costs** (`b_inputs.gms`, `2_financials.gms`, `plantcostprep.py`):
  - composed power and energy capital cost; TES wrappers share the gen tech's powerblock;
  - separate generation-side and storage-side financial multipliers;
  - vintage-averaged heat rate, VOM and FOM;
  - battery refurbishment over the wrapper's full life.
- **Operations** (`c_model.gms`, `d_objective.gms`):
  - plant output, plant-charging, storage-power and grid-charging limits;
  - storage state of charge with TES plant-charging efficiency 0.999;
  - minimum duration by storage class.
- **Interconnection:** wrappers pay POI and spur capacity for plant output plus storage discharge (`CAP/ILR + BCR × CAP`), so the shared interconnection gives no free capacity.
- **Fuel and policy:**
  - gas wrappers enter the gas supply curve, the seasonal gas price and the Clean Air Act 111 cap on `GEN_PLANT`;
  - the PTC and RECs count `GEN_PLANT`;
  - RPS/CES categories and REC-import bans are inherited;
  - battery wrappers count toward battery mandates and wind-ofs wrappers toward offshore-wind mandates;
  - CSAPR NOx is counted on `GEN_PLANT`.
- **VRE wrappers:** gen-tech capacity factors by resource class, a shared supply curve (`storage_hybrid_rsc_agg`) and shared spur lines.
- **Resource adequacy:**
  - capacity credit for the generation side, using the gen tech's outage rates, and for the storage side, using storage-duration bins;
  - PRAS `GeneratorStorage` units split by the gen tech's unit size, with the gen tech's outage rates and the VRE inflow profile.
- **Reporting:** `gen_plant_h`, `gen_storage_h`, `storage_in_plant_h`, `storage_in_grid_h`, energy capacity and duration, gas burn and system cost.
- **Inputs:**
  - `tes_ATB_2024_*` (ATB 2024);
  - `flex_geo_placeholder`;
  - `heater_sams_2020`;
  - `storage_hybrid_powerblock_share` (ATB 2024 GN-COA codes 23 and 24);
  - per-folder README entries.

## Changes to existing behavior
These run even with `GSw_StorageHybrid=0`. Each is listed with its reason; the docs page has the detail.
1. **New techs `tes_ms` and `flex_geo*`.** They are storage-side data sources for wrappers and are `bannew` in every run. The new technology groups `tes` and `geo-storage` each add one queue-overflow slack column per region and solve; no tech uses those groups in a base run.
2. **PV+battery formulation (only with `GSw_PVB=1`).** The hybrid-plant equations were generalized:
   - Plant charging no longer depends on `dayhours`. Solar output is already zero at night, so the restriction was redundant.
   - `GEN_PLANT` now includes the energy sent to storage. A new `eq_hybrid_plant_storage_limit` caps plant charging at `GEN_PLANT`, and `eq_plant_capacity_limit` subtracts plant charging, because that flow never reaches the grid side of the inverter.
   - A new `eq_hybrid_storage_capacity_limit` caps total storage activity at `BCR × CAP`.
   - REC and PTC accounting subtract PVB grid charging as drawn from the grid, without the `storage_eff_pvb_g` factor. Before, the credit was netted by the energy stored, not the energy drawn.
   - PVB reporting (VOM split, `gen_h`, `stor_inout`/`stor_out`, losses, charging cost) now reports storage throughput.
3. **Energy capacity of batteries, TES and hybrid plants.**
   - Retirable tuples get `eq_cap_energy_new_retub`/`retmo` and an energy retirement penalty, so energy capacity retires with power capacity. Before, energy capacity outlived retired power capacity and kept paying FOM. This affects batteries under `GSw_Retire=4`.
   - `eq_cap_energy_new_noret`, the duration bins and `eq_battery_minduration` cover TES and wrappers.
4. **Prescribed energy capacity.** `eq_forceprescription_energy` gives energy slack to tuples with a power prescription but no energy prescription. Without the slack, the equality forces zero energy capacity while the minimum-duration rule requires a positive amount.
5. **Removed `eq_storage_thermalres`.** Upstream's `THERMAL_STORAGE` subset is empty, so the equation never generated a row.
6. **Reporting.** `stor_energy_cap`/`cap_energy_ivrt` report `CAP_ENERGY` for techs with endogenous energy capacity. LCOE includes energy capital and energy FOM. Energy FOM is no longer multiplied by ILR.

## Upstream bug fixes included
These are independent of wrappers and could be split out on request.
- `reeds2pras` `make_pras_interfaces` raised `BoundsError` with no transmission lines, so every single-region run failed. It now returns empty Lines and Interfaces.
- `report_calcs.py` raised `KeyError` on an empty `FLOW` (single-region runs).
- `writecapdat.py` matched vintage rows by substring, so a configured wrapper on upv or wind doubled that tech's prescribed builds.
- `reeds2pras` `process_storages` looks up energy capacity by key instead of by position.

## Tests
- `tests/test_storage_hybrid.py`: 46 unit tests (configuration parsing, family expansion, the `ivt` append, the cloning registry, validation and outage inheritance). CI runs it.
- New CI scenario `github_StorageHybrid` (`github_Pacific` + nuclear+TES, gas-cc+battery with grid charging, upv+battery, `GSw_StorageHybrid_CostMult=0.5`). A CI step fails if the run builds no wrapper capacity.
- `tests/objective_function_params.yaml`: `check_inputs` now checks the wrapper cost parameters, BCR and heat rate.

## Verification
Runs were on Windows with the `reeds` environment. The Utah cases use `GSw_gopt=2`, because CPLEX barrier with `barcolnz 30` reports the Utah 2030 LP infeasible; `main` fails the same way.
- **Base equivalence (Utah, z54 zones, to 2040, against `main` 6c175c4f):**
  - `systemcost`, `cap` and `gen_ann` are identical in every year;
  - LP equations are identical;
  - the LP has +2 variables per solve, the two queue-overflow slacks in item 1 above;
  - `tes_ms`/`flex_geo` leave no trace in the LP.
- **Utah hybrid cases** (`hyb_ut`, `hyb_cc_ut`, `hyb_vre_ut`): each solves every year.
  - No wrapper is economic in Utah at default costs, so each result equals the base case to 1e-16.
  - With validation, `GSw_HybridPlant=0` and mismatched list lengths stop the run before setup.
  - `GSw_Nuclear=0` bans the nuclear wrappers.
- **Wrapper builds:** sandbox runs cut wrapper capital in the run-local GAMS copy only, so their build mix is not economic evidence. They built SMR+TES, gas-cc+battery, upv+battery and EGS wrappers. In them:
  - `error_check` z is within 4e-04;
  - every wrapper cost category matches the objective;
  - gas wrappers run at the 0.40 Clean Air Act cap, with their gas burn in `repgasquant`;
  - VRE wrappers stay within `m_cf × CAP` and within the shared supply-curve bins;
  - PRAS splits gas-wrapper fleets into units (for example 26 units for 6.3 GW).
  - Representative dispatch is plausible:
    - SMR+TES: plant capacity factor 0.89, 165 cycles/yr;
    - gas+battery: charges from the grid when grid energy is cheaper than fuel;
    - upv+battery: 17–36% grid charging;
    - no hour charges and discharges at once.
- **PRAS test system:** wrappers never gain adequacy over separate generators plus batteries. The storage shares the unit's outage, which adds about 6% EUE for gas+battery compared with independent batteries.
- **z54 to 2040** (`hyb_z54` with stress periods, `hyb_cc_z54` with capacity credit): both solve every year and build no wrappers at default costs.
- **CI case:** builds 55 GW of upv+battery wrappers by 2030 at `CostMult=0.5`. z is 7e-06, PRAS gets the wrapper units, and `test_outputs` passes except for a local Windows plotting crash that `main` also has.

## Known limitations
See the Limitations section of `docs/source/storage_hybrid.md`. In short:
- **Rejected gen techs:** coal, biomass, BECCS, gas-CCS and hydrogen.
- **Rules that use net output:** a few rules count net `GEN` for wrappers, each off by default or with a small effect.
- **Water:** water accounting does not cover wrappers.
- **VRE wrappers:** they add no reserve requirement.
- **Untested combination:** no CI or Utah case covers gas+battery or nuclear+TES builds at default costs, because neither is economic there.

## Review guide
- Start with `docs/source/storage_hybrid.md`.
- The GAMS changes are mostly guarded by wrapper sets that are empty when the feature is off; "Changes to existing behavior" above lists the unguarded ones.
- The input CSVs are row appends only, except `tech-subset-table.csv`, which gains three columns.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
