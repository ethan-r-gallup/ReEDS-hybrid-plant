import pandas as pd
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import reeds


def check_GSw_LoadSiteReg(sw):
    """
    Ensure the region entries in loadsite_{GSw_LoadSiteTrajectory} obey the hierarchy
    level specified by GSw_LoadSiteTrajectory
    """
    hierarchy = reeds.io.get_hierarchy()
    ## Make sure the file exists
    infile = os.path.join(
        reeds.io.reeds_path, 'inputs', 'load', f"loadsite_{sw['GSw_LoadSiteTrajectory']}.csv",
    )
    if not os.path.exists(infile):
        err = (
            f"GSw_LoadSiteTrajectory = {sw['GSw_LoadSiteTrajectory']} but {infile} does not exist"
        )
        print(err)
        raise FileNotFoundError(infile)
    ## Make sure the regions obey the hierarchy level
    level = sw['GSw_LoadSiteTrajectory'].split('_')[0]
    allowed = hierarchy[level].unique()
    df = pd.read_csv(infile, comment='#', index_col=0)
    regions = df.index.unique()
    wrong = [r for r in regions if r not in allowed]
    if len(wrong):
        err = f"{infile} contains [{', '.join(wrong)}] but can only contain [{', '.join(allowed)}]"
        raise ValueError(err)


