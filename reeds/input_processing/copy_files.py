#%% ===========================================================================
### --- IMPORTS ---
### ===========================================================================
import os
import sys
import re
import datetime
import numpy as np
import pandas as pd
import argparse
import shutil
import yaml
import json
import h5py
from pathlib import Path
# Local Imports
sys.path.append(str(Path(__file__).parent.parent.parent))
import reeds


STORAGE_HYBRID_EXPANDABLE_GEN_TECHS = {
    'upv',
    'wind-ofs',
    'wind-ons',
    'geohydro-allkm',
    'egs-allkm',
    'egs-nearfield',
}

# Geothermal generation families that carry a resource supply curve (rsc_i) and,
# where applicable, endogenous spur lines. Storage-hybrid wrappers built on these
# families share the parent geo tech's supply curve and spur-line capacity rather
# than being unconstrained (see append_storage_hybrid_subsets and
# write_storage_hybrid_rsc_agg / b_inputs.gms storage_hybrid_geo_rsc_agg).
STORAGE_HYBRID_GEO_RSC_FAMILIES = {
    'geohydro-allkm',
    'egs-allkm',
    'egs-nearfield',
}


def _storage_hybrid_canon_label(value):
    return str(value).strip().lower().replace('_', '-').replace(' ', '')


def _storage_hybrid_gen_is_geo_rsc(gen_tech):
    """Return True if `gen_tech` is a numbered geothermal supply-curve family member."""
    canon = _storage_hybrid_canon_label(gen_tech)
    match = re.match(r'^(.*)-\d+$', canon)
    family = match.group(1) if match else canon
    return family in STORAGE_HYBRID_GEO_RSC_FAMILIES


def _storage_hybrid_expand_to_len(values, n, label, storage_hybrid_types):
    values = [v for v in values if v != '']
    if len(values) == 1 and n > 1:
        values = values * n
    if len(values) < n:
        raise ValueError(
            f"{label} must have 1 value or {n} values "
            f"(to match GSw_StorageHybrid_Types={storage_hybrid_types})"
        )
    return values[:n]


def _storage_hybrid_techset_paths(inputs_case):
    return [
        os.path.join(inputs_case, 'sets', 'i.csv'),
        os.path.join(inputs_case, 'i.csv'),
    ]


def _load_storage_hybrid_techs(inputs_case):
    # The i set is written to inputs_case/inputs.h5 by write_non_region_files
    # (runfiles.csv entry with GAMStype=set), so read it from there first
    try:
        techs = (
            reeds.io.read_input(inputs_case, 'i')
            .squeeze('columns')
            .dropna()
            .astype(str)
            .map(lambda x: x.strip())
        )
        techs = [t for t in techs if t != '' and not t.startswith('*')]
        if techs:
            return techs
    except (FileNotFoundError, KeyError):
        pass
    techs = []
    for techset_path in _storage_hybrid_techset_paths(inputs_case):
        if not os.path.exists(techset_path):
            continue
        techs = (
            pd.read_csv(techset_path, header=None, comment='*', dtype=str, encoding='utf-8-sig')
            .squeeze(1)
            .dropna()
            .astype(str)
            .map(lambda x: x.strip())
        )
        techs = [t for t in techs if t != '']
        if techs:
            return techs
    return techs


def _load_storage_hybrid_tech_canon_map(inputs_case):
    return {_storage_hybrid_canon_label(t): t for t in _load_storage_hybrid_techs(inputs_case)}


def _storage_hybrid_resolve_i_name(value, tech_canon_map, switch_name):
    tech = str(value).strip()
    if not tech:
        raise ValueError(f"Empty entry in {switch_name}.")
    canon = _storage_hybrid_canon_label(tech)
    if canon in tech_canon_map:
        return tech_canon_map[canon]
    raise ValueError(f"{switch_name} entry {tech!r} not found in inputs/sets/i.csv.")


def _storage_hybrid_numbered_family_members(family_canon, techs):
    members = []
    prefix = f'{family_canon}-'
    for tech in techs:
        canon = _storage_hybrid_canon_label(tech)
        if not canon.startswith(prefix):
            continue
        suffix = canon[len(prefix):]
        if suffix.isdigit():
            members.append((int(suffix), tech))
    return [tech for _, tech in sorted(members)]


def _storage_hybrid_wrapper_name(config_id, gen_tech):
    config_label = _storage_hybrid_canon_label(config_id)
    gen_label = str(gen_tech).strip().lower()
    return f'storage-hybrid-{config_label}-{gen_label}'


def build_storage_hybrid_configs(sw, inputs_case):
    """Return run-specific storage-hybrid wrapper rows for this case."""
    if 'GSw_StorageHybrid' in sw and int(sw['GSw_StorageHybrid']) == 0:
        return []

    storage_hybrid_types_raw = str(sw.get('GSw_StorageHybrid_Types', '')).strip()
    storage_hybrid_types = [t for t in storage_hybrid_types_raw.split('_') if t]
    if not storage_hybrid_types:
        return []
    n_storage_hybrid_types = len(storage_hybrid_types)

    storage_hybrid_bcrs = _storage_hybrid_expand_to_len(
        str(sw.get('GSw_StorageHybrid_BCR', '')).split('_'),
        n_storage_hybrid_types,
        'GSw_StorageHybrid_BCR',
        storage_hybrid_types_raw,
    )
    storage_hybrid_storage_techs = _storage_hybrid_expand_to_len(
        str(sw.get('GSw_StorageHybrid_StorageTechs', '')).split('_'),
        n_storage_hybrid_types,
        'GSw_StorageHybrid_StorageTechs',
        storage_hybrid_types_raw,
    )
    storage_hybrid_gridcharge = _storage_hybrid_expand_to_len(
        str(sw.get('GSw_StorageHybrid_GridCharging', '')).split('_'),
        n_storage_hybrid_types,
        'GSw_StorageHybrid_GridCharging',
        storage_hybrid_types_raw,
    )
    storage_hybrid_gen_techs = _storage_hybrid_expand_to_len(
        str(sw.get('GSw_StorageHybrid_GenTechs', '')).split('_'),
        n_storage_hybrid_types,
        'GSw_StorageHybrid_GenTechs',
        storage_hybrid_types_raw,
    )

    techs = _load_storage_hybrid_techs(inputs_case)
    tech_canon_map = {_storage_hybrid_canon_label(t): t for t in techs}
    configs = []
    seen_wrappers = set()

    for config_id, gen_tech, storage_tech, bcr, gridcharge in zip(
        storage_hybrid_types,
        storage_hybrid_gen_techs,
        storage_hybrid_storage_techs,
        storage_hybrid_bcrs,
        storage_hybrid_gridcharge,
    ):
        gen_canon = _storage_hybrid_canon_label(gen_tech)
        storage_i = _storage_hybrid_resolve_i_name(
            storage_tech,
            tech_canon_map,
            'GSw_StorageHybrid_StorageTechs',
        )

        if gen_canon in STORAGE_HYBRID_EXPANDABLE_GEN_TECHS:
            gen_members = _storage_hybrid_numbered_family_members(gen_canon, techs)
            if not gen_members:
                raise ValueError(
                    f"GSw_StorageHybrid_GenTechs family entry {gen_tech!r} did not match "
                    "any numbered technologies in inputs/sets/i.csv."
                )
            expanded = True
        else:
            gen_members = [
                _storage_hybrid_resolve_i_name(
                    gen_tech,
                    tech_canon_map,
                    'GSw_StorageHybrid_GenTechs',
                )
            ]
            expanded = False

        for gen_i in gen_members:
            wrapper = _storage_hybrid_wrapper_name(config_id, gen_i)
            wrapper_canon = _storage_hybrid_canon_label(wrapper)
            if wrapper_canon in seen_wrappers:
                raise ValueError(
                    f"Duplicate generated storage-hybrid technology {wrapper!r}. "
                    "Use distinct GSw_StorageHybrid_Types entries for repeated gen/storage pairings."
                )
            seen_wrappers.add(wrapper_canon)
            configs.append({
                'config_id': str(config_id).strip(),
                'storage_hybrid_tech': wrapper,
                'gen_tech': gen_i,
                'storage_tech': storage_i,
                'bcr': float(bcr),
                'gridcharge_ratio': float(gridcharge),
                'expanded': expanded,
            })

    return configs


def write_storage_hybrid_case_inputs(sw, inputs_case):
    configs = build_storage_hybrid_configs(sw, inputs_case)

    pd.Series(
        [c['storage_hybrid_tech'] for c in configs],
        dtype=str,
    ).to_csv(os.path.join(inputs_case, 'storage_hybrid_config.csv'), index=False, header=False)

    pd.DataFrame(
        {
            '*storage-hybrid_type': [c['storage_hybrid_tech'] for c in configs],
            'bcr': [c['bcr'] for c in configs],
        }
    ).to_csv(os.path.join(inputs_case, 'storage_hybrid_bcr.csv'), index=False)

    pd.DataFrame(
        {
            '*storage-hybrid_type': [c['storage_hybrid_tech'] for c in configs],
            'gridcharge_ratio': [c['gridcharge_ratio'] for c in configs],
        }
    ).to_csv(os.path.join(inputs_case, 'storage_hybrid_gridcharging.csv'), index=False)

    pd.DataFrame(
        {
            '*storage-hybrid_type': [c['storage_hybrid_tech'] for c in configs],
            'storage_type': [c['storage_tech'] for c in configs],
        }
    ).to_csv(os.path.join(inputs_case, 'storage_hybrid_storagetechs.csv'), index=False)

    pd.DataFrame(
        {
            '*storage-hybrid_type': [c['storage_hybrid_tech'] for c in configs],
            'gen_tech': [c['gen_tech'] for c in configs],
        }
    ).to_csv(os.path.join(inputs_case, 'storage_hybrid_gentechs.csv'), index=False)

    # Map each geothermal storage-hybrid wrapper to its parent geo supply-curve tech.
    # The parent tech is the FIRST index so that eq_rsc_INVlim is generated only for
    # the parent (mirroring the UPV/PVB tg_rsc_upvagg pattern), and the wrapper's
    # INV_RSC is summed into the parent's shared resource limit via rsc_agg.
    geo_rsc_configs = [c for c in configs if _storage_hybrid_gen_is_geo_rsc(c['gen_tech'])]
    pd.DataFrame(
        {
            '*i': [c['gen_tech'] for c in geo_rsc_configs],
            'ii': [c['storage_hybrid_tech'] for c in geo_rsc_configs],
        }
    ).to_csv(os.path.join(inputs_case, 'storage_hybrid_rsc_agg.csv'), index=False)

    if configs:
        append_storage_hybrid_techs_to_i(inputs_case, configs)
        append_storage_hybrid_subsets(inputs_case, configs)
        append_storage_hybrid_ivt(inputs_case, configs)

    return configs


