"""
Generate the combined NREL nuclear-learning casefile
(cases_nuclearlearning_nrel.csv: "Default Value" column + 5 schedules x 16 cases
= 80 runs).

Layout (uses the ReEDS custom-casefile "Default Value" mechanism,
reeds/inputs.py parse_cases: empty cells in each case column are filled from
this file's Default Value column, then from cases.csv):

  Default Value   shared run config (seq / 2050 / equality capacity mandate /
                  capacity-credit RA + PRAS diagnostics) + the 8-type
                  storage-hybrid nuclear configuration + the LITERATURE-CENTER
                  learning world. Edit an axis here and every _lit and _oat
                  case moves with it.
  {s}_ctrl        learning OFF, mandate on — pure trajectory at ATB costs
  {s}_p05..p95    the notebook's per-schedule minimum spanning set
                  (mc_nuclear_smr_learning.ipynb item 10b,
                  reeds_cases_by_schedule.csv): actual joint draws at
                  P5/P25/P50/P75/P95 of the global PCA "expensiveness" axis,
                  conditional on the schedule — each an internally coherent
                  world (copula-consistent LR/BOAK/s/m/...). Written out in
                  full so each world is self-contained.
  {s}_lit         the literature-center world = the Default column (only the
                  trajectory scenario is set per block)
  {s}_lr_lo/hi    OAT: firm learning rate to its support ends (0.03 / 0.12-0.16)
  {s}_boak_lo/hi  OAT: BOAK anchor to its support ends (comonotone across techs)
  {s}_conv        OAT: convention -> full-stock (1)
  {s}_vend        OAT: vendors -> 8 (today's crowded market vs Abou-Jaoude's 4)
  {s}_ces         OAT: CES rho -> -2 (complements; the direction the
                  literature's multiplicative convention does NOT bracket)
  {s}_spill       OAT: spillover -> 0 (autarky bound; kills the foreign channel)
  {s}_lam         OAT: duration -> 1 (the INL moderate curve, conservative bound)

Literature-center choices (see the OAT writeup): LR 0.08/0.095 (Abou-Jaoude
firm-level), BOAK = ATB 2024 moderate anchor (switch 0), m = 4 (Abou-Jaoude),
convention tiny-base (Abou-Jaoude 2OAK), CES rho = 0 (multiplicative eq.-12
form), omega = 1/3 (Irwin & Klenow, held fixed). Axes with NO literature point
value use consistency centers: s = 0.5 (midpoint of the notebook's U(0,1)
prior; s = 0 would make the ces axis exactly inert via autarky flatness),
lambda = 0.5 (midpoint of the INL optimistic/moderate curves), ForeignScen =
mid (IAEA publishes a Low/High envelope only).

Resource adequacy: capacity-credit PRM (GSw_PRM_CapCredit=1, StressIterateMax=0)
with pras=1 for final-year adequacy diagnostics. reeds2pras storage-hybrid
support works as of the plantchar_tes wiring restoration (validated end-to-end
in the nlval2_eo_boak_lo run: 2050, 6 wrappers, PRAS finished cleanly); note it
models hybrids as lumped batteries (no generator/storage split), so PRAS results
value the hybrids conservatively. Set pras to 0 in the Default column to skip.

Rerun with:
  python inputs/nuclear_learning/_generate_sensitivity_casefile.py [--export-dir D:/z-ethan]
"""
import argparse
import os
import pandas as pd

SCHEDULES = {  # notebook schedule_axis name -> (case prefix, GSw_NuclearCapMandateScen)
    "EIA 2026 AEO high": ("eia", "eia_aeo_high"),
    "Abou-Jaoude": ("aj", "abou_jaoude"),
    "McKinsey GEP 2025": ("mck", "mckinsey"),
    "COP29 target": ("cop29", "cop29"),
    "2025 EO": ("eo", "eo2025"),
}
SPAN_CASES = {"low_P05": "p05", "P25": "p25", "central_P50": "p50",
              "P75": "p75", "high_P95": "p95"}
