# Storage-Hybrid Technology

This page documents the `storage-hybrid` technology family in ReEDS. A storage-hybrid technology represents a paired generation and storage resource where the generation technology can be any configured ReEDS generation technology and the storage technology can be any configured storage technology that is valid for the storage-hybrid workflow. The `geo-storage` subset is a storage-side specialization for in-reservoir geothermal pressure storage, represented by the `flex_geo`, `flex_geo_high`, `flex_geo_med`, and `flex_geo_low` placeholder technologies.

Storage-hybrid was generalized from an earlier nuclear-plus-storage representation. The current implementation no longer assumes that the plant side is nuclear and no longer relies on static `Storage-HybridN` source technologies. Instead, preprocessing creates run-specific wrapper technologies for the storage-hybrid configurations requested by the case switches.

## Conceptual Model

Each storage-hybrid configuration is a generated technology in the run's `inputs_case` files. The model treats each generated wrapper as a hybrid plant with:

- A generation-side power capacity, represented by `CAP(i,v,r,t)`.
- A storage-side charge/discharge power capacity, represented as `bcr(i) * CAP(i,v,r,t)`.
- A storage energy capacity, represented by `CAP_ENERGY(i,v,r,t)`.
- Optional grid-charging power capacity, represented as `gridcharge_ratio(i) * CAP(i,v,r,t)`.

The storage-hybrid dispatch variables follow the existing hybrid-plant pattern:

| Variable | Meaning |
| --- | --- |
| `GEN_PLANT(i,v,r,h,t)` | Generation-side output before local charging is netted out. |
| `GEN_STORAGE(i,v,r,h,t)` | Storage discharge to the grid. |
| `STORAGE_IN_PLANT(i,v,r,h,t)` | Storage charging from the coupled generation technology. |
| `STORAGE_IN_GRID(i,v,r,h,t)` | Storage charging from the grid. |
| `GEN(i,v,r,h,t)` | Net hybrid output used by the model's generation accounting. |

The core net-output identity is:

```text
GEN = GEN_PLANT + GEN_STORAGE - STORAGE_IN_PLANT
```

Grid charging is not included in that identity. It is constrained separately by `gridcharge_ratio`, enters storage state-of-charge accounting, and is subtracted in reporting and tax-credit accounting where the model needs net generation after grid charging.

## User Switches

Storage-hybrid is configured through the case switches in `cases.csv`:

| Switch | Purpose | Example |
| --- | --- | --- |
| `GSw_StorageHybrid` | Turns storage-hybrid on (`1`) or off (`0`). | `1` |
| `GSw_StorageHybrid_Types` | `_`-delimited configuration IDs used to create run-specific wrapper names. | `1_2_3` |
| `GSw_StorageHybrid_GenTechs` | `_`-delimited generation technologies or approved numbered families to pair with storage. | `nuclear_nuclear-smr_egs-allkm` |
| `GSw_StorageHybrid_StorageTechs` | `_`-delimited storage technologies to pair with generation. | `tes-ms_tes-ms_battery-li_flex-geo-med` |
| `GSw_StorageHybrid_BCR` | `_`-delimited storage power capacity ratio relative to generation capacity. | `0.5_0.5_1.0` |
| `GSw_StorageHybrid_GridCharging` | `_`-delimited grid-charging power capacity ratio relative to generation capacity. | `0.0_0.5_1.0` |

The list-valued switches must either provide one value or the same number of values as `GSw_StorageHybrid_Types`. A single value is expanded to all active types. `GSw_StorageHybrid_Types` entries are configuration IDs, not source technology names.

`GSw_StorageHybrid_GenTechs` may name an explicit technology, such as `egs-allkm-1`, or one of the approved numbered families: `upv`, `wind-ofs`, `wind-ons`, `geohydro-allkm`, `egs-allkm`, and `egs-nearfield`. A family token expands to all matching numbered `i` technologies found in `inputs_case/sets/i.csv`. Other numbered-looking families are not expanded.

For example:

```csv
GSw_StorageHybrid,1
GSw_StorageHybrid_Types,1_2_3_4_5_6
GSw_StorageHybrid_GenTechs,nuclear_nuclear-smr_gas-cc_egs-allkm_upv-1_wind-ons-1
GSw_StorageHybrid_StorageTechs,tes-ms_tes-ms_battery-li_flex-geo-med_battery-li_battery-li
GSw_StorageHybrid_BCR,0.5_0.5_0.5_0.5_0.5_0.5
GSw_StorageHybrid_GridCharging,0.0_0.0_0.0_0.5_0.0_0.0
```

This example activates six configuration IDs. The fourth ID expands to every `egs_allkm_*` subtype, so preprocessing creates one generated wrapper per EGS subtype for that configuration.

| Config | Generation tech | Storage tech | BCR | Grid-charge ratio |
| --- | --- | --- | --- | --- |
| `storage-hybrid-1-nuclear` | `nuclear` | `tes_ms` | 0.5 | 0.0 |
| `storage-hybrid-2-nuclear-smr` | `nuclear-smr` | `tes_ms` | 0.5 | 0.0 |
| `storage-hybrid-3-gas-cc` | `gas-cc` | `battery_li` | 0.5 | 0.0 |
| `storage-hybrid-4-egs_allkm_1` ... `storage-hybrid-4-egs_allkm_10` | `egs_allkm_1` ... `egs_allkm_10` | `flex_geo_med` | 0.5 | 0.5 |
| `storage-hybrid-5-upv_1` | `upv_1` | `battery_li` | 0.5 | 0.0 |
| `storage-hybrid-6-wind-ons_1` | `wind-ons_1` | `battery_li` | 0.5 | 0.0 |

Hyphens and underscores in switch labels are canonicalized during preprocessing. For example, `battery-li` resolves to the `battery_li` technology and `flex-geo-med` resolves to `flex_geo_med` if those technologies exist in `inputs_case/sets/i.csv`. Use hyphenated labels in case switches because underscores delimit switch lists.

## Preprocessing

The storage-hybrid preprocessing happens in `input_processing/copy_files.py`.

### Generated Case Inputs

`write_miscellaneous_files()` reads the `GSw_StorageHybrid_*` switches, creates run-specific wrapper technologies, and writes storage-hybrid input files into `inputs_case`:

| Generated file | Loaded by | Meaning |
| --- | --- | --- |
| `storage_hybrid_config.csv` | `b_inputs.gms` | Lists generated wrapper technologies active in the run. |
| `storage_hybrid_bcr.csv` | `b_inputs.gms` | Maps each generated wrapper to its storage power capacity ratio. |
| `storage_hybrid_gridcharging.csv` | `b_inputs.gms` | Maps each generated wrapper to its grid-charging capacity ratio. |
| `storage_hybrid_storagetechs.csv` | `b_inputs.gms` | Maps each generated wrapper to its storage technology. |
| `storage_hybrid_gentechs.csv` | `b_inputs.gms` | Maps each generated wrapper to its generation technology. |
| `storage_hybrid_rsc_agg.csv` | `b_inputs.gms` | Maps each geothermal wrapper (second column) to its parent geo supply-curve technology (first column) so both share one resource supply curve and spur-line capacity. |

Preprocessing also appends generated wrappers to the run-specific `sets/i.csv` and `tech-subset-table.csv`. Repository source files list only real component technologies; generated storage-hybrid wrappers are not source technologies.

### Geothermal Supply Curves and Spur Lines

Geothermal wrappers (those whose generation technology belongs to the
`geohydro_allkm`, `egs_allkm`, or `egs_nearfield` supply-curve families) are marked
`RSC='YES'` in `tech-subset-table.csv` and mapped to their parent geo technology in
`storage_hybrid_rsc_agg.csv`. In `b_inputs.gms` this mapping is added to `rsc_agg`
(mirroring the UPV/PVB `tg_rsc_upvagg` construct), the parent's `rsc_dat` and
`m_rscfeas` are copied to the wrapper, and the wrapper joins `spur_techs` /
`spurline_sitemap` alongside its parent. As a result:

- The wrapper's investment is split into supply-curve bins (`INV_RSC`) and is bounded
  by the **same** `eq_rsc_INVlim` as its parent, so standalone geo plus geo-hybrid
  buildout cannot exceed the shared geothermal supply curve.
- The wrapper shares the parent's per-site spur-line capacity (`CAP_SPUR`) when the
  parent uses endogenous reV spur lines.