def append_storage_hybrid_ivt(inputs_case, configs):
    """Append a vintage row to ivt.csv for each storage-hybrid wrapper tech.

    ivt.csv is written by runbatch.get_ivt_numclass() before copy_files runs and
    sources only static rows from inputs/userinput/ivt_{suffix}.csv. The
    dynamically generated storage-hybrid-{config}-{gentech} wrappers are not in
    that source, so without this patch they have no ivt(i,newv,t) entries and
    GAMS never adds them to valcap (see b_inputs.gms valcap rules at L2556+).

    Each wrapper inherits its gen tech's vintage schedule. This keeps newv
    vintages aligned with the gen tech (whose plant_char, supply curve, and
    heat_rate the wrapper already inherits) and does not change numclass since
    the max v index is unchanged.

    ivt.csv stores numbered tech families in GAMS-style condensed range form
    (e.g. ``egs_allkm_1*egs_allkm_10``) rather than as one row per numbered
    member. We mirror that convention by emitting one condensed range row per
    (config_id, gen_tech_family) group when the wrappers cover a contiguous
    suffix range and share an identical vintage schedule; otherwise we fall
    back to individual rows.
    """
    ivt_path = os.path.join(inputs_case, 'ivt.csv')
    if not os.path.exists(ivt_path):
        return

    ivt = pd.read_csv(ivt_path, index_col=0)

    suffix_re = re.compile(r'^(.*)_(\d+)$')

    def _parse_range(index_value):
        """Return (prefix, lo, hi) if `index_value` is a GAMS range, else None."""
        text = str(index_value).strip()
        if '*' not in text:
            return None
        left, right = [part.strip() for part in text.split('*', 1)]
        left_match = suffix_re.match(left)
        right_match = suffix_re.match(right)
        if not (left_match and right_match):
            return None
        if left_match.group(1) != right_match.group(1):
            return None
        return left_match.group(1), int(left_match.group(2)), int(right_match.group(2))

    # Map every individual tech name (including those expanded from ranges) to
    # its vintage row in ivt.csv so wrappers can look up their gen tech values.
    tech_to_row = {}
    covered_techs = set()
    for ivt_index, row in ivt.iterrows():
        text = str(ivt_index).strip()
        parsed = _parse_range(text)
        if parsed is None:
            tech_to_row[text] = row
            covered_techs.add(text)
        else:
            prefix, lo, hi = parsed
            for n in range(lo, hi + 1):
                name = f'{prefix}_{n}'
                tech_to_row[name] = row
                covered_techs.add(name)

    # Group configs by (config_id, gen_tech_family_prefix) so contiguous
    # numbered wrappers can be emitted as a single condensed range row.
    grouped = {}
    singletons = []
    for config in configs:
        wrapper = config['storage_hybrid_tech']
        gen_tech = config['gen_tech']
        match = suffix_re.match(gen_tech)
        if match:
            key = (config['config_id'], match.group(1))
            grouped.setdefault(key, []).append((int(match.group(2)), wrapper, gen_tech))
        else:
            singletons.append((wrapper, gen_tech))

    new_rows = {}

    def _lookup_gen_row(gen_tech, wrapper):
        if gen_tech not in tech_to_row:
            raise ValueError(
                f"Cannot extend ivt.csv for storage-hybrid wrapper {wrapper!r}: "
                f"underlying gen tech {gen_tech!r} has no row in ivt.csv."
            )
        return tech_to_row[gen_tech]

    for (config_id, gen_prefix), members in grouped.items():
        members.sort(key=lambda item: item[0])
        suffixes = [item[0] for item in members]
        contiguous = suffixes == list(range(suffixes[0], suffixes[-1] + 1))
        rows = [_lookup_gen_row(item[2], item[1]) for item in members]
        identical = all(row.equals(rows[0]) for row in rows)
        wrapper_prefix = (
            f'storage-hybrid-{_storage_hybrid_canon_label(config_id)}-{gen_prefix}'
        )

        if contiguous and identical:
            lo_wrapper = f'{wrapper_prefix}_{suffixes[0]}'
            hi_wrapper = f'{wrapper_prefix}_{suffixes[-1]}'
            if all(f'{wrapper_prefix}_{n}' in covered_techs for n in suffixes):
                continue
            range_index = (
                lo_wrapper if lo_wrapper == hi_wrapper
                else f'{lo_wrapper}*{hi_wrapper}'
            )
            new_rows[range_index] = rows[0]
        else:
            for suffix, wrapper, gen_tech in members:
                if wrapper in covered_techs:
                    continue
                new_rows[wrapper] = tech_to_row[gen_tech]

    for wrapper, gen_tech in singletons:
        if wrapper in covered_techs:
            continue
        new_rows[wrapper] = _lookup_gen_row(gen_tech, wrapper)

    if not new_rows:
        return

    appended = pd.DataFrame.from_dict(new_rows, orient='index', columns=ivt.columns)
    appended.index.name = ivt.index.name
    pd.concat([ivt, appended]).to_csv(ivt_path)


def append_storage_hybrid_techs_to_i(inputs_case, configs):
    new_techs = [c['storage_hybrid_tech'] for c in configs]
    # The i set lives in inputs_case/inputs.h5 (written by write_non_region_files);
    # h5_to_gdx.py later converts it to the gdx loaded by b_inputs.gms
    try:
        i_set = reeds.io.read_input(inputs_case, 'i').squeeze('columns').astype(str)
    except (FileNotFoundError, KeyError):
        i_set = None
    if i_set is not None:
        existing = {_storage_hybrid_canon_label(t) for t in i_set}
        to_add = [t for t in new_techs if _storage_hybrid_canon_label(t) not in existing]
        if to_add:
            i_out = pd.Series(list(i_set) + to_add, name='*')
            reeds.io.write_to_inputs_h5(
                i_out, 'i', inputs_case, 'set',
                comment='generation technologies', verbose=0,
            )
        return
    for techset_path in _storage_hybrid_techset_paths(inputs_case):
        if not os.path.exists(techset_path):
            continue
        with open(techset_path, 'r', encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        existing = {_storage_hybrid_canon_label(line) for line in lines if line.strip()}
        to_add = [tech for tech in new_techs if _storage_hybrid_canon_label(tech) not in existing]
        if not to_add:
            continue
        with open(techset_path, 'a', encoding='utf-8') as f:
            if lines and lines[-1].strip():
                f.write('\n')
            f.write('\n'.join(to_add))
            f.write('\n')


def append_storage_hybrid_subsets(inputs_case, configs):
    path = os.path.join(inputs_case, 'tech-subset-table.csv')
    if not os.path.exists(path):
        return

    df = pd.read_csv(path, index_col=0, dtype=str, keep_default_na=False).fillna('')
    required_cols = ['STORAGE', 'HYBRID_PLANT', 'STORAGE-HYBRID']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            "tech-subset-table.csv is missing required storage-hybrid subset columns: "
            + ', '.join(missing_cols)
        )

    for config in configs:
        tech = config['storage_hybrid_tech']
        if tech not in df.index:
            df.loc[tech] = ''
        df.loc[tech, required_cols] = 'YES'
        # Geothermal storage-hybrid wrappers carry a resource supply curve so their
        # buildout is bounded by the shared parent geo supply curve. Marking RSC='YES'
        # puts the wrapper in rsc_i(i); the actual binding limit is enforced on the
        # parent tech via storage_hybrid_geo_rsc_agg -> rsc_agg in b_inputs.gms.
        if _storage_hybrid_gen_is_geo_rsc(config['gen_tech']):
            if 'RSC' not in df.columns:
                raise ValueError(
                    "tech-subset-table.csv is missing the 'RSC' column required to "
                    "enable geothermal storage-hybrid supply curves."
                )
            df.loc[tech, 'RSC'] = 'YES'

    df.to_csv(path)


def translate_legacy_storage_hybrid_labels(df, sw, inputs_case, filename):
    if 'i' not in df.columns:
        return df

    configs = build_storage_hybrid_configs(sw, inputs_case)
    if not configs:
        return df

    by_legacy_label = {}
    for config in configs:
        legacy_label = f"storage-hybrid{_storage_hybrid_canon_label(config['config_id'])}"
        by_legacy_label.setdefault(legacy_label, []).append(config['storage_hybrid_tech'])

    replacements = {}
    for legacy_label, wrappers in by_legacy_label.items():
        unique_wrappers = sorted(set(wrappers))
        if len(unique_wrappers) == 1:
            replacements[legacy_label] = unique_wrappers[0]
        else:
            legacy_hits = df['i'].astype(str).map(_storage_hybrid_canon_label) == legacy_label
            if legacy_hits.any():
                raise ValueError(
                    f"{filename} references legacy {legacy_label!r}, but that storage-hybrid "
                    "configuration expands to multiple generated technologies. Use an explicit "
                    "generated storage-hybrid technology name in the demonstration plant input."
                )

    if not replacements:
        return df

    df = df.copy()
    i_canon = df['i'].astype(str).map(_storage_hybrid_canon_label)
    for legacy_label, wrapper in replacements.items():
        mask = i_canon == legacy_label
        if not mask.any():
            continue
        old_values = df.loc[mask, 'i'].astype(str)
        df.loc[mask, 'i'] = old_values.map(
            lambda value: wrapper.lower() if value == value.lower() else wrapper
        )
        if 'coolingwatertech' in df.columns:
            old_prefix = old_values.iloc[0]
            cooling = df.loc[mask, 'coolingwatertech'].astype(str)
            df.loc[mask, 'coolingwatertech'] = cooling.map(
                lambda value: wrapper + value[len(old_prefix):]
                if value.lower().startswith(old_prefix.lower()) else value
            )

    return df


#%% ===========================================================================
### --- General Read Functions---
### ===========================================================================
def is_required_file(runfiles_row, sw):
    """
    Determine whether or not the file corresponding to the provided row of
    runfiles.csv is required using the row's "required_if" value.

    Note that the code snippets assume that a variable 'sw' has been
    initialized and holds the result of reeds.io.get_switches(), which is why
    this function takes 'sw' as an argument despite 'sw' not being used
    explicitly.
    """
    required_if_value = runfiles_row['required_if']
    is_required = eval(required_if_value)
    if is_required not in [True, False, 1, 0]:
        raise ValueError(
            "The 'required_if' value must evaluate to a true/false statement."
            f"Update the entry for {runfiles_row['filename']} in "
            "runfiles.csv."
        )
    return is_required