# OAT support ends (the notebook's sampling supports; LR/BOAK comonotone across techs)
LR_LO, LR_HI = (0.03, 0.03), (0.12, 0.16)            # (large, smr)
BOAK_LO, BOAK_HI = (5250.0, 5500.0), (7750.0, 10000.0)

# Shared run configuration for every case (via the Default Value column).
RUN_CONFIG = {
    "timetype": "seq",
    "endyear": "2050",
    "GSw_NuclearCapMandate": "2",            # equality: deployment pinned to the trajectory
    "GSw_NuclearCapMandate_Scale": "1",
    "pras": "1",                             # final-year PRAS adequacy diagnostics
    "GSw_PRM_StressIterateMax": "0",         # capacity-credit PRM, no stress iterations
    "GSw_PRM_CapCredit": "1",
    # 8-type storage-hybrid nuclear configuration: 4 SMR + 4 large-reactor
    # TES-molten-salt hybrids at BCR 0.25/0.5/0.75/1.0, no grid charging.
    "GSw_StorageHybrid": "1",
    "GSw_StorageHybrid_Types": "1_2_3_4_5_6_7_8",
    "GSw_StorageHybrid_GenTechs":
        "nuclear-smr_nuclear-smr_nuclear-smr_nuclear-smr_nuclear_nuclear_nuclear_nuclear",
    "GSw_StorageHybrid_StorageTechs":
        "tes-ms_tes-ms_tes-ms_tes-ms_tes-ms_tes-ms_tes-ms_tes-ms",
    "GSw_StorageHybrid_BCR": "0.25_0.5_0.75_1.0_0.25_0.5_0.75_1.0",
    "GSw_StorageHybrid_GridCharging": "0.0_0.0_0.0_0.0_0.0_0.0_0.0_0.0",
}

# Literature-center learning world (see module docstring). Lives in the Default
# Value column so the _lit and _oat cases inherit it.
LIT_CENTER = {
    "GSw_NuclearLearning": "1",
    "GSw_NuclearLearning_LR_large": "0.0800",    # Abou-Jaoude firm-level
    "GSw_NuclearLearning_LR_smr": "0.0950",      # Abou-Jaoude firm-level
    "GSw_NuclearLearning_BOAK_large": "0",       # 0 = ATB 2024 moderate anchor (5750 2022$/kW)
    "GSw_NuclearLearning_BOAK_smr": "0",         # 0 = ATB 2024 moderate anchor (8000 2022$/kW)
    "GSw_NuclearLearning_Vendors": "4",          # Abou-Jaoude's market split
    "GSw_NuclearLearning_Spillover": "0.5",      # consistency center (no literature value)
    "GSw_NuclearLearning_Convention": "0",       # tiny-base (Abou-Jaoude 2OAK)
    "GSw_NuclearLearning_CES_rho": "0",          # multiplicative eq.-12 form
    "GSw_NuclearLearning_Dur_Lambda": "0.5",     # consistency center (midpoint of INL curves)
    "GSw_NuclearLearning_ForeignScen": "mid",    # consistency center (IAEA envelope midpoint)
}


def foreign_scen(u):
    return "low" if u < 1.0 / 3.0 else ("mid" if u < 2.0 / 3.0 else "high")