- Geohydro discovery scaling and exogenous supply-curve reductions remain applied only
  to the parent technology; because the binding limit is the parent-generated
  `eq_rsc_INVlim`, the wrapper inherits those effects through the shared constraint
  without being added to `geo(i)`, `geo_hydro(i)`, `exog_rsc`, or `prescriptivelink`.


### Technology Row Propagation

`propagate_storage_hybrid_tech_rows()` duplicates relevant input rows and columns from each configured generation technology to the corresponding generated wrapper technology. This lets storage-hybrid technologies inherit generation-side data that downstream model logic expects to find by technology name.

For example, if configuration ID `3` maps `gas-cc` to battery storage, preprocessing creates `storage-hybrid-3-gas-cc` and copies applicable `gas-cc` rows or columns to that generated wrapper in the case inputs. This is intentionally a generation-side propagation step. Storage-side parameters are inherited explicitly from `storage_hybrid_stortech(i,ii)` in GAMS.

The propagation code avoids files that should not be blindly copied, including selected capacity prescription files, demonstrations, some financial incentive files, `tech-subset-table.csv`, and files that already contain storage-hybrid-specific content.

## Sets and Activation

The core storage-hybrid sets are built in `b_inputs.gms`.

| Set or parameter | Purpose |
| --- | --- |
| `storage_hybrid(i)` | All active storage-hybrid technologies. |
| `storage_hybrid_config` | Generated wrapper technologies active in the run. |
| `storage_hybrid_gentech(i,ii)` | Generation technology used by storage-hybrid technology `i`. |
| `storage_hybrid_stortech(i,ii)` | Storage technology used by storage-hybrid technology `i`. |
| `storage_hybrid_active(i)` | Active configs inferred from nonempty `storage_hybrid_gentech(i,ii)`. |
| `storage_hybrid_with_tes(i)` | Storage-hybrid configs whose storage technology is in `thermal_storage`. |
| `geo_storage(i)` | Raw flex-geo storage placeholders and generated wrappers whose storage technology is in `geo-storage`. |
| `storage_hybrid_vre(i)` | Storage-hybrid configs whose generation technology is VRE. |
| `storage_hybrid_dispatchable(i)` | Storage-hybrid configs whose generation technology is not VRE. |

`storage_hybrid_vre(i)` and `storage_hybrid_dispatchable(i)` are important because they drive dispatch, reserve margin, and capacity-credit behavior. VRE-paired storage-hybrids behave like VRE hybrid plants with output availability derated by `m_cf`. Dispatchable-paired storage-hybrids use full nameplate capacity in the hybrid plant energy limit.

Storage-hybrid technologies also inherit technology-group membership through `tg_i(tg,i)` from their configured generation technology. This keeps downstream group-keyed logic, such as investment grouping and policy aggregation, aware of the hybrid configuration's generation-side identity.

Storage-hybrid configurations whose storage technology is in `geo-storage` also enter the `geo-storage` technology group. Raw `flex_geo`, `flex_geo_high`, `flex_geo_med`, and `flex_geo_low` technologies are banned from direct builds; they are only intended to act as storage-side components of storage-hybrid configurations.

## Cost and Performance Inheritance

Storage-hybrid cost and performance parameters are composed from the configured generation and storage technologies.

### Capacity Costs

`b_inputs.gms` first defines component costs:

```text
cost_cap_storage_hybrid_p = gen-tech capcost
cost_cap_storage_hybrid_s = storage-tech capcost
cost_cap_energy           = storage-tech capcost_energy
```

The final `cost_cap(i,t)` depends on whether the storage technology is thermal storage.

For non-thermal storage configurations:

```text
cost_cap = gen capex - shared powerblock capex + bcr * storage power capex
```

For thermal-storage configurations:

```text
cost_cap = gen capex - shared powerblock capex
         + (1 + bcr) * storage power capex
         + gridcharge_ratio * heater capex
```

The shared powerblock subtraction is controlled by `inputs/storage_hybrid_powerblock_share.csv`. It currently provides nonzero turbine-generator plus electrical equipment shares for `nuclear` and `nuclear-smr`. Generation technologies without an explicit row default to zero powerblock subtraction.