def read_runfiles(reeds_path, sw):
    """
    Read runfiles.csv and return the runfiles dataframe
    Identify files that have a region index versus those that do not.
    """
    runfiles = (
        pd.read_csv(
            os.path.join(reeds_path, 'reeds', 'input_processing', 'runfiles.csv'),
            dtype={'fix_cols':str,
                   'depends_on_switch':str,
                   'depends_on_switch_value': str},
            comment='#',
        ).fillna({'fix_cols':'',
                  'depends_on_switch':'',
                  'depends_on_switch_value':''})
    )

    runfiles['file_is_required'] = runfiles.apply(
        axis=1,
        func=is_required_file,
        args=(sw,),
    )

    # Determine existence of each file
    runfiles['full_filepath'] = runfiles.apply(
        axis=1,
        func=lambda row: os.path.join(reeds_path, row['filepath'].format(**sw))
    )
    runfiles['file_exists'] = (
        runfiles['full_filepath'].apply(lambda x: os.path.exists(x))
    )

    # Raise an error if any of the required files are missing
    missing_required_files = (
        runfiles.loc[runfiles['file_is_required'] & ~runfiles['file_exists']]
        ['filepath']
        .tolist()
    )
    if len(missing_required_files) > 0:
        raise FileNotFoundError(
            'The following required files are missing. Add them '
            'to the inputs directory or update runfiles.csv to specify optionality:\n{}\n'
            .format('\n'.join(missing_required_files))
        )

    # Non-region files that need copied either do not have an entry in region_col
    # or have 'ignore' as the entry. They also have a filepath specified.
    non_region_files = (
        runfiles[
            (
                (runfiles['region_col'].isna())
                | (runfiles['region_col'] == 'ignore')
            )
            & (~runfiles['filepath'].isna())]
        )

    # Region files are those that have a region and do not specify 'ignore'
    # Also ignore files that are created after this script runs (i.e., post_copy = 1)
    region_files = (
        runfiles[
            (~runfiles['region_col'].isna())
            & (runfiles['region_col'] != 'ignore')
            & (runfiles['post_copy'] != 1)]
        )

    return runfiles, non_region_files, region_files


def get_source_deflator_map(reeds_path):
    """
    Get the deflator for each input file
    """
    # Inflation-adjusted inputs
    sources_dollaryear = pd.read_csv(
        os.path.join(reeds_path,'docs','sources.csv'),
        usecols=["RelativeFilePath", "DollarYear"]
    )
    deflator = pd.read_csv(
        os.path.join(reeds_path,'inputs','financials','deflator.csv'),
        header=0, names=['Dollar.Year','Deflator'], index_col='Dollar.Year').squeeze(1)
    # Create a mapping between inputs' relative filepaths and their deflation
    # multipliers based on the dollar years their monetary values are in
    sources_dollaryear = (
        # Filter out rows that don't contain a valid dollar year
        sources_dollaryear[pd.to_numeric(sources_dollaryear['DollarYear'], errors='coerce').notnull()]
        # Note: We must remove the backslash that prepends each relative filepath
        # for compatibility with the 'os' package (otherwise it is treated as an absolute path)
        .assign(RelativeFilePath=sources_dollaryear["RelativeFilePath"].str[1:])
        .astype({"DollarYear": "int64"})
        .rename(columns={"DollarYear": "Dollar.Year"})
        .merge(deflator,on="Dollar.Year",how="left")
    )

    source_deflator_map = dict(zip(sources_dollaryear["RelativeFilePath"], sources_dollaryear["Deflator"]))

    return source_deflator_map

def get_regions_and_agglevel(
    reeds_path,
    inputs_case,
    save_regions_and_agglevel=True,
):
    """
    Create a regional mapping to help filter for specific regions and aggregation levels.
    This function reads various input files, processes them to create mappings of regions
    at different levels of aggregation, and writes these mappings to csv files.

    If save_regions_and_agglevel is False do not save intermediate files
    (You just want the mapping)
    """
    sw = reeds.io.get_switches(inputs_case)

    hierarchy = reeds.io.assemble_hierarchy(inputs_case, extra=False)
    hierarchy['offshore'] = 0
    # Label offshore zones if using
    if int(sw.GSw_OffshoreZones):
        offshore_zones = (
            reeds.io.assemble_hierarchy(
                fpath=os.path.join(
                    reeds_path,
                    'inputs',
                    'zones',
                    'hierarchy_offshore.csv'
                ),
                extra=False,
            )
            ['ba']
            .tolist()
        )
        hierarchy.loc[hierarchy.r.isin(offshore_zones), 'offshore'] = 1

    # Save the original hierarchy file: used in recf.py and hourly_*.py scripts
    if save_regions_and_agglevel:
        hierarchy.to_csv(
            os.path.join(inputs_case,'hierarchy_original.csv'),
            index=False, header=True
            )

    # Add a row for each county
    county2zone = (
        reeds.io.get_county2zone(GSw_ZoneSet=sw['GSw_ZoneSet'], as_map=False)
        .rename(columns={'r':'ba'})
    )
    county2zone['county'] = 'p' + county2zone.FIPS
    county2zone.to_csv(
        os.path.join(inputs_case, 'county2zone_original.csv'),
        index=False
    )

    # Add county info to hierarchy
    hierarchy = hierarchy.merge(
        county2zone.drop(columns=['FIPS','state']),
        left_on='r',
        right_on='ba',
        how='outer'
    )

    # Add legacy zone (z134) info to hierarchy
    # This is needed because some inputs still have data at z134 resolution,
    # so we need to capture these legacy zones when subsetting to valid regions
    county2zone_z134 = reeds.io.get_county2zone(GSw_ZoneSet='z134', as_map=True)
    county2zone_z134.index = 'p' + county2zone_z134.index
    hierarchy['legacy_ba'] = hierarchy['county'].map(county2zone_z134)

    # Subset hierarchy for the region of interest (based on the GSw_Region switch)
    # Parse the GSw_Region switch. If it includes a '/' character, it has the format
    # {column of hierarchy.csv}/{period-delimited entries to keep from that column}.
    hier_sub = pd.DataFrame()
    # allow the list defined by the user to include multiple spatial resolutions
    region_groups = sw['GSw_Region'].split('//') if '//' in sw['GSw_Region'] else [sw['GSw_Region']]
    # separate lists associated with each spatial resolution
    for region_group in region_groups:
        GSw_RegionLevel, GSw_Region = region_group.split('/')
        GSw_Region = GSw_Region.split('.')

        hier_sub_partial = pd.concat([
            hierarchy[hierarchy[GSw_RegionLevel] == region] for region in GSw_Region
        ])

        hier_sub = pd.concat([hier_sub, hier_sub_partial])

    # Write out mappings of r and ba to all counties
    r_county = hier_sub[['r','county']].dropna(subset='county')

    # Rewrite county2zone for this case
    county2zone_agg = county2zone.merge(r_county, on='county')
    county2zone_agg.to_csv(
        os.path.join(inputs_case, 'county2zone.csv'),
        index=False
    )

    if save_regions_and_agglevel:
        r_county.to_csv(
            os.path.join(inputs_case, 'r_county.csv'), index=False)

        # Write out mapping of r to census divisions
        hier_sub[['r','cendiv']].drop_duplicates().to_csv(
            os.path.join(inputs_case, 'r_cendiv.csv'), index=False)

    # Find all the unique elements that might define a region
    val_r_all = []
    for column in hier_sub.columns.drop('offshore', errors='ignore'):
        val_r_all.extend(hier_sub[column].dropna().unique().tolist())

    # Converting to a set ensures that only unique values are kept
    val_r_all = sorted(list(set(val_r_all)))

    if save_regions_and_agglevel:
        pd.Series(val_r_all).to_csv(
            os.path.join(inputs_case, 'val_r_all.csv'), header=False, index=False)

    # Drop county name and resolution columns
    hier_sub = hier_sub.drop(['county_name'],axis=1)


    # Collapse to only unique regions
    hier_sub = hier_sub.drop_duplicates(subset=['r'])

    # Sort hier_sub by r so that "ord(r)" commands in GAMS result in the properly
    # ordered outputs
    hier_sub['numeric_value'] = hier_sub['r'].str.extract(r'(\d+)').astype(float)
    hier_sub = hier_sub.sort_values(by='numeric_value').drop('numeric_value', axis=1)

    ### TEMPORARY 20260402: For now just assign 'itlgrp' hierarchy level to 'r'
    hier_sub['itlgrp'] = hier_sub['r']
    hier_sub[['r','itlgrp']].rename(columns={'r':'*r'}).to_csv(
        os.path.join(inputs_case, 'hierarchy_itlgrp.csv'), index=False)

    itlgrp = hier_sub['itlgrp'].drop_duplicates().rename()
    reeds.io.write_to_inputs_h5(
        itlgrp, 'itlgrp', inputs_case, gamstype='set',
        comment='zone for additional interface transfer limit constraint',
    )

    # Drop any substate region columns as these will no longer be needed
    hier_sub = hier_sub.drop(['county', 'ba', 'itlgrp'], axis=1)

    # Populate val_st as unique states (not st_int) from the subsetted hierarchy table
    # Also include "voluntary" state for modeling voluntary market REC trading
    val_st = list(hier_sub['st'].unique()) + ['voluntary']

    # Write out the unique values of each column in hier_sub to val_[column name].csv
    # Note the conversion to a pd Series is necessary to leverage the to_csv function
    if save_regions_and_agglevel:
        comments = {
            'cendiv': 'census division',
            'country': 'nation',
            'h2ptcreg': 'H2 production tax credit region',
            'hurdlereg': 'hurdle rate region (for extra costs on interregional flows)',
            'interconnect': 'synchronous interconnection',
            'nercr': 'NERC region',
            'transgrp': 'sub-FERC-1000 region',
            'transreg': 'Transmission Planning Regions from FERC Order 1000',
            'usda_region': 'biomass supply curve region',
            'gasreg': 'gas price region (for applying daily temperature-based price adjustments)',
        }
        for level, comment in comments.items():
            df = pd.Series(hier_sub[level].unique())
            reeds.io.write_to_inputs_h5(
                df, level, inputs_case, gamstype='set', comment=comment,
            )

        # Use a modified version of val_st that includes 'voluntary'
        reeds.io.write_to_inputs_h5(
            pd.Series(val_st), 'st', inputs_case, gamstype='set',
            comment="state (or special 'voluntary' entry for corporate procurements)",
        )

        # Rename columns and save as hierarchy.csv
        (
            hier_sub
            .rename(columns={'r':'*r'})
            .drop(columns=['legacy_ba', 'offshore'], errors='ignore')
        ).to_csv(os.path.join(inputs_case, 'hierarchy.csv'), index=False)

        # Write offshore zones
        offshore = hier_sub.loc[hier_sub.offshore == 1, 'r']
        reeds.io.write_to_inputs_h5(
            offshore, 'offshore', inputs_case, gamstype='set', comment='offshore zones',
        )

    levels = [i for i in hier_sub if i != 'offshore']
    valid_regions = {level: list(hier_sub[level].unique()) for level in levels}

    val_r = sorted(valid_regions['r'])

    # Export region files
    if save_regions_and_agglevel:
        reeds.io.write_to_inputs_h5(
            pd.Series(val_r), 'r', inputs_case, gamstype='set', comment='regions',
        )

    regions_and_agglevel = {
        "valid_regions": valid_regions,
        "val_r_all": val_r_all,
        "val_st": val_st,
        "r_county": r_county,
        "levels": levels
    }

    return regions_and_agglevel