def world_switches(row):
    """Map one notebook joint draw onto the GSw_NuclearLearning_* switches."""
    return {
        "GSw_NuclearLearning": "1",
        "GSw_NuclearLearning_LR_large": f"{row['lr_large']:.4f}",
        "GSw_NuclearLearning_LR_smr": f"{row['lr_smr']:.4f}",
        "GSw_NuclearLearning_BOAK_large": f"{row['boak_large']:.0f}",
        "GSw_NuclearLearning_BOAK_smr": f"{row['boak_smr']:.0f}",
        "GSw_NuclearLearning_Vendors": f"{int(row['n_vendors'])}",
        "GSw_NuclearLearning_Spillover": f"{row['s_spill']:.3f}",
        "GSw_NuclearLearning_Convention": "1" if row["convention"] == "full-stock" else "0",
        "GSw_NuclearLearning_CES_rho": f"{row['ces_rho']:g}",
        "GSw_NuclearLearning_Dur_Lambda": f"{row['dur_lambda']:.3f}",
        "GSw_NuclearLearning_ForeignScen": foreign_scen(float(row["u"])),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--export-dir", default=r"D:\z-ethan",
                   help="dir containing reeds_cases_by_schedule.csv (notebook exports)")
    args = p.parse_args()

    exp = pd.read_csv(os.path.join(args.export_dir, "reeds_cases_by_schedule.csv"))
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Default Value column must come first: parse_cases only default-fills the
    # case columns to its right.
    cols = {"Default Value": {**RUN_CONFIG, **LIT_CENTER}}
    for sched_name, (prefix, scen) in SCHEDULES.items():
        block = exp[exp["schedule_axis"] == sched_name].set_index("case")
        base = {"GSw_NuclearCapMandateScen": scen}
        # control: trajectory at ATB costs, no learning
        cols[f"{prefix}_ctrl"] = dict(base, GSw_NuclearLearning="0")
        # spanning set: written in full so each world is self-contained
        for nb_case, tag in SPAN_CASES.items():
            cols[f"{prefix}_{tag}"] = dict(base, **world_switches(block.loc[nb_case]))
        # literature center = the Default column; only the trajectory is set
        cols[f"{prefix}_lit"] = dict(base)

        def oat(tag, **overrides):
            cols[f"{prefix}_{tag}"] = {**base, **overrides}

        oat("lr_lo", GSw_NuclearLearning_LR_large=f"{LR_LO[0]:.4f}",
            GSw_NuclearLearning_LR_smr=f"{LR_LO[1]:.4f}")
        oat("lr_hi", GSw_NuclearLearning_LR_large=f"{LR_HI[0]:.4f}",
            GSw_NuclearLearning_LR_smr=f"{LR_HI[1]:.4f}")
        oat("boak_lo", GSw_NuclearLearning_BOAK_large=f"{BOAK_LO[0]:.0f}",
            GSw_NuclearLearning_BOAK_smr=f"{BOAK_LO[1]:.0f}")
        oat("boak_hi", GSw_NuclearLearning_BOAK_large=f"{BOAK_HI[0]:.0f}",
            GSw_NuclearLearning_BOAK_smr=f"{BOAK_HI[1]:.0f}")
        oat("conv", GSw_NuclearLearning_Convention="1")    # -> full-stock
        oat("vend", GSw_NuclearLearning_Vendors="8")       # -> today's crowded market
        oat("ces", GSw_NuclearLearning_CES_rho="-2")       # -> complements
        oat("spill", GSw_NuclearLearning_Spillover="0")    # -> autarky
        oat("lam", GSw_NuclearLearning_Dur_Lambda="1")     # -> INL moderate curve

    df = pd.DataFrame(cols)
    # stable row order: run config first, then mandate scenario, then learning
    order = [r for r in {**RUN_CONFIG, **LIT_CENTER} if r in df.index]
    order.insert(order.index("GSw_NuclearCapMandate") + 1, "GSw_NuclearCapMandateScen")
    order += [r for r in df.index if r not in order]
    df = df.loc[order]
    out = os.path.join(repo, "cases_nuclearlearning_nrel.csv")
    df.to_csv(out)
    ncases = df.shape[1] - 1
    print(f"wrote {out}: Default Value + {ncases} cases x {df.shape[0]} switch rows")
    assert ncases == 80, df.shape  # 5 blocks x (ctrl + 5 spanning + lit + 9 OAT)


if __name__ == "__main__":
    main()