For geo-storage configurations, raw flex-geo storage placeholders have no inherent power-capacity cost. The storage-side power-capacity cost is instead represented by `bcr * powerblock_cost_storage_hybrid`, while energy-capacity cost remains separate through `cost_cap_energy(i,t)`.

Storage energy capacity cost remains separate through `cost_cap_energy(i,t)` and is applied to `INV_ENERGY(i,v,r,t)`.

### Fixed and Variable O&M

Generation-side VOM and FOM are inherited from `storage_hybrid_gentech(i,ii)`. Storage-side VOM, FOM, and energy-capacity FOM are inherited from `storage_hybrid_stortech(i,ii)`.

The power-capacity FOM composition is:

```text
cost_fom = gen-side FOM + bcr * storage-side FOM
```

The energy-capacity FOM is stored separately as `cost_fom_energy(i,v,r,t)` and is applied to `CAP_ENERGY` in the objective and reporting.

### Financial Multipliers

Storage-hybrid has separate financial multiplier parameters for the generation and storage portions:

| Parameter family | Meaning |
| --- | --- |
| `cost_cap_fin_mult_storage_hybrid_p*` | Generation-side capital cost multipliers. |
| `cost_cap_fin_mult_storage_hybrid_s*` | Storage-side capital cost multipliers. |

The generation-side multiplier is inherited from the configured generation technology. The storage-side multiplier starts from the configured storage technology, then adjusts financing risk so that the storage side carries the configured generation technology's financing risk. The storage side still keeps storage-specific items such as IDC and depreciation schedule.

The aggregate `cost_cap_fin_mult(i,r,t)` for `INV` is a cost-weighted average of the generation-side and storage-side multipliers. Energy investment, `INV_ENERGY`, uses the storage-side multiplier because `cost_cap_energy(i,t)` is purely a storage energy-capacity cost.

For raw `geo-storage` placeholders, the technology financial multipliers are kept neutral at `1`. For storage-hybrid configurations in `geo-storage`, the storage-side financial multiplier families are also kept at `1` because the storage-side costs come from storage-hybrid scaling rather than from standalone flex-geo financial assumptions.

### Operational Parameters

Several operating parameters are inherited from component technologies:

| Parameter | Inheritance rule |
| --- | --- |
| `ramprate(i)` | Configured generation technology. |
| `ramprate_storage_hybrid(i)` | Configured storage technology. |
| `cost_opres(i,ortype,t)` | Configured storage technology. |
| `outage_forced_h(i,r,h)` | Configured generation technology. |
| `outage_scheduled_h(i,h)` | Configured generation technology. |
| `storage_eff_storage_hybrid_g(i,t)` | Configured storage technology round-trip efficiency. |
| `storage_eff_storage_hybrid_p(i,t)` | Configured storage technology round-trip efficiency, except TES configs use `0.99` for local plant charging. |

The TES local-charge efficiency is set near one to avoid degeneracy between dispatching directly from the plant and charging thermal storage from the coupled plant.

## Dispatch and Constraints

Storage-hybrid dispatch uses the hybrid plant equations in `c_supplymodel.gms`.

### Plant Output Limit

`eq_hybrid_plant_energy_limit` limits generation-side output based on the generation technology type:

```text
m_cf * CAP >= GEN_PLANT          for VRE-paired storage-hybrids
CAP        >= GEN_PLANT          for dispatchable-paired storage-hybrids
```

This is the main equation-level split between `storage_hybrid_vre(i)` and `storage_hybrid_dispatchable(i)`.

### Local Charging Limit

`eq_hybrid_plant_storage_limit` requires local plant charging to be no larger than generation-side output:

```text
GEN_PLANT >= STORAGE_IN_PLANT
```

### Hybrid Plant Capacity Limit

`eq_plant_capacity_limit` limits total power moving through the hybrid plant interface. For storage-hybrid, the capacity side is:

```text
CAP * (1 + bcr)
```

and it must cover generation-side output, local charging, storage discharge, grid charging, and operating reserves.

### Storage Power Limit

`eq_hybrid_storage_capacity_limit` limits storage activity to storage-side power capacity:

```text
CAP * bcr >= GEN_STORAGE + STORAGE_IN_PLANT + STORAGE_IN_GRID
```

### Grid Charging Limit

`eq_cap_storage_in_grid` limits storage charging from the grid:

```text
CAP * gridcharge_ratio >= STORAGE_IN_GRID
```

A `gridcharge_ratio` of `0` disables grid charging for that configuration.

Geo-storage storage-hybrid configurations are constrained to charge only from the grid. `eq_storage_hybrid_geo_storage_grid_only` sets `STORAGE_IN_PLANT` to zero for storage-hybrid technologies in `geo_storage(i)`, while `eq_cap_storage_in_grid` still limits grid charging by `gridcharge_ratio`.

### Storage State of Charge

`eq_storage_level` tracks state of charge for storage-hybrid using the storage-hybrid local and grid charging efficiencies:

```text
SOC_next = SOC
         + storage_eff_storage_hybrid_p * STORAGE_IN_PLANT * hours_daily
         + storage_eff_storage_hybrid_g * STORAGE_IN_GRID  * hours_daily
         - GEN_STORAGE * hours_daily
         - reserve losses
```

`eq_storage_duration` limits `STORAGE_LEVEL` using `CAP_ENERGY` for battery, TES, and storage-hybrid technologies. New storage-hybrid builds also must satisfy the minimum energy duration constraint:

```text
CAP_ENERGY >= CAP * bcr * min_storage_hybrid_duration
```

The scalar `min_storage_hybrid_duration` is defined in `inputs/scalars.csv`.

### Minimum Generation

For dispatchable-paired storage-hybrid configurations, `eq_mingen_fixed` applies minimum generation to `GEN_PLANT` rather than net `GEN`. This prevents storage charging or discharge from masking the generation-side minimum output constraint.

## Capacity Credit and Reserve Margin

Storage-hybrid energy capacity participates in storage capacity-credit logic with battery and TES technologies through `CAP_ENERGY`.

The capacity credit treatment depends on the generation technology:

- `storage_hybrid_vre(i)` uses the hybrid capacity-credit derate factor, similar to PVB, because its output is tied to VRE availability.
- `storage_hybrid_dispatchable(i)` does not use the VRE-availability derate and contributes storage capacity through the storage capacity-credit bins.

This distinction appears in both `eq_sdbin_power_limit` and `eq_reserve_margin`.

## Objective Function and Reporting

The objective function separates plant-side and storage-side accounting.

Investment costs include:

- `INV * cost_cap * cost_cap_fin_mult` for the composed power capacity cost.
- `INV_ENERGY * cost_cap_energy * cost_cap_fin_mult_storage_hybrid_s` for storage energy capacity.

Operating costs include:

- Plant-side VOM on `GEN_PLANT` using generation-side `cost_vom`.
- Storage-side VOM on `GEN_STORAGE` using `cost_vom_storage_hybrid_s`.
- FOM on `CAP` using composed `cost_fom`.
- Energy-capacity FOM on `CAP_ENERGY` using `cost_fom_energy`.
- Fuel and emissions on `GEN_PLANT` for fuel-burning generation technologies.

Production tax credit accounting subtracts storage charging from the grid so that credits are not earned on energy imported from the grid and re-exported through storage.

## Outputs to Inspect

Storage-hybrid results appear in the same output files used for other generation and hybrid technologies. Useful files include:

| Output file | What to inspect |
| --- | --- |
| `cap_ivrt.csv` | Power capacity, `CAP`, by technology, vintage, region, and year. |
| `cap_energy_ivrt.csv` | Storage energy capacity, `CAP_ENERGY`, for battery, TES, and storage-hybrid technologies. |
| `gen_h.csv` | Net generation after model-level hybrid accounting. |
| `gen_plant_h.csv` | Generation-side output from hybrid plants. |
| `gen_storage_h.csv` | Storage discharge from hybrid plants. |
| `storage_in_plant_h.csv` | Charging from the coupled generation technology. Values are reported as negative. |
| `storage_in_grid_h.csv` | Charging from the grid. Values are reported as negative. |
| `systemcost_techba.csv` | Tech/BA-level cost accounting, including storage-hybrid plant and storage-side costs. |

For storage-hybrid dispatch plots, `gen_plant_h.csv`, `gen_storage_h.csv`, `storage_in_plant_h.csv`, and `storage_in_grid_h.csv` are usually the most direct files to use.

## Adding a New Storage-Hybrid Scenario

