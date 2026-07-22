"""
Generate the national nuclear capacity mandate trajectories used by
GSw_NuclearCapMandate (eq_nuclear_cap_mandate in c_supplymodel.gms).

The six trajectories are the US deployment schedules of
`mc_nuclear_smr_learning.ipynb` (cell 3, US_SCHEDULES), transcribed verbatim.
The schedule values are read as literal GW targets (e.g. the 2025 EO is
literally 400 GW by 2050; COP29 tripling ~300 GW): the base-year "100" is the
actual 97 GW 2024 fleet rounded up, so a flat -3 GW offset undoes that
rounding rather than rescaling the stated targets multiplicatively.
Output files are in MW of total national nuclear capacity (existing + new,
net-path basis) with a GAMS-comment header, since b_inputs.gms $includes them
directly into nuclear_cap_trajectory(allt).

Rerun with:  python inputs/nuclear_learning/_generate_cap_trajectories.py
"""
import os

OFFSET_GW = 3.0   # schedule base year lists 100 for the actual 97 GW 2024 fleet
YEARS = list(range(2024, 2051))

# mc_nuclear_smr_learning.ipynb US_SCHEDULES (GW; base-year 100 = rounded 97 GW)
SCHEDULES = {
    "iaea_high": [100,100,100,100,100,100,100,103.4,106.8,110.2,113.6,117,120.4,123.8,127.2,
                  130.6,134,137.83,141.66,145.49,149.32,153.15,156.98,160.81,164.64,168.47,172.3],
    "cop29": [100,100,100,100,100,100,100,107,114,121,128,135,138,141,144,147,150,165,180,195,
              210,225,240,255,270,285,300],
    "eo2025": [100,100,100,100,100,100,100,110,120,130,140,150,160,170,180,190,200,220,240,260,
               280,300,320,340,360,380,400],
    "eia_aeo_high": [100,100,100,100,100,100,100,100,100,100,100,100,103.3,106.6,109.9,113.2,
                     116.5,116.58,116.66,116.74,116.82,116.9,116.98,117.06,117.14,117.22,117.3],
    "abou_jaoude": [100,100,100,100.25,100.5,100.75,101,101.4,101.8,102.2,102.6,103,104.1,105.2,
                    106.3,107.4,108.5,110.2,111.9,113.6,115.3,117,120.4,123.8,127.2,130.6,134],
    "mckinsey": [100,100,100,100,100,100,100,103.5,107,110.5,114,117.5,121,124.5,128,131.5,135,
                 141.5,148,154.5,161,167.5,174,180.5,187,193.5,200],
}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    for scen, idx in SCHEDULES.items():
        assert len(idx) == len(YEARS), (scen, len(idx))
        lines = ["*t,MW"]
        for y, v in zip(YEARS, idx):
            lines.append(f"{y},{round((v - OFFSET_GW) * 1000.0, 1)}")
        path = os.path.join(here, f"nuclear_cap_trajectory_{scen}.csv")
        with open(path, "w", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print(f"wrote nuclear_cap_trajectory_{scen}.csv "
              f"(2050 = {idx[-1] - OFFSET_GW:.1f} GW national)")


if __name__ == "__main__":
    main()