def read_banned_tech_file(full_path, filepath, inputs_case, r_county):
    """
    Parses the list of regionally (state/county-level) banned techs from the
    provided YAML file and reformats it as a GAMS-compatible table.
    Regions banning nuclear are exported as their own list, as nuclear bans
    have their own switches and functionalities that are handled separately.
    """
    if not (full_path.endswith('yaml') or full_path.endswith('yml')):
        raise TypeError(f'filetype for {full_path} is not .yaml/.yml')

    with open(full_path) as f:
        techs_banned = yaml.safe_load(f)

    hierarchy = pd.read_csv(os.path.join(inputs_case, 'hierarchy.csv'))
    df = pd.DataFrame(data=0, columns=hierarchy['*r'], index=techs_banned.keys())

    # Nuclear bans are handled specially in the model,
    # so we create a separate dataframe for those regions.
    nuclear_ban_regions = pd.DataFrame(data=[], columns=['*r'])
    for tech, ban_lists in techs_banned.items():
        ban_regions = []

        if not all([x in ['st', 'county'] for x in ban_lists.keys()]):
            raise NotImplementedError(
                "The regional scope of banned techs must be either 'st' or 'county'. "
                f"Update the nested keys in {filepath}."
            )

        # Apply state-wide bans to all of the regions belonging to those states
        if 'st' in ban_lists.keys():
            ban_states = ban_lists['st']
            state_ban_regions = list(hierarchy.loc[hierarchy.st.isin(ban_states)]['*r'])
            ban_regions.extend(state_ban_regions)

        # Apply county-wide bans to regions where all of the counties have banned the tech
        if 'county' in ban_lists.keys():
            ban_counties = ['p' + str(fips).zfill(5) for fips in ban_lists['county']]
            num_counties = r_county.r.value_counts()
            num_bans = r_county.loc[r_county.county.isin(ban_counties)].r.value_counts()
            fully_banned = num_counties.loc[num_counties - num_bans == 0].index.tolist()
            ban_regions.extend(fully_banned)

        if tech == 'nuclear':
            nuclear_ban_regions['*r'] = ban_regions
        else:
            df.loc[tech, ban_regions] = 1

    df = df.reset_index(names=['i'])

    return df, nuclear_ban_regions


def subset_to_valid_regions(
    sw,
    region_file_entry,
    regions_and_agglevel,
    inputs_case=None,
    agg=True,
):
    """
    Filter data for valid regions and return a dataframe
    """
    levels = regions_and_agglevel["levels"]
    val_r_all = regions_and_agglevel["val_r_all"]
    val_st = regions_and_agglevel["val_st"]
    valid_regions = regions_and_agglevel["valid_regions"]

    # Read file and return dataframe filtered for valid regions
    filepath = region_file_entry['filepath']
    filename = region_file_entry['filename']
    full_path = region_file_entry['full_filepath']

    # Get the filetype of the input file from the filepath string
    filetype_in = os.path.splitext(filepath)[1].strip('.')

    region_col = region_file_entry['region_col']
    fix_cols = [i for i in region_file_entry['fix_cols'].split(',') if i != '']

    # Replace '{switchnames}' in full_path with corresponding switch values
    full_path = full_path.format(**sw)
    ## Filename conditions
    if filename.startswith('supplycurve'):
        df = reeds.io.assemble_supplycurve(
            full_path,
            case=os.path.dirname(os.path.normpath(inputs_case)),
            agg=agg,
        ).reset_index()
    elif filename == 'techs_banned.csv':
        df, nuclear_ban_regions = read_banned_tech_file(
            full_path,
            filepath,
            inputs_case,
            r_county=regions_and_agglevel['r_county']
        )
        nuclear_ban_regions.to_csv(
            os.path.join(inputs_case,'nuclear_ba_ban_list.csv'),
            index=False
        )
    ## Filetype conditions
    elif filetype_in == 'h5':
        df = reeds.io.read_file(full_path)
    elif filetype_in == 'csv':
        # do not read in # as comment if reading unitdata_orig.csv to avoid omitting data
        # (temporary. will remove after updating NEMS and remove # from unit ID columns)
        if filename == 'unitdata_orig.csv':
            df = pd.read_csv(full_path, dtype={'FIPS':str, 'fips':str, 'cnty_fips':str})
        else:
            df = pd.read_csv(full_path, dtype={'FIPS':str, 'fips':str, 'cnty_fips':str}, comment='#')
    else:
        raise ValueError(f'Unmatched filename ({filename}) or filetype ({filetype_in})')

    # Filter data to valid regions
    df = filter_data(
        df,
        region_col,
        fix_cols,
        levels,
        val_r_all,
        valid_regions,
        val_st,
        filename=filename
    )

    return df


#%% ===========================================================================
### --- General Write Functions---
### ===========================================================================
def write_empty_file(filepath):
    filetype = os.path.splitext(filepath)[1].strip('.')
    if filetype == 'h5':
        with h5py.File(filepath, 'w'):
            pass
    else:
        open(filepath, 'a').close()

    return


def scalar_csv_to_txt(path_to_scalar_csv):
    """
    Write a scalar csv to GAMS-readable text
    Format of csv should be: scalar,value,comment
    """
    # Load the csv
    dfscalar = pd.read_csv(
        path_to_scalar_csv,
        header=None, names=['scalar','value','comment'], index_col='scalar').fillna(' ')
    # Create the GAMS-readable string (comments can only be 255 characters long)
    scalartext = '\n'.join([
        'scalar {:<30} "{:<5.255}" /{}/ ;'.format(
            i, row['comment'], row['value'])
        for i, row in dfscalar.iterrows()
    ])
    # Write it to a file, replacing .csv with .txt in the filename
    with open(path_to_scalar_csv.replace('.csv','.txt'), 'w') as w:
        w.write(scalartext)

    return dfscalar


def param_csv_to_txt(infilepath, outdirpath, writelist=True):
    """
    Write a parameter csv to GAMS-readable text
    Format of csv should be: parameter(indices),units,comment
    """
    # Load the csv
    dfparams = pd.read_csv(
        infilepath,
        index_col='param', comment='#',
    )
    # Create the GAMS-readable param definition string (comments must be ≤255 characters)
    paramtext = '\n'.join([
        f'parameter {i:<50} "--{row.units}-- {row.comment:.255}" ;'
        # Don't define parameters with an input flag because they already exist
        for i, row in dfparams.loc[dfparams.input != 1].iterrows()
    ])
    # Write it to a file, replacing .csv with .gms in the filename
    param_gms_path = Path(outdirpath, Path(infilepath).stem + '.gms')
    with open(param_gms_path, 'w') as w:
        w.write(paramtext)
    # Write the list of parameters if desired
    if writelist:
        # Create the GAMS-readable list of parameters (without indices)
        paramlist = '\n'.join(dfparams.index.map(lambda x: x.split('(')[0]).tolist())
        param_list_path = Path(
            outdirpath,
            Path(infilepath).stem.replace('params','paramlist') + '.txt'
        )
        with open(param_list_path, 'w') as w:
            w.write(paramlist)

    return dfparams

# Function to filter data to valid regions
def filter_data(
    df,
    region_col,
    fix_cols,
    levels,
    val_r_all,
    valid_regions,
    val_st,
    filename
):
    if region_col == 'wide':
        # Check to see if the regions are listed in the columns. If they are,
        # then use those columns

        # Need check for case where there are no data for val_r_all (but not because of the column headr formatting) and empty dataframe needs to be returned
        if (len([x for x in val_r_all if x in df.columns])==0) & ( not any('|' in col for col in df.columns)) & ( not any('_' in col for col in df.columns)):
            df = df.loc[:,df.columns.isin(fix_cols + val_r_all)]
        elif df.columns.isin(val_r_all).any():
            df = df.loc[:,df.columns.isin(fix_cols + val_r_all)]
        else:
            # Checks if regions are in columns as '[class]|[region]' or '[class]_[region]' (e.g. in 8760 RECF data).
            # This 'try' attempts to split each column name using '|' and '_' as delimiters and checks the second
            # value for any regions.
            # If it can't do so, it will instead use a blank dataframe.
            try:
                if any('|' in col for col in df.columns):
                    delim = '|'
                elif '_' in df.columns[0]:
                    delim = '_'
                else:
                    raise ValueError(f"Cannot split columns in {filename} by '|' or '_' (example: {df.columns[0]}).")
                column_mask = (df.columns.str.split(delim,expand=True)
                                .get_level_values(1)
                                .isin(val_r_all)
                                .tolist()
                )
                df = df.loc[:, column_mask | df.columns.isin(fix_cols)]
                # Empty h5 files cannot be read in, causing errors in recf.py.
                # In the case that val_r_all filters out all columns, leaving an empty dataframe,
                # fill a single column with NaN to preserve the file index for use in recf.py
                if len(df.columns) == 0:
                    df = pd.DataFrame(np.nan, index = df.index,columns = val_r_all)
            except Exception:
                df = pd.DataFrame()

    # Subset on the valid regions except for r regions
    # (r regions might also include s regions, which complicates things...)
    elif ((region_col.strip('*') in levels) & (region_col.strip('*') != 'r')):
        df = df.loc[df[region_col].isin(valid_regions[region_col.strip('*')])]

    # Subset both column of 'st' and columns of state if st_st
    elif (region_col.strip('*') == 'st_st'):
        # make sure both the state regions are in val_st
        df = df.loc[df['st'].isin(val_st)]
        df = df.loc[:,df.columns.isin(fix_cols + val_st)]

    elif (region_col.strip('*') == 'r_cendiv'):
        # Make sure both the r is in val_r_all and cendiv is in val_cendiv
        val_cendiv = valid_regions['cendiv']
        df = df.loc[df['r'].isin(val_r_all)]
        df = df.loc[:,df.columns.isin(["r"] + val_cendiv)]

    # Subset on val_{level} if region_col == 'wide_{level}'
    elif (region_col.split('_')[0] == 'wide') and (region_col.split('_')[1] in valid_regions.keys()):
        # Check to see if the region values are listed in the columns. If they are,
        # then use those columns
        val_reg = valid_regions[region_col.split('_')[1]]
        if df.columns.isin(val_reg).any():
            df = df.loc[:,df.columns.isin(fix_cols + val_reg)]
        # Otherwise just use an empty dataframe
        else:
            df = pd.DataFrame()

    # If region_col is not wide, st, or aliased..
    else:
        df = df.loc[df[region_col].isin(val_r_all)]

    return df


