"""Build the v6 nuclear+TES paper casefiles for the nuclear-tes-paper branch.

The paper runs in waves. Every wave uses the same wrapper set: nuclear-SMR
with molten-salt TES at BCR 0.1, 0.25, 0.5, 0.75 and 1.0. New large nuclear
is off (GSw_NuclearLarge=0), so SMR is the only new reactor; existing large
nuclear remains.
- TES wrappers use the split costing (GSw_StorageHybrid_TESCostSplit=1): the
  SMR keeps its powerblock, discharge adds BCR x the SMR powerblock, and the
  sweep scales only the TES add-on (storage-specific power share and energy)
  through GSw_StorageHybrid_TESAddonMult.
- Wave 0 picks the time resolution for all later waves. It runs the n25
  generation-share mandate (2035-0.1_2050-0.25) at 3-hour, 2-hour and 1-hour
  dispatch timeslices, with a control (hybrids off) and the TES add-on at 20,
  40 and 60% of ATB 2024 moderate at each resolution.
- Wave 1 is a broad TES add-on sweep (20-100%) on the generation-share
  mandates (base, n15, n20, n25, n50) at the resolution wave 0 selects.
- Wave 2 is a fine sweep around each mandate's breakeven TES cost.
- Wave 3 holds the sensitivities around the breakeven: a few capacity-mandate
  runs (GSw_NuclearCapMandate), new large nuclear allowed (GSw_NuclearLarge=1),
  and others to be chosen.

v6 differs from v5 in the pins: the default zone set (z90 on current main)
instead of z54, OBBBA incentives with the statutory 45Y/48E phase-down
(incentives_obbba_phasedown) instead of none, the Clean Air Act Section 111
rules off (GSw_Clean_Air_Act=0; GSw_CSAPR stays at its default), and up to 5
stress-period iterations (upstream now stops a run whose RA thresholds are
still unmet after the last iteration).

Writes, at the repo root:
- cases_nuclearstor_paper_v6_wave0_lab.csv: the 3-hour cases (4), run on the
  lab machine.
- cases_nuclearstor_paper_v6_wave0_nlr.csv: the 2-hour cases, then the
  1-hour cases (8), run on the NLR cluster.
cases_nuclearstor_paper_v5_core.csv is the record of the first test batch
(6-type ladder) and is not generated here.

Every switch the paper fixes is pinned in the Default Value column (PINS);
each case sets only the switches that define it. Descriptions come from this
branch's cases.csv. Run from the repo root:
    python z-ethan/make_paper_v6_casefiles.py
"""
import csv

# BCR ladder: one nuclear-SMR+TES wrapper type per rung
BCR_LADDER = ['0.1', '0.25', '0.5', '0.75', '1.0']

# Switches fixed for the whole paper batch (Default Value column)
PINS = {
    'ignore': '0',
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
    'incentives_suffix': 'obbba_phasedown',
    'GSw_TCPhaseout': '1',
    'GSw_Clean_Air_Act': '0',
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
    'GSw_PRM_StressIterateMax': '5',
    'reg_cap_cost_diff_suffix': 'default',
    'GSw_TransInvMaxLongTerm': '0',
    'pcm': '0',
}

# Time resolution: tag -> switches. The representative and stress-period
# timeslice lengths stay equal within each case.
RESOLUTION = {
    'h3': {},
    'h2': {
        'GSw_HourlyChunkLengthRep': '2',
        'GSw_HourlyChunkLengthStress': '2',
    },
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
# Used in the wave 3 sensitivities only.
CAPACITY = {
    'atb': 'abou_jaoude',
    'mck': 'mckinsey',
    'cop28': 'cop28',
    'eo25': 'eo2025',
}
# Wave 0: TES add-on cost as a percent of the ATB 2024 moderate add-on
# (GSw_StorageHybrid_TESAddonMult)
WAVE0_MANDATE = 'n25'
WAVE0_PCT = [20, 40, 60]
WAVE0_FILES = {
    'cases_nuclearstor_paper_v6_wave0_lab.csv': ['h3'],
    'cases_nuclearstor_paper_v6_wave0_nlr.csv': ['h2', 'h1'],
}


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


def wave0_cases(resolutions):
    cases = {}
    for res in resolutions:
        cases[f'w0_{res}_{WAVE0_MANDATE}_ctrl'] = case(WAVE0_MANDATE, res)
        for pct in WAVE0_PCT:
            cases[f'w0_{res}_{WAVE0_MANDATE}_ta{pct}'] = case(WAVE0_MANDATE, res, pct)
    return cases


def read_descriptions():
    with open('cases.csv', newline='', encoding='utf-8') as f:
        return {r[0]: r[1] for r in csv.reader(f) if r and r[0]}


def write(path, cases, descriptions):
    for name, sw in cases.items():
        unpinned = set(sw) - set(PINS)
        assert not unpinned, f'{name}: switches missing from PINS: {unpinned}'
        assert sw.get('GSw_HourlyChunkLengthRep', PINS['GSw_HourlyChunkLengthRep']) == sw.get(
            'GSw_HourlyChunkLengthStress', PINS['GSw_HourlyChunkLengthStress']), (
            f'{name}: representative and stress timeslice lengths differ')
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
    for path, resolutions in WAVE0_FILES.items():
        write(path, wave0_cases(resolutions), descriptions)


if __name__ == '__main__':
    main()
