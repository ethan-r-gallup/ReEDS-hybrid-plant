"""Build the v5 nuclear+TES paper casefiles for the nuclear-tes-paper branch.

The paper runs in waves. Every wave uses the same wrapper set: nuclear-SMR
with molten-salt TES at BCR 0.1, 0.25, 0.5, 0.75 and 1.0. New large nuclear
is off (GSw_NuclearLarge=0), so SMR is the only new reactor; existing large
nuclear remains.
- TES wrappers use the split costing (GSw_StorageHybrid_TESCostSplit=1): the
  SMR keeps its powerblock, discharge adds BCR x the SMR powerblock, and the
  sweep scales only the TES add-on (storage-specific power share and energy)
  through GSw_StorageHybrid_TESAddonMult.
- Wave 0 fixes the time resolution for all later waves. It runs two energy
  mandates (n15, n50) and two capacity mandates (atb, eo25) at 3-hour and
  1-hour dispatch timeslices, with the TES add-on at 20/40/60/80/100% of ATB
  2024 moderate, and a control (hybrids off) for each mandate and resolution.
- Wave 1 is the broad TES cost sweep (20-100%) for all nine mandate levels at
  the resolution wave 0 selects. Wave 0 already covers its n15, n50, atb and
  eo25 cases.
- Wave 2 is a fine sweep around each mandate's breakeven TES cost.
- Wave 3 holds the sensitivities (including OBBBA) around the breakeven.

Writes cases_nuclearstor_paper_v5_wave0.csv at the repo root (48 cases; the
3-hour cases come first, so they finish first).
cases_nuclearstor_paper_v5_core.csv is the record of the first test batch
(6-type ladder) and is no longer generated here.

Every switch the paper fixes is pinned in the Default Value column (PINS);
each case sets only the switches that define it. Descriptions come from this
branch's cases.csv. Run from the repo root:
    python z-ethan/make_paper_v5_casefiles.py
"""
import csv

# BCR ladder: one nuclear-SMR+TES wrapper type per rung
BCR_LADDER = ['0.1', '0.25', '0.5', '0.75', '1.0']

# Switches fixed for the whole paper batch (Default Value column)
PINS = {
    'ignore': '0',
    'GSw_ZoneSet': 'z54',
    'timetype': 'seq',
    'yearset': '2010..2030..5_2032..2050..3',
    'plantchar_tes': 'tes_ATB_2024_moderate',
    'plantchar_nuclear_smr': 'nuclear-smr_ATB_2024_moderate',
    'plantchar_battery': 'battery_ATB_2024_moderate',
    'GSw_Nuclear': '1',
    'GSw_NuclearLarge': '0',
    'GSw_NuclearDemo': '0',
    'GSw_NuclearFirstYear': '2031',
    'GSw_NukeStateBan': '1',
    'GSw_StorageHybrid': '1',
    'GSw_StorageHybrid_Types': '_'.join(str(n) for n in range(1, len(BCR_LADDER) + 1)),
    'GSw_StorageHybrid_StorageTechs': '_'.join(['tes-ms'] * len(BCR_LADDER)),
    'GSw_StorageHybrid_GenTechs': '_'.join(['nuclear-smr'] * len(BCR_LADDER)),
    'GSw_StorageHybrid_BCR': '_'.join(BCR_LADDER),
    'GSw_StorageHybrid_GridCharging': '_'.join(['0.0'] * len(BCR_LADDER)),
    'GSw_StorageHybrid_TESCostSplit': '1',
    'GSw_StorageHybrid_TESStorShare': '0.203',
    'GSw_StorageHybrid_TESAddonMult': '1',
    'GSw_GenMandate': '1',
    'GSw_GenMandateList': 'Nuke',
    'GSw_interpolate_mandates': '0',
    'GSw_NuclearCapMandate': '0',
    'GSw_NuclearCapMandateScen': 'abou_jaoude',
    'GSw_StateRPS': '1',
    'incentives_suffix': 'none',
    'GSw_TCPhaseout': '1',
    'GSw_AnnualCap': '0',
    'GSw_AnnualCapScen': 'default',
    'GSw_LoadProfiles': 'EER2025_IRAlow',
    'ngscen': 'AEO_2026_baseline',
    'coalscen': 'AEO_2026_baseline',
    'uraniumscen': 'AEO_2026_baseline',
    'demandscen': 'AEO_2026_baseline',
    'GSw_InterDayLinkage': '0',
    'GSw_HourlyChunkLengthRep': '3',
    'GSw_HourlyChunkLengthStress': '3',
    'GSw_NewValCapShrink': '1',
    'GSw_PRM_StressIterateMax': '3',
    'reg_cap_cost_diff_suffix': 'default',
    'GSw_TransInvMaxLongTerm': '0',
    'pcm': '0',
}