To configure a new storage-hybrid scenario:

1. Set `GSw_StorageHybrid` to `1`.
2. Choose one or more configuration IDs in `GSw_StorageHybrid_Types`. Valid IDs are `1` through `8`.
3. Set `GSw_StorageHybrid_GenTechs` to the generation technologies to pair with storage.
4. Set `GSw_StorageHybrid_StorageTechs` to the storage technologies to pair with those generation technologies.
5. Set `GSw_StorageHybrid_BCR` to the storage power-to-generation power ratio for each configuration.
6. Set `GSw_StorageHybrid_GridCharging` to the grid-charging power-to-generation power ratio for each configuration.
7. Confirm that all generation and storage technologies resolve to entries in `inputs/sets/i.csv` after case input copying.
8. Run the case and inspect the generated files in `runs/<case>/inputs_case/` to confirm the mappings are what you intended.

The preprocessing validation currently allows storage technology families whose labels begin with `battery`, `tes`, `caes`, or `flex`, but the exact technology label must still resolve to a valid `i` technology in the copied case inputs.

## Design Assumptions and Current Limitations

- Storage-hybrid configurations are generic slots, not separate named technologies for every possible generation-storage pair. The active slot-to-component mapping is controlled by case switches.
- The implementation generates run-specific storage-hybrid wrapper technologies from case switches.
- Each generated wrapper maps to exactly one generation technology and one storage technology.
- Approved family tokens in `GSw_StorageHybrid_GenTechs` can expand one configuration ID into several generated wrappers, one per numbered subtype.
- Generation-side attributes are partly propagated in preprocessing and partly inherited in GAMS through `storage_hybrid_gentech(i,ii)`.
- Storage-side attributes are inherited in GAMS through `storage_hybrid_stortech(i,ii)`.
- VRE-paired and dispatchable-paired storage-hybrids branch in several equations; new model logic that handles hybrid plants may need to decide whether it should apply to all storage-hybrids or only one branch.
- Thermal-storage configurations have special powerblock and efficiency treatment. Non-thermal-storage configurations use the simpler `gen + bcr * storage` power-capex composition.
- `gridcharge_ratio` limits the ability to charge from the grid. Local charging from the coupled plant is still bounded by plant output and storage power capacity, except for geo-storage configurations, where local plant charging is disabled.

## Key Implementation Files

| File | Role |
| --- | --- |
| `cases.csv` | Defines user-facing `GSw_StorageHybrid_*` switches. |
| `input_processing/copy_files.py` | Writes storage-hybrid mapping files and propagates generation-tech input rows. |
| `inputs/sets/storage_hybrid_config.csv` | Empty source placeholder; preprocessing overwrites the run-specific copy with generated wrappers. |
| `inputs/sets/i.csv` | Declares source component technologies such as `tes_ms` and flex-geo variants; generated storage-hybrid wrappers are added only in `inputs_case`. |
| `inputs/tech-subset-table.csv` | Places source technologies in subsets; generated storage-hybrid wrapper rows are added only in `inputs_case`. |
| `inputs/plant_characteristics/flex_geo_placeholder.csv` | Defines the costless `flex_geo`, `flex_geo_high`, `flex_geo_med`, and `flex_geo_low` placeholders used for geo-storage storage-hybrid configurations. |
| `inputs/storage_hybrid_powerblock_share.csv` | Defines powerblock cost shares for generation technologies that share a powerblock with storage discharge. |
| `b_inputs.gms` | Builds storage-hybrid sets, mappings, cost parameters, efficiencies, ramp rates, and operating parameters. |
| `d1_financials.gms` | Builds generation-side, storage-side, and aggregate financial multipliers. |
| `d1_temporal_params.gms` | Inherits storage-hybrid forced and scheduled outages from the configured generation technology. |
| `c_supplymodel.gms` | Defines dispatch, state-of-charge, grid charging, capacity credit, and reserve margin constraints. |
| `c_supplyobjective.gms` | Accounts for storage-hybrid investment, VOM, FOM, fuel, and tax credits in the objective. |
| `d3_data_dump.gms` | Dumps storage-hybrid energy capacity and investment for reporting/Augur inputs. |
| `e_report.gms` | Reports storage-hybrid generation, charging, storage discharge, and system costs. |