def write_scalars(scalars, inputs_case):
    """
    Write modified scalars.csv file
    Special-case handling of scalars.csv: turn years_until into firstyear
    """
    toadd = scalars.loc[scalars.index.str.startswith('years_until')].copy()
    toadd.index = toadd.index.map(lambda x: x.replace('years_until','firstyear'))
    toadd.value += scalars.loc['this_year','value']
    scalars_write = pd.concat([scalars, toadd], axis=0)

    # Trim trailing decimal zeros
    scalars_write.value = scalars_write.value.astype(str).replace(r'\.0+$', '', regex=True)
    scalars_write.to_csv(os.path.join(inputs_case, 'scalars.csv'), header=False)

    # Rewrite the scalar tables as GAMS-readable definition
    scalar_csv_to_txt(os.path.join(inputs_case,'scalars.csv'))


def write_non_region_file(
    row,
    case,
    dir_dst,
    sw,
    regions_and_agglevel,
    source_deflator_map,
):
    """
    Copy a non-region specific file (filename) from src_file to dir_dst
    """
    # Check if source file exists and is not rev_paths.csv
    if (os.path.exists(row.full_filepath)) and (row.filename != 'rev_paths.csv'):

        # Special Case: Values in load_multiplier.csv need to be rounded prior to copy
        if row.filename == 'load_multiplier.csv':
            df_load_multiplier = pd.read_csv(row.full_filepath).round(6)
            df_load_multiplier.to_csv(os.path.join(dir_dst,'load_multiplier.csv'),index=False)

        elif row.filename == 'h2_exogenous_demand.csv':
            # h2_exogenous_demand.csv has a path in runfiles.csv (considered a non-region file)
            df=pd.read_csv(row.full_filepath, index_col=['p','t'])
            df[sw['GSw_H2_Demand_Case']].round(3).rename_axis(['*p','t']).to_csv(
                os.path.join(dir_dst,'h2_exogenous_demand.csv')
            )

        elif row.filename in ['energy_communities.csv', 'nuclear_energy_communities.csv']:
            # Map energy communities to regions and compute the percentage of energy communities
            # within each region to assign a weighted bonus.

            # Rename column in energy_communities.csv and map county to r, save as energy_communities.csv
            energy_communities = pd.read_csv(row.full_filepath)
            energy_communities.rename(columns={'County Region': 'county'}, inplace=True)

            r_county = regions_and_agglevel ['r_county']
            # Map energy communities to regions
            e_df = pd.merge(energy_communities, r_county, on='county', how='left').dropna()

            # Group energy community regions and count the number of counties in each
            energy_county_counts = e_df.groupby('r')['county'].nunique()

            # Group all regions and count the number of counties in each
            total_county_counts = r_county.groupby('r')['county'].nunique()

            # Calculate the percentage of counties that are energy communities in each region
            e_df = (energy_county_counts / total_county_counts).round(3).reset_index().dropna()

            # Rename columns from ['r','county'] to ['r','percentage_energy_communities']
            e_df.columns = ['r', 'percentage_energy_communities']

            e_df.to_csv(os.path.join(dir_dst, row.filename),index=False)

        else:
            if str(row.GAMStype).lower() in ['set', 'parameter']:
                reeds.io.write_csv_to_inputs_h5(
                    filepath=row.full_filepath,
                    case=case,
                    gamstype=row.GAMStype.lower(),
                    name=(None if isinstance(row.GAMSname, float) else row.GAMSname),
                    comment=(row.GAMScomment if isinstance(row.GAMScomment, str) else ''),
                )
            else:
                shutil.copy(row.full_filepath, os.path.join(dir_dst, row.filename))

            if row.filename == 'scalars.csv':
                # Rewrite scalars.csv as GAMS-readable definition
                scalars = reeds.io.get_scalars(full=True)
                write_scalars(scalars, dir_dst)


def write_non_region_files(non_region_files, sw, inputs_case, regions_and_agglevel, source_deflator_map):
    """
    Copy non-region specific files to the input case directory.
    """
    print('Copying non-region-indexed files')
    case = reeds.io.standardize_case(inputs_case)
    for _, row in non_region_files.iterrows():
        if row['filepath'].split('/')[0] in ['inputs','postprocessing','tests']:
            dir_dst = inputs_case
        else:
            dir_dst = os.path.dirname(inputs_case)

        # If the file is missing and not required,
        # an empty file is written with the given filename.
        if (not row['file_exists']) and (not row['file_is_required']):
            print(f'...writing empty file {row.filename}')
            write_empty_file(os.path.join(dir_dst,row['filename']))
        else:
            print(f'...copying {row.filename}')
            write_non_region_file(
                row,
                case,
                dir_dst,
                sw,
                regions_and_agglevel,
                source_deflator_map,
            )

    
def calculate_county_fractions(df, county2zone_with_legacy_bas):
    """
    Calculates the values associated with each county as a percentage
    of the total values for the county's state, zone, and legacy BA
    (where "zone" means a region from the zone set corresponding to
    the current run and "legacy BA" means a region from the z134 zone set).
    Note the calculation of the county-to-legacy BA fractions will eventually
    be deprecated once the 134-zone structure is removed from all spatial
    inputs (see https://github.com/ReEDS-Model/ReEDS/issues/16).

    The provided dataframe "df" must have columns 'FIPS' and 'value'.
    The provided dataframe "county2zone_with_legacy_bas" must have columns
    'FIPS', 'state', 'r', and 'legacy_ba'.
    """
    required_columns = ['FIPS', 'value']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if len(missing_columns) > 0:
        raise KeyError(f"Provided dataframe is missing required columns {missing_columns}")

    df = df.merge(county2zone_with_legacy_bas)
    df['fracdata'] = (
        df.groupby('legacy_ba')
        ['value']
        .transform(lambda x: x / x.sum())
    )
    for col in ['r', 'state']:
        df[f'{col}_frac'] = (
            df.groupby(col)
            ['value']
            .transform(lambda x: x / x.sum())
        )

    df = (
        df.dropna(subset='r')
        [['legacy_ba', 'FIPS', 'fracdata', 'r', 'state', 'r_frac', 'state_frac']]
    )

    return df

def write_disagg_data_files(runfiles, inputs_case):
    """
    Write files that will be used for disaggregation.
    """
    # Get the county2zone file for the z134 zone set and append the zones
    # corresponding to this run. The z134 file is needed to calculate
    # state-to-county fractions (since it includes all counties in the CONUS)
    # and legacy BA-to-county fractions (which are needed to disaggregate
    # inputs that are still at the z134 resolution).
    county2zone_with_legacy_bas = (
        reeds.io.get_county2zone(GSw_ZoneSet='z134', as_map=False)
        .rename(columns={'r': 'legacy_ba'})
    )
    county_r_map = reeds.io.get_county2zone(os.path.dirname(inputs_case))
    county2zone_with_legacy_bas['r'] = (
        county2zone_with_legacy_bas['FIPS'].map(county_r_map)
    )
    county2zone_with_legacy_bas['FIPS'] = (
        'p' + county2zone_with_legacy_bas['FIPS']
    )

    filename_filepath_map = runfiles.set_index('filename')['full_filepath']
    for filename in [
        'disagg_geosize.csv',
        'disagg_population.csv',
        'disagg_state_lpf.csv'
    ]:
        if filename == 'disagg_geosize.csv':
            # Calculate county land areas from the county shapefile
            dfcounty = reeds.io.get_countymap(exclude_water_areas=True)
            df = (
                dfcounty.set_index('rb')
                .rename_axis('FIPS')
                .area
                .rename('value')
                .reset_index()
            )
        else:
            # Read the raw data file for the disagg variable (e.g., 
            # county population data for disagg_population.csv)
            filepath = filename_filepath_map[filename]
            df = pd.read_csv(filepath)
    
        # Calculate state/region/BA-to-county fractions for the
        # disagg variable and write to inputs_case
        df = calculate_county_fractions(df, county2zone_with_legacy_bas)
        df.to_csv(os.path.join(inputs_case, filename), index=False)

    return


def write_region_indexed_file(
    df,
    inputs_case,
    source_deflator_map,
    sw,
    region_file_entry
):
    """
    Write a single region-indexed file to the dir_dst directory
    """
    filename = region_file_entry['filename']
    # Get the filetype of the output file from the filename string
    filetype_out = os.path.splitext(filename)[1].strip('.')

    region_col = region_file_entry['region_col']
    fix_cols = region_file_entry['fix_cols'].split(',')

    if region_file_entry['disaggfunc'] != 'ignore':
        df = reeds.spatial.downscale_from_legacy_zone_to_county(
            df=df,
            region_col=region_col,
            fix_cols=fix_cols,
            inputs_case=inputs_case,
            disaggfunc=region_file_entry['disaggfunc']
        )

    if region_file_entry['aggfunc'] != 'ignore':
        df = reeds.spatial.upscale_from_county_to_zone(
            df=df,
            region_col=region_col,
            fix_cols=fix_cols,
            inputs_case=inputs_case,
            aggfunc=region_file_entry['aggfunc']
        )

    #---- Write data to dir_dst (inputs_case) folder ----
    if filetype_out == 'h5':
        reeds.io.write_profile_to_h5(df, filename, inputs_case)
    else:
        # Special cases: These files' values need to be adjusted to copy
        filepath = region_file_entry['filepath']
        match filename:
            case 'bio_supplycurve.csv':
                # Adjust for inflation
                df['price'] = df['price'].astype(float) * source_deflator_map[filepath]
            case 'unitdata_orig.csv':
                # Map counties to zones
                county2zone = reeds.io.get_county2zone(case=os.path.dirname(inputs_case))
                county2zone.index = 'p' + county2zone.index
                df['r'] = df['FIPS'].map(county2zone)
                ## If using offshore zones, map offshore wind units from land to offshore zones
                if int(sw.GSw_OffshoreZones):
                    df = reeds.spatial.assign_to_offshore_zones(df)
                num_units_missing_zones = len(df.loc[df.r.isna()])
                if num_units_missing_zones > 0:
                    raise ValueError(
                        f"{num_units_missing_zones} units were not mapped to any zones."
                    )
            case _:
                pass

        if str(region_file_entry.GAMStype).lower() in ['set', 'parameter']:
            reeds.io.write_to_inputs_h5(
                df,
                key=(
                    Path(region_file_entry.filename).stem
                    if isinstance(region_file_entry.GAMSname, float)
                    else region_file_entry.GAMSname
                ),
                case=reeds.io.standardize_case(inputs_case),
                gamstype=region_file_entry.GAMStype.lower(),
                comment=(
                    region_file_entry.GAMScomment
                    if isinstance(region_file_entry.GAMScomment, str) else ''
                ),
            )
        else:
            df.to_csv(os.path.join(inputs_case, filename), index=False)