def check_storage_hybrid(sw):
    """
    Check the GSw_StorageHybrid_* switches when storage-hybrid wrappers are on.
    The GenTechs, StorageTechs, BCR, and GridCharging lists need one value per
    GSw_StorageHybrid_Types entry, or one value for all of them.
    """
    if not int(sw['GSw_StorageHybrid']):
        return
    from reeds.input_processing import copy_files

    if int(sw['GSw_HybridPlant']) not in [2, 3]:
        raise ValueError(
            "GSw_StorageHybrid=1 requires GSw_HybridPlant=2 or 3, because storage-hybrid "
            "wrappers are hybrid plants and GSw_HybridPlant=0 or 1 bans them "
            f"(GSw_HybridPlant={sw['GSw_HybridPlant']})"
        )

    types = [t for t in sw['GSw_StorageHybrid_Types'].split('_') if t]
    if not types:
        raise ValueError("GSw_StorageHybrid=1 but GSw_StorageHybrid_Types is empty")
    bad_types = [t for t in types if not t.isalnum()]
    if bad_types:
        raise ValueError(
            f"GSw_StorageHybrid_Types entries must be letters and digits but got {bad_types}"
        )
    if len(set(types)) != len(types):
        raise ValueError(
            f"GSw_StorageHybrid_Types={sw['GSw_StorageHybrid_Types']} has duplicate entries"
        )
    lists = {
        key: copy_files._storage_hybrid_expand_to_len(
            sw[key].split('_'), len(types), key, sw['GSw_StorageHybrid_Types'])
        for key in [
            'GSw_StorageHybrid_GenTechs', 'GSw_StorageHybrid_StorageTechs',
            'GSw_StorageHybrid_BCR', 'GSw_StorageHybrid_GridCharging',
        ]
    }

    for bcr, gridcharging in zip(
        lists['GSw_StorageHybrid_BCR'], lists['GSw_StorageHybrid_GridCharging']
    ):
        try:
            bcr, gridcharging = float(bcr), float(gridcharging)
        except ValueError:
            raise ValueError(
                "GSw_StorageHybrid_BCR and GSw_StorageHybrid_GridCharging must be numbers "
                f"but are {sw['GSw_StorageHybrid_BCR']} and {sw['GSw_StorageHybrid_GridCharging']}"
            )
        if not bcr > 0:
            raise ValueError(f"GSw_StorageHybrid_BCR entries must be > 0 but one is {bcr}")
        if not 0 <= gridcharging <= bcr:
            raise ValueError(
                "GSw_StorageHybrid_GridCharging entries must be between 0 and the matching "
                f"GSw_StorageHybrid_BCR entry but one is {gridcharging} (BCR={bcr})"
            )
    try:
        costmult = float(sw.get('GSw_StorageHybrid_CostMult', 1))
    except ValueError:
        costmult = None
    if not (costmult is not None and costmult > 0):
        raise ValueError(
            "GSw_StorageHybrid_CostMult must be a number > 0 "
            f"but is {sw['GSw_StorageHybrid_CostMult']}"
        )

    ### Technologies
    canon = copy_files._storage_hybrid_canon_label
    inputs = os.path.join(reeds.io.reeds_path, 'inputs')
    techs = pd.read_csv(os.path.join(inputs, 'sets', 'i.csv'), header=None).squeeze(1).tolist()
    tech_canon = {canon(t) for t in techs}
    subsets = {
        key.lower(): {canon(t) for t in val}
        for key, val in reeds.techs.import_tech_groups(
            os.path.join(inputs, 'tech-subset-table.csv')).items()
    }
    upgrades = {
        canon(t) for t in pd.read_csv(os.path.join(inputs, 'upgrades', 'upgrade_link.csv'))['*TO']
    }
    cooling_variants = {
        canon(t) for t in pd.read_csv(
            os.path.join(inputs, 'waterclimate', 'i_coolingtech_watersource.csv'))['*i']
    }

    gen_members = {}
    for gen_tech in sorted(set(lists['GSw_StorageHybrid_GenTechs'])):
        gen_canon = canon(gen_tech)
        if gen_canon in copy_files.STORAGE_HYBRID_EXPANDABLE_GEN_TECHS:
            members = [
                canon(t) for t in copy_files._storage_hybrid_numbered_family_members(gen_canon, techs)
            ]
        elif gen_canon in tech_canon:
            members = [gen_canon]
        else:
            members = []
        if not members:
            raise ValueError(
                f"GSw_StorageHybrid_GenTechs entry {gen_tech!r} is not in inputs/sets/i.csv "
                "or an expandable family "
                f"({', '.join(sorted(copy_files.STORAGE_HYBRID_EXPANDABLE_GEN_TECHS))})"
            )
        gen_members[gen_tech] = members
        for member in members:
            if (member in upgrades) or (member in cooling_variants):
                problem = 'is an upgrade or cooling-water variant'
            elif (member in subsets['storage']) or (member in subsets['hybrid_plant']):
                problem = 'includes storage'
            elif member in subsets['h2_gen']:
                problem = 'is fueled by hydrogen'
            elif (member in subsets['coal']) or (member in subsets['cofire']):
                problem = (
                    'burns coal; the Clean Air Act coal rules do not cover wrappers yet'
                )
            elif (member in subsets['bio']) or (member in subsets['beccs']):
                problem = (
                    'burns biomass; the biomass supply curve and carbon-removal '
                    'limits do not cover wrappers yet'
                )
            elif (member in subsets['ccs']) or (member in subsets['ccsflex']):
                problem = (
                    'captures CO2; the 45Q credit, CO2 transport and storage, and '
                    'capture accounting do not cover wrappers yet'
                )
            elif (member in subsets['hydro']) or (member in subsets['vre_distributed']):
                problem = (
                    'is hydropower or distributed PV, whose generation profiles '
                    'wrappers do not inherit'
                )
            elif member not in subsets['gentech']:
                problem = 'is not a generation technology (GENTECH)'
            else:
                continue
            raise ValueError(f"GSw_StorageHybrid_GenTechs entry {gen_tech!r} {problem}")

    for storage_tech in sorted(set(lists['GSw_StorageHybrid_StorageTechs'])):
        storage_canon = canon(storage_tech)
        if (
            (storage_canon not in tech_canon)
            or (storage_canon not in subsets['storage'])
            or any(storage_canon in subsets[s] for s in ['hybrid_plant', 'demand_flex', 'rsc'])
        ):
            raise ValueError(
                f"GSw_StorageHybrid_StorageTechs entry {storage_tech!r} must be a storage "
                "technology in inputs/sets/i.csv (STORAGE) without its own supply curve, "
                "such as battery-li, tes-ms, or flex-geo"
            )

    ### Pairings
    ## TES wrappers charge from their plant's heat at near-100% efficiency, so the gen
    ## tech must be thermal. Flex-geo stores energy in a geothermal reservoir.
    for gen_tech, storage_tech in zip(
        lists['GSw_StorageHybrid_GenTechs'], lists['GSw_StorageHybrid_StorageTechs']
    ):
        storage_canon = canon(storage_tech)
        members = gen_members[gen_tech]
        if (storage_canon in subsets['tes']) and any(m in subsets['vre'] for m in members):
            raise ValueError(
                f"GSw_StorageHybrid_StorageTechs entry {storage_tech!r} is thermal storage, "
                f"which cannot pair with the VRE gen tech {gen_tech!r}"
            )
        if (storage_canon in subsets['geo_storage']) and not all(
            m in subsets['geo'] for m in members
        ):
            raise ValueError(
                f"GSw_StorageHybrid_StorageTechs entry {storage_tech!r} is geothermal "
                f"reservoir storage, which needs a geothermal gen tech, not {gen_tech!r}"
            )


def check_switches(sw):
    """Run all the checks"""
    check_GSw_LoadSiteReg(sw)
    check_storage_hybrid(sw)
