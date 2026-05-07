"""
One-shot refactor: rename `nuclear_stor` -> `storage_hybrid` across the codebase
and rename the existing `storage_hybrid` (parent superset of all hybrids) ->
`hybrid_plant`.

NOT IDEMPOTENT. Aborts if any sentinel of the post-state is detected.

Run from repo root:  python scripts/refactor_storage_hybrid.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- replacement passes ---
# Use sentinel tokens so the swap (storage_hybrid <-> nuclear_stor naming) is safe
# in a single sequential pass: rename old `storage_hybrid` -> sentinel,
# rename `nuclear_stor` -> `storage_hybrid`, then sentinel -> `hybrid_plant`.

SENT_LOWER = '__SENT_HYBRID_PLANT__'
SENT_UPPER = '__SENT_HYBRID_PLANT_UPPER__'

# Stage 1: rename existing parent superset to sentinel
STAGE1 = [
    ("'storage_hybrid'", f"'{SENT_LOWER}'"),
    ('"storage_hybrid"', f'"{SENT_LOWER}"'),
    ('STORAGE_HYBRID', SENT_UPPER),
    ('storage_hybrid', SENT_LOWER),
]

# Stage 2: compound names containing `nuclear_stor` as fragment, BEFORE generic rename
STAGE2 = [
    ('minnuclear_storduration',           'min_storage_hybrid_duration'),
    ('minnuclear_stor',                   'min_storage_hybrid'),

    ('turbine_generator_cost_nuc_stor',   'turbine_generator_cost_storage_hybrid'),
    ('electrical_cost_nuc_stor',          'electrical_cost_storage_hybrid'),
    ('nuc_stor_cost_nuc',                 'storage_hybrid_cost_p'),
    ('nuc_stor_cost_stor',                'storage_hybrid_cost_s'),

    ('nuclearstorcapcostmult',            'storagehybridcapcostmult'),

    ('cost_cap_nuclear_stor_p',           'cost_cap_storage_hybrid_p'),
    ('cost_cap_nuclear_stor_s',           'cost_cap_storage_hybrid_s'),
    ('cost_vom_nuclear_stor_s',           'cost_vom_storage_hybrid_s'),
    ('cost_fom_nuclear_stor_p',           'cost_fom_storage_hybrid_p'),
    ('cost_fom_nuclear_stor_s',           'cost_fom_storage_hybrid_s'),
    ('cost_cap_fin_mult_nuclear_stor_p',  'cost_cap_fin_mult_storage_hybrid_p'),
    ('cost_cap_fin_mult_nuclear_stor_s',  'cost_cap_fin_mult_storage_hybrid_s'),
    ('storage_eff_nuclear_stor_p',        'storage_eff_storage_hybrid_p'),
    ('storage_eff_nuclear_stor_g',        'storage_eff_storage_hybrid_g'),
    ('bcr_nuclear_stor_config',           'bcr_storage_hybrid_config'),
    ('gridcharge_nuclear_stor_config',    'gridcharge_storage_hybrid_config'),
    ('ramprate_nuclear_stor',             'ramprate_storage_hybrid'),
    ('nuclear_stor_with_tes',             'storage_hybrid_with_tes'),
    ('nuclear_stor_stortech',             'storage_hybrid_stortech'),
    ('nuclear_stor_gentech',              'storage_hybrid_gentech'),
    ('nuclear_stor_config',               'storage_hybrid_config'),
    ('nuclear_stor_storagetechs',         'storage_hybrid_storagetechs'),
    ('nuclear_stor_gentechs',             'storage_hybrid_gentechs'),
    ('nuclear_stor_bcr',                  'storage_hybrid_bcr'),
    ('nuclear_stor_gridcharging',         'storage_hybrid_gridcharging'),

    ('propagate_nuclearstor_tech_rows',   'propagate_storage_hybrid_tech_rows'),
    ('append_nuclear_stor_parameters',    'append_storage_hybrid_parameters'),
    ('_nuclearstor_gen_tech_to_i_name',   '_storage_hybrid_gen_tech_to_i_name'),
]

# Stage 3: switches
STAGE3 = [
    ('GSw_NuclearStor_StorageTechs',  'GSw_StorageHybrid_StorageTechs'),
    ('GSw_NuclearStor_GridCharging',  'GSw_StorageHybrid_GridCharging'),
    ('GSw_NuclearStor_GenTechs',      'GSw_StorageHybrid_GenTechs'),
    ('GSw_NuclearStor_Types',         'GSw_StorageHybrid_Types'),
    ('GSw_NuclearStor_BCR',           'GSw_StorageHybrid_BCR'),
    ('GSw_NuclearStor',               'GSw_StorageHybrid'),
    ('Sw_NuclearStor',                'Sw_StorageHybrid'),
    ('NuclearStor',                   'StorageHybrid'),
]

# Stage 4: tech IDs / case variants (number-suffixed first)
STAGE4 = [
    *[(f'Nuclear-Stor{n}', f'Storage-Hybrid{n}') for n in range(1, 9)],
    *[(f'NUCLEAR-STOR{n}', f'STORAGE-HYBRID{n}') for n in range(1, 9)],
    *[(f'nuclear-stor{n}', f'storage-hybrid{n}') for n in range(1, 9)],
    ('Nuclear-Stor',  'Storage-Hybrid'),
    ('NUCLEAR-STOR',  'STORAGE-HYBRID'),
    ('nuclear-stor',  'storage-hybrid'),
    ('nuclearstor',   'storagehybrid'),
]

# Stage 5: catchall
STAGE5 = [
    ('nuclear_stor', 'storage_hybrid'),
]

# Stage 6: resolve sentinels -> hybrid_plant
STAGE6 = [
    (f"'{SENT_LOWER}'", "'hybrid_plant'"),
    (f'"{SENT_LOWER}"', '"hybrid_plant"'),
    (SENT_UPPER, 'HYBRID_PLANT'),
    (SENT_LOWER, 'hybrid_plant'),
]

ALL_STAGES = STAGE1 + STAGE2 + STAGE3 + STAGE4 + STAGE5 + STAGE6

# --- file walking ---

INCLUDE_EXTS = {'.gms', '.py', '.csv', '.opt', '.op2', '.yml', '.yaml', '.md', '.toml', '.jl', '.sh'}

EXCLUDE_DIR_PARTS = {
    '.git', 'runs', 'node_modules', '__pycache__', '.venv', 'venv',
}


def should_skip(rel_path: Path) -> bool:
    parts = rel_path.parts
    rel_str = '/'.join(parts)
    for ex in EXCLUDE_DIR_PARTS:
        if ex in rel_str:
            return True
    if rel_path.suffix.lower() not in INCLUDE_EXTS:
        return True
    if str(rel_path).replace('\\', '/') == 'scripts/refactor_storage_hybrid.py':
        return True
    return False


def apply_replacements(text: str, pairs):
    n = 0
    for old, new in pairs:
        if old in text:
            n += text.count(old)
            text = text.replace(old, new)
    return text, n


def main() -> int:
    # Idempotency guard: if `hybrid_plant(i)` (the post-state set declaration)
    # appears anywhere in b_inputs.gms, the rename has already been applied.
    b_inputs = REPO_ROOT / 'b_inputs.gms'
    if b_inputs.exists() and 'hybrid_plant(i)' in b_inputs.read_text(encoding='utf-8'):
        print('ABORT: b_inputs.gms already contains hybrid_plant(i); rename appears to have been applied.')
        return 1

    edited = 0
    total_subs = 0
    for path in REPO_ROOT.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT)
        if should_skip(rel):
            continue
        try:
            original = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        new_text, n = apply_replacements(original, ALL_STAGES)
        if n > 0:
            path.write_text(new_text, encoding='utf-8')
            edited += 1
            total_subs += n
            print(f'  {rel}: {n} substitutions')

    rename_map = [
        ('inputs/sets/nuclear_stor_config.csv', 'inputs/sets/storage_hybrid_config.csv'),
    ]
    for src_rel, dst_rel in rename_map:
        src = REPO_ROOT / src_rel
        dst = REPO_ROOT / dst_rel
        if src.exists():
            src.rename(dst)
            print(f'  RENAMED: {src_rel} -> {dst_rel}')

    print(f'\nDone. Edited {edited} files; {total_subs} total substitutions.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