def write_region_indexed_files(
    inputs_case,
    sw,
    region_files,
    regions_and_agglevel,
    source_deflator_map
):
    """
    Filter and copy data for files with regions
    """
    print('Copying region-indexed files: filtering for valid regions')
    for _, region_file_entry in region_files.iterrows():
        # If the file is missing and not required,
        # an empty file is written with the given filename.
        if (
            (not region_file_entry['file_exists'])
            and (not region_file_entry['file_is_required'])
        ):
            print(f'...writing empty file {region_file_entry.filename}')
            write_empty_file(os.path.join(inputs_case,region_file_entry['filename']))
        else:
            print(f'...copying {region_file_entry.filename}')
            # Read file and return dataframe filtered for valid regions
            df = subset_to_valid_regions(
                sw,
                region_file_entry,
                regions_and_agglevel,
                inputs_case
            )
            write_region_indexed_file(
                df,
                inputs_case,
                source_deflator_map,
                sw,
                region_file_entry
            )


def write_miscellaneous_files(
    sw,
    inputs_case,
    reeds_path
):
    """
    Handle miscellaneous files.
    Many of these files are not in the non_region_files and region_files set
    (runfiles.csv - from function read_runfiles).
    """
    ### Solver file
    case = Path(inputs_case).parent
    optfile = reeds.io.get_optfile(case)
    shutil.copy(Path(reeds_path, 'reeds', 'solver', optfile), case)

    ### Parsed switches
    pd.DataFrame(
        {'*pvb_type': [f'pvb{i}' for i in sw['GSw_PVB_Types'].split('_')],
        'ilr': [np.around(float(c) / 100, 2) for c in sw['GSw_PVB_ILR'].split('_')
                ][0:len(sw['GSw_PVB_Types'].split('_'))]}
    ).to_csv(os.path.join(inputs_case, 'pvb_ilr.csv'), index=False)

    pd.DataFrame(
        {'*pvb_type': [f'pvb{i}' for i in sw['GSw_PVB_Types'].split('_')],
        'bir': [np.around(float(c) / 100, 2) for c in sw['GSw_PVB_BIR'].split('_')
                ][0:len(sw['GSw_PVB_Types'].split('_'))]}
    ).to_csv(os.path.join(inputs_case, 'pvb_bir.csv'), index=False)

    ### County-to-zone mapping
    county2zone = reeds.io.get_county2zone(case=os.path.dirname(inputs_case))
    county2zone.index = 'p' + county2zone.index

    write_storage_hybrid_case_inputs(sw, inputs_case)

    # Constant value if input is float, otherwise named profile
    # Methane leakage rate:
    # Constant value if input is float, otherwise named profile.
    # Best estimate for fixed leakage rate is from
    # Alvarez et al. 2018 (https://dx.doi.org/10.1126/science.aar7204)
    try:
        rate = float(sw['GSw_MethaneLeakageScen'])
        methane_leakage_rate = pd.Series(
            index=range(int(sw.startyear), int(sw.endyear)+1), data=rate, name='constant'
        ).rename_axis('allt')
    except ValueError:
        methane_leakage_rate = pd.read_csv(
            os.path.join(reeds_path,'inputs','emission_constraints','methane_leakage_rate.csv'),
            index_col='t',
        )[sw['GSw_MethaneLeakageScen']].rename_axis('allt')
    reeds.io.write_to_inputs_h5(
        methane_leakage_rate, 'methane_leakage_rate', inputs_case, 'parameter',
        units='fraction', comment='methane leakage as fraction of gross production',
    )

    # H2 leakage rate:
    h2_leakage_rate = pd.read_csv(
        os.path.join(reeds_path,'inputs','emission_constraints','h2_leakage_rate.csv'),
        index_col='i',
    )[sw['GSw_H2LeakageScen']]
    reeds.io.write_to_inputs_h5(
        h2_leakage_rate, 'h2_leakage_rate', inputs_case, 'parameter', units='fraction',
        comment='H2 leakage rate as a fraction of total production by technology',
    )

    # Transmission employment factors:
    ef_trans = pd.read_csv(
        os.path.join(reeds_path,'inputs','employment','employment_factor_inter_transmission.csv'),
        index_col=0)
    ef_trans[ef_trans.index == sw['GSw_EmploymentFactor']].T.round(8).to_csv(
        os.path.join(inputs_case,'employment_factor_inter_transmission.csv'),header=False)
    
    # Add this_year to years_until_endogenous to generate the tech-specific firstyear parameter
    scalars = reeds.io.get_scalars(full=True)
    firstyear = (
        pd.read_csv(
            # years_until_endogenous created using function write_non_region_files
            os.path.join(inputs_case, 'years_until_endogenous.csv'),
            index_col=0,
        ).squeeze(1)
        + int(scalars.loc['this_year','value'])
    )
    reeds.io.write_to_inputs_h5(
        firstyear, 'firstyear', inputs_case, gamstype='parameter',
        comment='first year where new investment is allowed',
    )

    ### Single column from input table ###

    pd.read_csv(
        os.path.join(reeds_path,'inputs','emission_constraints','ng_crf_penalty.csv'), index_col='t',
    )[sw['GSw_NG_CRF_penalty']].rename_axis('*t').to_csv(
        os.path.join(inputs_case,'ng_crf_penalty.csv')
    )

    gwp = pd.read_csv(
        os.path.join(reeds_path,'inputs','emission_constraints','gwp.csv'),
        index_col='e',
    )
    if sw['GSw_GWP'] in gwp:
        gwp_write = gwp[sw['GSw_GWP']].copy()
    else:
        gwp_ch4, gwp_n2o = [float(i.split('_')[1]) for i in sw['GSw_GWP'].split('/')]
        gwp_write = pd.Series({'CO2':1, 'CH4':gwp_ch4, 'N2O':gwp_n2o})

    gwp_write['H2'] = scalars.loc['h2_gwp','value'].copy()

    reeds.io.write_to_inputs_h5(
        gwp_write, 'gwp', inputs_case, gamstype='parameter',
        comment='--metric ton CO2-equivalents-- global warming potential',
    )

    # Calculate CO2 cap based on GSw_Region chosen (national or sub-national regions)
    # Read in national co2 cap
    co2_cap = (
        pd.read_csv(
            os.path.join(reeds_path, 'inputs', 'emission_constraints', 'co2_cap.csv'),
            index_col='t',
        )
        .loc[sw['GSw_AnnualCapScen']]
        .rename_axis('allt')
        .rename('tonne_per_year')
    )

    # Read in 2022 CO2 emission share by county calculated from 2022 eGrid emission data:
    em_share = pd.read_csv(
        os.path.join(
            reeds_path,'inputs','emission_constraints','county_co2_share_egrid_2022.csv'),
        index_col=0)

    # Merge emission share by county with the counties in GSw_Region and calculate emission share of GSw_Region
    region_em_share = (
        em_share.reindex(county2zone.index)
        .fillna(0)
        ['share']
        .sum()
    )

    # Apply the emission share to national cap to get the emission cap trajectory of GSw_Region
    co2_cap *= region_em_share

    reeds.io.write_to_inputs_h5(
        co2_cap, 'co2_cap', inputs_case, gamstype='parameter',
        comment='--metric tons-- CO2 emissions cap used when Sw_AnnualCap is on',
    )

    # CO2 tax
    co2_tax = pd.read_csv(
        os.path.join(reeds_path,'inputs','emission_constraints','co2_tax.csv'), index_col='t',
    )[sw['GSw_CarbTaxOption']].rename_axis('allt')
    reeds.io.write_to_inputs_h5(
        co2_tax, 'co2_tax', inputs_case, gamstype='parameter',
        comment='--$/metric ton-- CO2 tax used when Sw_CarbTax is on',
    )

    solveyears = reeds.inputs.parse_yearset(sw['yearset'])
    if int(sw['startyear']) not in solveyears:
        solveyears.append(int(sw['startyear']))
        solveyears = sorted(solveyears)
    solveyears = [y for y in solveyears if (y >= int(sw['startyear'])) and (y <= int(sw['endyear']))]
    pd.DataFrame(columns=solveyears).to_csv(
        os.path.join(inputs_case,'modeledyears.csv'), index=False)
    reeds.io.write_to_inputs_h5(
        pd.Series(solveyears, name='allt'), 'tmodel_new', inputs_case, gamstype='set',
        comment='years to run the model',
    )

    t = pd.Series(range(int(sw.startyear), int(sw.endyear)+1), name='allt')
    reeds.io.write_to_inputs_h5(
        pd.Series(t, name='allt'), 't', inputs_case, gamstype='set',
        comment='full set of years',
    )

    gen_mandate_trajectory = pd.read_csv(
        os.path.join(reeds_path,'inputs','national_generation','gen_mandate_trajectory.csv'),
        index_col='GSw_GenMandateScen'
    ).loc[sw['GSw_GenMandateScen']].rename_axis('allt')
    reeds.io.write_to_inputs_h5(
        gen_mandate_trajectory, 'national_gen_frac', inputs_case, gamstype='parameter',
        comment='--fraction-- national fraction of load + losses that must be met by RE',
    )

    nat_gen_tech_frac = pd.read_csv(
        os.path.join(reeds_path,'inputs','national_generation','nat_gen_tech_frac.csv'),
        index_col='*i',
    )[sw['GSw_GenMandateList']].rename_axis('i')
    reeds.io.write_to_inputs_h5(
        nat_gen_tech_frac, 'nat_gen_tech_frac', inputs_case, gamstype='parameter',
        comment='--fraction-- fraction of each tech generation that may be counted toward eq_national_gen',
    )

    pd.read_csv(
        os.path.join(reeds_path,'inputs','climate','climate_heuristics_yearfrac.csv'),
        index_col='*t',
    )[sw['GSw_ClimateHeuristics']].round(3).to_csv(
        os.path.join(inputs_case,'climate_heuristics_yearfrac.csv')
    )

    pd.read_csv(
        os.path.join(reeds_path,'inputs','climate','climate_heuristics_finalyear.csv'),
        index_col='*parameter',
    )[sw['GSw_ClimateHeuristics']].round(3).to_csv(
        os.path.join(inputs_case,'climate_heuristics_finalyear.csv')
    )

    pd.read_csv(
        os.path.join(reeds_path,'inputs','upgrades','upgrade_costs_ccs_coal.csv'),
        index_col='t',
    )[sw['ccs_upgrade_cost_case']].round(3).rename_axis('*t').to_csv(
        os.path.join(inputs_case,'upgrade_costs_ccs_coal.csv')
    )

    pd.read_csv(
        os.path.join(reeds_path,'inputs','upgrades','upgrade_costs_ccs_gas.csv'),
        index_col='t',
    )[sw['ccs_upgrade_cost_case']].round(3).rename_axis('*t').to_csv(
        os.path.join(inputs_case,'upgrade_costs_ccs_gas.csv')
    )

    ccseason_dates = pd.read_csv(
        os.path.join(reeds_path, 'inputs', 'reserves', 'ccseason_dates.csv'),
        index_col=['month', 'day'],
    )[sw['GSw_PRM_CapCreditSeasons']].rename('ccseason')
    ccseason_dates.to_csv(os.path.join(inputs_case, 'ccseason_dates.csv'))
    reeds.io.write_to_inputs_h5(
        df=ccseason_dates.drop_duplicates().rename().reset_index(drop=True),
        key='ccseason',
        case=inputs_case,
        gamstype='set',
        comment='seasons used for capacity credit',
    )

    prm_profiles = pd.read_csv(
        os.path.join(reeds_path,'inputs','reserves','prm_annual.csv'),
    ).rename(columns={'*nercr':'nercr'}).set_index(['nercr','t'])
    if sw['GSw_PRM_scenario'] in prm_profiles:
        prm = prm_profiles[sw['GSw_PRM_scenario']]
    else:
        prm = pd.Series(index=prm_profiles.index, data=float(sw['GSw_PRM_scenario']))

    ## Broadcast PRM from nercr to r and backfill missing years
    hierarchy = reeds.io.get_hierarchy(reeds.io.standardize_case(inputs_case))
    prm_initial = (
        prm
        .unstack('nercr')
        .reindex(solveyears)
        .bfill().ffill()
        [hierarchy['nercr']]
    )
    prm_initial.columns = hierarchy.index.rename('*r')
    prm_initial = prm_initial.stack('*r').reorder_levels(['*r','t']).round(4).rename('fraction')
    prm_initial.to_csv(os.path.join(inputs_case, 'prm_initial.csv'))
    for t in solveyears:
        stresspath = os.path.join(inputs_case, f'stress{t}i0')
        os.makedirs(stresspath, exist_ok=True)
        prm_initial.xs(t, 0, 't').to_csv(os.path.join(stresspath, 'prm.csv'))

    # Add capacity deployment limits based on interconnection queue data
    cap_queue = pd.read_csv(
        os.path.join(reeds_path,'inputs','capacity_exogenous','interconnection_queues.csv'))
    # Map counties to zones
    cap_queue['r'] = cap_queue['r'].map(county2zone)
    cap_queue = cap_queue.dropna(subset='r')

    cap_queue = cap_queue.groupby(['tg','r'],as_index=False).sum()
    cap_queue.to_csv(os.path.join(inputs_case,'cap_limit.csv'), index=False)
    # ----  Miscelanous files in non_region_files or region_files (in this case we are overwriting them)
    # Expand i (technologies) set if modeling water use. Overwrite originals.
    if int(sw['GSw_WaterMain']):
        techs = pd.concat([
            reeds.io.read_input(inputs_case, 'i').squeeze(1),
            pd.read_csv(
                os.path.join(inputs_case,'i_coolingtech_watersource.csv'),
                comment='*', header=None).squeeze(1),
            pd.read_csv(
                os.path.join(inputs_case,'i_coolingtech_watersource_upgrades.csv'),
                comment='*', header=None).squeeze(1),
        ])
        reeds.io.write_to_inputs_h5(
            techs, 'i', inputs_case, gamstype='set', comment='generation technologies',
            overwrite=True,
        )

    ## Unit sizes for ReEDS2PRAS
    fpath_out = os.path.join(inputs_case, 'unitsize.csv')
    if sw['pras_unitsize_source'] == 'atb':
        shutil.copy(
            os.path.join(reeds_path, 'inputs', 'plant_characteristics', 'unitsize_atb.csv'),
            fpath_out,
        )
    elif sw['pras_unitsize_source'] == 'r2x':
        fpath_in = os.path.join(reeds_path, 'inputs', 'plant_characteristics', 'pcm_defaults.json')
        with open(fpath_in) as f:
            pcm_defaults = json.load(f)
        unitsize = pd.Series(
            index=pcm_defaults.keys(),
            data=[pcm_defaults[tech]['avg_capacity_MW'] for tech in pcm_defaults.keys()],
            name='MW',
        ).rename_axis('tech').dropna().astype(int)
        unitsize.to_csv(fpath_out)

    # Rewrite report_params as GAMS-readable definitions
    param_csv_to_txt(
        infilepath=Path(reeds_path, 'reeds', 'core', 'terminus', 'report_params.csv'),
        outdirpath=Path(inputs_case, '..', 'autocode'),
    )