# Time resolution: tag -> switches (representative and stress-period timeslice length)
RESOLUTION = {
    'h3': {},
    'h1': {
        'GSw_HourlyChunkLengthRep': '1',
        'GSw_HourlyChunkLengthStress': '1',
    },
}

# Energy (generation-share) mandates: tag -> GSw_interpolate_mandates
ENERGY = {
    'base': None,
    'n15': '2035-0.1_2050-0.15',
    'n20': '2035-0.1_2050-0.2',
    'n25': '2035-0.1_2050-0.25',
    'n50': '2035-0.1_2050-0.5',
}
# Capacity mandates (total-fleet basis, floor mode): tag -> GSw_NuclearCapMandateScen
CAPACITY = {
    'atb': 'abou_jaoude',
    'mck': 'mckinsey',
    'cop28': 'cop28',
    'eo25': 'eo2025',
}
# TES add-on cost: percent of the ATB 2024 moderate add-on (GSw_StorageHybrid_TESAddonMult)
SWEEP_PCT = [20, 40, 60, 80, 100]
WAVE0_MANDATES = ['n15', 'n50', 'atb', 'eo25']


def mandate_switches(tag):
    if tag in CAPACITY:
        return {
            'GSw_GenMandate': '0',
            'GSw_NuclearCapMandate': '1',
            'GSw_NuclearCapMandateScen': CAPACITY[tag],
        }
    if ENERGY[tag] is None:
        return {'GSw_GenMandate': '0'}
    return {'GSw_interpolate_mandates': ENERGY[tag]}


def case(tag, res, pct=None):
    """pct=None gives the control (hybrids off)."""
    sw = {**mandate_switches(tag), **RESOLUTION[res]}
    if pct is None:
        sw['GSw_StorageHybrid'] = '0'
    elif pct != 100:
        sw['GSw_StorageHybrid_TESAddonMult'] = str(pct / 100)
    return sw


def wave0_cases():
    cases = {}
    for res in RESOLUTION:
        for tag in WAVE0_MANDATES:
            cases[f'w0_{res}_{tag}_ctrl'] = case(tag, res)
            for pct in SWEEP_PCT:
                cases[f'w0_{res}_{tag}_ta{pct}'] = case(tag, res, pct)
    return cases


def read_descriptions():
    with open('cases.csv', newline='', encoding='utf-8') as f:
        return {r[0]: r[1] for r in csv.reader(f) if r and r[0]}


def write(path, cases, descriptions):
    for name, sw in cases.items():
        unpinned = set(sw) - set(PINS)
        assert not unpinned, f'{name}: switches missing from PINS: {unpinned}'
    missing = [k for k in PINS if k != 'ignore' and k not in descriptions]
    assert not missing, f'pinned switches not in cases.csv: {missing}'
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['', 'Description', 'Default Value'] + list(cases))
        for key, default in PINS.items():
            w.writerow([key, descriptions.get(key, ''), default]
                       + [cases[c].get(key, '') for c in cases])
    print(f'wrote {path}: {len(cases)} cases')


def main():
    descriptions = read_descriptions()
    write('cases_nuclearstor_paper_v5_wave0.csv', wave0_cases(), descriptions)


if __name__ == '__main__':
    main()