def generate_maps_gpkg(inputs_case):
    """
    Write maps.gpkg to speed up map visualization in postprocessing.
    If using region dis/aggregation, maps.gpkg is overwritten in aggregation_regions.py.
    """
    mapsfile = os.path.join(inputs_case, 'maps.gpkg')
    if os.path.exists(mapsfile):
        os.remove(mapsfile)

    dfmap = reeds.io.get_dfmap(os.path.abspath(os.path.join(inputs_case,'..')))
    for level in dfmap:
        dfmap[level].to_file(mapsfile, layer=level)


def propagate_storage_hybrid_tech_rows(sw, inputs_case):
    """Duplicate generator-tech rows for Storage-Hybrid technologies."""
    configs = build_storage_hybrid_configs(sw, inputs_case)
    if not configs:
        return

    # Prescribed-capacity files may reference storage-hybrid configs by their
    # legacy config label (e.g. 'storage-hybrid1'); rewrite those to the
    # per-case wrapper tech names now that the copied file is in inputs_case
    demo_plants_path = os.path.join(inputs_case, 'demonstration_plants.csv')
    if os.path.isfile(demo_plants_path):
        df_demo = pd.read_csv(demo_plants_path)
        df_demo = translate_legacy_storage_hybrid_labels(
            df_demo, sw, inputs_case, 'demonstration_plants.csv'
        )
        df_demo.to_csv(demo_plants_path, index=False)

    skip_dirs = ['capacity_exogenous', 'demonstration_files']
    # incentives.csv and reg_cap_cost_diff.csv are never cloned: their wrapper
    # values are inherited deterministically from the component techs in GAMS
    # (tc_phaseout_mult_t in d1_financials.gms; reg_cap_cost_diff in
    # b_inputs.gms). Cloning them here matched group-labeled rows/columns
    # (e.g. NUCLEAR, TES|CSP) nondeterministically -- "Nuclear" happened to
    # match its group label while "Nuclear-SMR" matched nothing.
    # NOTE on emitrate.csv: deliberately NOT skipped. Wrappers inherit the gen
    # tech's upstream-fuel emission rates (CH4/N2O for nuclear) by cloning, which
    # gives standalone-generator parity under CO2e accounting (Sw_AnnualCap=2).
    # There is no GAMS-side emit-rate inheritance, so removing the cloned rows
    # would silently zero wrapper upstream emissions.
    # All entries are basenames: runfiles flattens run-copies to the inputs_case
    # root, so dir-qualified paths (e.g. 'financials/cap_penalty.csv') never
    # matched the copies that matter. The match below checks both fname and rel.
    skip_files = {
        'cap_penalty.csv',
        'gbin_min.csv',
        'unitdata.csv',
        # source for process_unitdata.py; cloning wrapper rows here would create
        # phantom existing units for the wrappers
        'unitdata_orig.csv',
        'tg.csv',
        'tech-subset-table.csv',
        'incentives.csv',
        'reg_cap_cost_diff.csv',
        # the wide, group-labeled source copied into inputs_case by runfiles;
        # calc_financial_inputs.py stacks it into reg_cap_cost_diff.csv
        'regional_cap_cost_diff.csv',
        # parent-link files: the tech-name column ('ii') holds the numeraire
        # PARENT of each cooling variant, not a tech row to clone. Cloning
        # substituted wrapper names into the parent column, which under
        # GSw_WaterMain=1 made wrappers numeraires (valcap removed) and
        # multi-counted every ctt_i_ii parameter sum for standalone variants.
        'i_coolingtech_watersource_link.csv',
        'i_coolingtech_watersource_upgrades_link.csv',
        # upgrade machinery: wrappers are new-vintage composite techs and are
        # never upgradable (no hintage data), so cloning gen-tech rows here
        # made wrappers upgrade sources/targets and crashed the CCS-retrofit
        # upgrade_derate heat-rate division in b_inputs.gms
        'upgrade_link.csv',
        'upgradelink_water.csv',
        'ccs_link.csv',
        'ccs_link_water.csv',
        'i_coolingtech_watersource_upgrades.csv',
        'plantchar_upgrades.csv',
    }

    financials_dir = os.path.join(inputs_case, 'financials')
    if os.path.isdir(financials_dir):
        for fname in os.listdir(financials_dir):
            fname_lower = fname.lower()
            if fname_lower.endswith('.csv') and (
                fname_lower.startswith('incentives_')
                or fname_lower.startswith('reg_cap_cost_diff_')
            ):
                skip_files.add(fname_lower)

    tech_canon_map = _load_storage_hybrid_tech_canon_map(inputs_case)
    # For each Storage-Hybrid config, list (source_techs, wrapper) where
    # source_techs is a precedence-ordered list of techs to try when cloning
    # rows into the wrapper. The paired storage tech is tried first by default;
    # the gen tech is the fallback. Only the first matching source is used per
    # file/column, so no row is ever cloned twice for the same wrapper.
    tech_map = [
        (
            [config['storage_tech'], config['gen_tech']],
            config['storage_hybrid_tech'],
        )
        for config in configs
    ]

    # Outage/unit-characteristic files take GEN-FIRST precedence: the wrapper is
    # modeled as one unit whose storage side shares the generator's forced/scheduled
    # outage behavior (in the LP, d1_temporal_params.gms re-inherits avail from the
    # gen tech; in PRAS the wrapper GeneratorStorage uses these rows directly).
    gen_first_files = {
        'outage_forced_static.csv',
        'outage_scheduled_static.csv',
        'mttr.csv',
        'unitsize.csv',
        'unitsize_atb.csv',
    }

    def _first_noncomment_line(path):
        with open(path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    return stripped
        return None

    tech_canon_set = set(tech_canon_map.keys())

    def _looks_like_tech_label(value):
        text = str(value).strip()
        canon = _storage_hybrid_canon_label(text)
        if canon in tech_canon_set:
            return True
        if '*' in text:
            return any(_storage_hybrid_canon_label(part) in tech_canon_set for part in text.split('*'))
        return False

    def _line_has_header(header_line):
        try:
            first_col = header_line.split(',')[0].strip()
        except Exception:
            return True
        if first_col.lower() in {'i', '*i', 'tech', 'technology'}:
            return True
        return not _looks_like_tech_label(first_col)

    def _read_csv_loose(path, has_header):
        return pd.read_csv(
            path,
            header=0 if has_header else None,
            comment='#',
            dtype=str,
            keep_default_na=False,
            encoding='utf-8-sig',
        )

    def _looks_like_tech_column(series, min_nonempty=5, min_match_frac=0.6):
        values = series.astype(str).str.strip()
        values = values[values != '']
        if len(values) < min_nonempty or not tech_canon_set:
            return False
        canon = (
            values.str.lower()
            .str.replace('_', '-', regex=False)
            .str.replace(' ', '', regex=False)
        )
        return float(canon.isin(tech_canon_set).mean()) >= min_match_frac

    def _normalize_headers(df, header_line):
        try:
            raw_cols = [c.strip() for c in header_line.split(',')]
        except Exception:
            return df
        if len(raw_cols) != len(df.columns):
            return df
        new_cols = list(df.columns)
        for idx, (raw, col) in enumerate(zip(raw_cols, df.columns)):
            if raw == '' and str(col).startswith('Unnamed:'):
                new_cols[idx] = ''
        if new_cols != list(df.columns):
            df = df.copy()
            df.columns = new_cols
        return df

    def _file_contains_storage_hybrid(path):
        try:
            with open(path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                for chunk in iter(lambda: f.read(65536), ''):
                    lower = chunk.lower()
                    if ('storage-hybrid' in lower) or ('storage_hybrid' in lower):
                        return True
        except Exception:
            return True
        return False

    n_files_modified = 0
    for root, _dirs, files in os.walk(inputs_case):
        for fname in files:
            if not fname.lower().endswith('.csv'):
                continue
            if fname.lower().startswith('plantchar_') or fname.lower() == 'plantcharout.csv':
                continue
            if ('storage-hybrid' in fname.lower()) or ('storage_hybrid' in fname.lower()):
                continue

            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, inputs_case).replace('\\', '/').lstrip('./')
            if fname.lower() in skip_files or rel.lower() in skip_files:
                continue
            if any(rel == d or rel.startswith(d + '/') for d in skip_dirs):
                continue
            if _file_contains_storage_hybrid(fpath):
                continue

            header_line = _first_noncomment_line(fpath)
            if not header_line:
                continue

            has_header = _line_has_header(header_line)

            try:
                df = _read_csv_loose(fpath, has_header)
            except Exception:
                continue

            if has_header:
                df = _normalize_headers(df, header_line)
            tech_id_cols = [
                col for col in df.columns
                if (str(col).strip().lower() in {'i', '*i'})
                or _looks_like_tech_column(df[col])
            ]

            changed = False
            gen_first = fname.lower() in gen_first_files
            for source_techs, stor_i in tech_map:
                if gen_first:
                    source_techs = list(reversed(source_techs))
                stor_canon = _storage_hybrid_canon_label(stor_i)

                # Column-name propagation: if any source tech appears as a
                # column header, clone that column under the wrapper name.
                # First match wins to avoid duplicate columns.
                col_canons = {_storage_hybrid_canon_label(c): c for c in df.columns}
                if stor_canon not in col_canons:
                    for source_i in source_techs:
                        source_canon = _storage_hybrid_canon_label(source_i)
                        if source_canon in col_canons:
                            base_col = col_canons[source_canon]
                            stor_col = (
                                stor_i.lower()
                                if str(base_col) == str(base_col).lower()
                                else stor_i
                            )
                            df[stor_col] = df[base_col]
                            changed = True
                            break

                # Row propagation: for each tech-identifier column, find rows
                # matching a source tech (first match in precedence order wins)
                # and append clones keyed by the wrapper name.
                for col in tech_id_cols:
                    series_canon = (
                        df[col]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .str.replace('_', '-', regex=False)
                        .str.replace(' ', '', regex=False)
                    )
                    if stor_canon in set(series_canon):
                        continue
                    mask = None
                    for source_i in source_techs:
                        source_canon = _storage_hybrid_canon_label(source_i)
                        candidate_mask = series_canon == source_canon
                        if candidate_mask.any():
                            mask = candidate_mask
                            break
                    if mask is None:
                        continue
                    base_rows = df.loc[mask].copy()
                    example = str(df.loc[mask, col].iloc[0])
                    stor_value = stor_i.lower() if example == example.lower() else stor_i
                    base_rows[col] = stor_value
                    df = pd.concat([df, base_rows], ignore_index=True)
                    changed = True

            if changed:
                df.to_csv(fpath, index=False, header=has_header)
                n_files_modified += 1

    ### Clone tech rows inside inputs_case/inputs.h5 as well: sets/parameters
    ### with a GAMStype in runfiles.csv (e.g. fuel2tech) are written to the h5
    ### store instead of loose CSVs, so the CSV walk above never sees them
    h5path = os.path.join(inputs_case, 'inputs.h5')
    ## 'i' is handled by append_storage_hybrid_techs_to_i
    h5_skip_keys = {'i'}
    if os.path.isfile(h5path):
        import h5py
        with h5py.File(h5path, 'r') as f:
            h5_keys = list(f.keys())
            h5_attrs = {k: dict(f[k].attrs) for k in h5_keys}
        for key in h5_keys:
            if key in h5_skip_keys:
                continue
            try:
                df = reeds.io.read_h5(h5path, key)
            except Exception:
                continue
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            tech_id_cols = [
                col for col in df.columns
                if (str(col).strip().lower().lstrip('*') == 'i')
                or _looks_like_tech_column(df[col].astype(str))
            ]
            if not tech_id_cols:
                continue
            changed = False
            for source_techs, stor_i in tech_map:
                stor_canon = _storage_hybrid_canon_label(stor_i)
                for col in tech_id_cols:
                    series_canon = (
                        df[col]
                        .astype(str)
                        .str.strip()
                        .str.lower()
                        .str.replace('_', '-', regex=False)
                        .str.replace(' ', '', regex=False)
                    )
                    if stor_canon in set(series_canon):
                        continue
                    mask = None
                    for source_i in source_techs:
                        candidate_mask = series_canon == _storage_hybrid_canon_label(source_i)
                        if candidate_mask.any():
                            mask = candidate_mask
                            break
                    if mask is None:
                        continue
                    base_rows = df.loc[mask].copy()
                    example = str(df.loc[mask, col].iloc[0])
                    base_rows[col] = stor_i.lower() if example == example.lower() else stor_i
                    df = pd.concat([df, base_rows], ignore_index=True)
                    changed = True
            if changed:
                gamstype = h5_attrs[key].get('gamstype', 'parameter')
                comment = re.sub(
                    r'\s*\(written by [^)]*\)\s*$', '',
                    str(h5_attrs[key].get('comment', '')),
                )
                reeds.io.write_to_inputs_h5(
                    df, key, inputs_case, gamstype, comment=comment, verbose=0,
                )
                n_files_modified += 1

    if n_files_modified:
        print(f"propagate_storage_hybrid_tech_rows: modified {n_files_modified} file(s)")


#%% ===========================================================================
### --- PROCEDURE ---
### ===========================================================================
def main(reeds_path, inputs_case):
    """
    Run copy_files.py for use in the ReEDS workflow

    Parameters:
    reeds_path : str (Path to the ReEDS directory)
    inputs_case : str (Path to the run/inputs_case directory)

    Returns:
    None (Writes files to the inputs_case directory)
    """
    #%% ===========================================================================
    ### --- Gather dataframes and dictionaries necessary for the script execution ---
    ### ===========================================================================
    # Obtain data necessary to filter and aggregate regions
    regions_and_agglevel = get_regions_and_agglevel(reeds_path, inputs_case)

    #%% ===========================================================================
    ### --- Copying files ---
    ### ===========================================================================

    sw = reeds.io.get_switches(inputs_case)

    runfiles, non_region_files, region_files = read_runfiles(reeds_path, sw)

    # Rewrite the switches tables as GAMS-readable definition
    # (gswitches.csv is first written at runreeds.py)
    scalar_csv_to_txt(os.path.join(inputs_case,'gswitches.csv'))
    
    source_deflator_map = get_source_deflator_map(reeds_path)

    # Copy non-region files
    write_non_region_files(non_region_files, sw, inputs_case, regions_and_agglevel, source_deflator_map)
    
    # Write files used for disaggregation
    write_disagg_data_files(runfiles, inputs_case)

    # Copy region files
    write_region_indexed_files(
        inputs_case,
        sw,
        region_files,
        regions_and_agglevel,
        source_deflator_map
    )

    #%% ===========================================================================
    ### --- Exceptions ---
    ### ===========================================================================
    # Handle miscellaneous files not included in non_region_files, region_files.
    # Needs to run after copy of non-region files
    write_miscellaneous_files(
        sw,
        inputs_case,
        reeds_path
    )

    # Create a maps.gpkg for this run
    reeds.spatial.validate_proj()
    generate_maps_gpkg(inputs_case)

    propagate_storage_hybrid_tech_rows(sw, inputs_case)


#%% Procedure
if __name__ == '__main__' and not hasattr(sys, 'ps1'):
    # ---- Parse arguments ----
    parser = argparse.ArgumentParser(description="Copy files needed for this run")
    parser.add_argument('reeds_path', help='ReEDS directory')
    parser.add_argument('inputs_case', help='output directory')

    args = parser.parse_args()
    reeds_path = args.reeds_path
    inputs_case = args.inputs_case

    # #%% Settings for testing ###
    # reeds_path = reeds.io.reeds_path
    # inputs_case = os.path.join(reeds_path,'runs','v20260722_envM0_Pacific','inputs_case')


    # ---- Set up logger ----
    tic = datetime.datetime.now()
    log = reeds.log.makelog(
        scriptname=__file__,
        logpath=os.path.join(inputs_case,'..','gamslog.txt'),
    )

    print('Starting copy_files.py')
    main(reeds_path, inputs_case)

    reeds.log.toc(tic=tic, year=0, process='input_processing/copy_files.py',
        path=os.path.join(inputs_case,'..'))
    print('Finished copy_files.py')
