"""
Endogenous nuclear learning — between-years engine.

Runs once per solve year (scheduled by runbatch.setup_sequential, immediately
after tc_phaseout.py and before the GAMS solve), mirroring the tc_phaseout.py
pattern: read a small per-year gdx written by the previous solve year, compute
updated inputs, and write a gdx that d_solveoneyear.gms re-reads before the
d1_financials.gms include.

It ports the deterministic learning engine from
`mc_nuclear_smr_learning.ipynb` (Abou-Jaoude eq. 12 market-split OCC learning
with the CES generalization, plus INL series-reduction construction durations),
made ENDOGENOUS: US deployment N^US(t) is the cumulative post-anchor nuclear
investment ReEDS has chosen through the previous solve year. Each ReEDS case is
one deterministic "world" defined by the GSw_NuclearLearning_* switches.

Applies to `nuclear` (large) and `nuclear-smr`, and — via the storage-hybrid
cost recomposition in d_solveoneyear.gms — to storage-hybrid wrappers whose
generation tech is nuclear/nuclear-smr.

Usage:
    python nuclear_learning.py <cur_year> <casedir>   # between-years engine (called by runbatch)
    python nuclear_learning.py check <casedir>        # post-run verification of a finished case:
        (1) diagnostics experience == the GAMS INV dump it was derived from,
        (2) the cost_cap/ccmult values GAMS actually applied == the engine's learned values,
        (3) the storage-hybrid gen-side cost == the learned base-tech OCC,
        (4) occ_factor matches the analytic formula given N, and is non-increasing
            while experience is non-decreasing.

See cases.csv for the switch definitions.
"""
#%% ===========================================================================
### --- IMPORTS ---
### ===========================================================================
import os
import math
import argparse
import gdxpds  # noqa: E402  (import before pandas per gdxpds guidance)
import numpy as np
import pandas as pd
import reeds

# GAMS i-name (lower-case) -> internal parent key used for switch lookups.
BASE_TECHS = {'nuclear': 'large', 'nuclear-smr': 'smr'}
# ReEDS default construction schedule column and duration (months) per parent.
CANONICAL_SCH = {'large': '6', 'smr': '3B'}
N_BOAK_UNITS = 2.0        # per-vendor units at the anchor (BOAK = 2OAK convention)
CES_EPS = 1e-8


#%% ===========================================================================
### --- SMALL READERS ---
### ===========================================================================
def _canon(name):
    return str(name).strip().lower()


def get_modeled_years(case):
    return pd.read_csv(
        os.path.join(case, 'inputs_case', 'modeledyears.csv')
    ).columns.astype(int).values


def read_atb_boak(case, anchor_year):
    """BOAK anchor OCC (2004$/MW) per parent, from the pristine ATB plantcharout."""
    df = pd.read_csv(os.path.join(case, 'inputs_case', 'plantcharout.csv'))
    df.columns = [c.lstrip('*') for c in df.columns]
    df['ilow'] = df['i'].map(_canon)
    df = df[(df['variable'] == 'capcost') & (df['t'].astype(int) == int(anchor_year))]
    boak = {}
    for itech, parent in BASE_TECHS.items():
        hit = df[df['ilow'] == itech]
        if len(hit):
            boak[parent] = float(hit['value'].iloc[0])
    return boak


def read_interest_base(case, year):
    """Nominal construction interest as the (1+i) gross multiplier for `year`."""
    fs = pd.read_csv(os.path.join(case, 'inputs_case', 'financials_sys.csv'))
    fs['t'] = fs['t'].astype(int)
    row = fs.loc[fs['t'] == int(year)]
    if not len(row):
        # nearest year: idxmin returns an index LABEL, so select with .loc on it
        row = fs.loc[[fs['t'].sub(int(year)).abs().idxmin()]]
    return float(row['interest_rate_nom'].iloc[0])


def read_canonical_schedules(case):
    """Return {parent: nonzero spend-fraction array} from construction_schedules.csv."""
    cs = pd.read_csv(os.path.join(case, 'inputs_case', 'construction_schedules.csv'))
    out = {}
    for parent, col in CANONICAL_SCH.items():
        frac = pd.to_numeric(cs[col], errors='coerce').fillna(0.0).to_numpy()
        frac = frac[frac > 0]
        out[parent] = frac if frac.sum() > 0 else np.array([1.0])
    return out


def read_historical_stock(case):
    try:
        hs = pd.read_csv(os.path.join(case, 'inputs_case', 'historical_stock.csv'))
        d = dict(zip(hs['key'], hs['value'].astype(float)))
        return float(d.get('H_US', 0.0)), float(d.get('H_KV', 0.0))
    except FileNotFoundError:
        return 0.0, 0.0


def read_foreign_cum(case):
    """{year: raw cumulative theta-weighted foreign units} or {} if absent."""
    try:
        fx = pd.read_csv(os.path.join(case, 'inputs_case', 'foreign_experience.csv'))
        return dict(zip(fx['t'].astype(int), fx['foreign_units_cum'].astype(float)))
    except FileNotFoundError:
        return {}


def foreign_stock_postanchor(foreign_cum, year, anchor_year):
    """S_KV(year) = max(0, cum(year) - cum(anchor)), interpolating on the year grid."""
    if not foreign_cum:
        return 0.0
    yrs = np.array(sorted(foreign_cum))
    vals = np.array([foreign_cum[y] for y in yrs])
    cum_y = float(np.interp(year, yrs, vals))
    cum_a = float(np.interp(anchor_year, yrs, vals))
    return max(0.0, cum_y - cum_a)


def read_experience_mw(case, tprev, pool_hybrid):
    """Cumulative post-anchor gross investment (MW) per parent, from the tprev dump.

    Reads nuc_inv_by_tech(i) (base nuclear + storage-hybrid nuclear wrappers) and
    aggregates to the large/smr parents, optionally pooling the storage-hybrid
    wrappers' gen-side nameplate investment with standalone nuclear.
    """
    mw = {'large': 0.0, 'smr': 0.0}
    gdx = os.path.join(
        case, 'outputs', 'nuclear_learning_data', f'cumulative_inv_{tprev}.gdx')
    if not os.path.isfile(gdx):
        return mw  # first post-anchor year: no prior builds recorded yet
    df = gdxpds.to_dataframes(gdx).get('nuc_inv_by_tech')
    if df is None or not len(df):
        return mw
    tcol, vcol = df.columns[0], df.columns[-1]
    inv = {_canon(r[tcol]): float(r[vcol]) for _, r in df.iterrows()}

    # storage-hybrid wrapper -> gen tech map
    wrapper_parent = {}
    try:
        gt = pd.read_csv(os.path.join(case, 'inputs_case', 'storage_hybrid_gentechs.csv'))
        gt.columns = [c.lstrip('*') for c in gt.columns]
        for _, r in gt.iterrows():
            parent = BASE_TECHS.get(_canon(r['gen_tech']))
            if parent is not None:
                wrapper_parent[_canon(r['storage-hybrid_type'])] = parent
    except FileNotFoundError:
        pass

    for itech, val in inv.items():
        if itech in BASE_TECHS:
            mw[BASE_TECHS[itech]] += val
        elif pool_hybrid and itech in wrapper_parent:
            mw[wrapper_parent[itech]] += val
    return mw


#%% ===========================================================================
### --- LEARNING ENGINE (ported from mc_nuclear_smr_learning.ipynb) ---
### ===========================================================================
def occ_factor(N, N_other, lr, omega, m, s, c, rho, h_us, h_kv, s_kv):
    """OCC / BOAK multiplier for one deterministic draw (occ_paths_ces port).

    N        : post-anchor cumulative own-tech units
    N_other  : other-tech units entering the cross-firm channel (0 unless CrossTech)
    """
    o0 = N_BOAK_UNITS + c * h_us / m
    a0 = (m - 1.0) * o0 + s * c * h_kv
    o = o0 + N / m
    a = (m - 1.0) * o0 + (m - 1.0) / m * N + s * (c * h_kv + s_kv) + N_other
    b1 = math.log2(1.0 - lr)
    b2 = math.log2(1.0 - omega * lr)
    if abs(rho) < CES_EPS:
        return (o / o0) ** b1 * (a / a0) ** b2
    b = -(b1 + b2)
    w = b1 / (b1 + b2)
    ln_et = math.log(o) + math.log1p((1 - w) * math.expm1(rho * (math.log(a) - math.log(o)))) / rho
    ln_e0 = math.log(o0) + math.log1p((1 - w) * math.expm1(rho * (math.log(a0) - math.log(o0)))) / rho
    return math.exp(-b * (ln_et - ln_e0))


def duration_months(N, m, inl, lam, smr_ratio, smr_floor, reeds_default, mode, is_smr):
    """Learned construction duration (months) at the current per-vendor series.

    Ports the notebook's duration model exactly (mc_nuclear_smr_learning.ipynb):
    a series is one two-unit plant and the NEXT build at zero post-anchor
    experience is series 2 (Vogtle was the vendor's series 1), so
    series = clip(2 + floor(n_own/2), 2, 10) with n_own = N/m. lam interpolates
    the INL Fig. 18 LEVEL curves (optimistic at 0, moderate at 1), so the
    long-run (NOAK) duration depends on lam: 36 months optimistic vs 50 moderate
    for large reactors. SMR = max(large_base * smr_ratio, smr_floor)
    (Abou-Jaoude's 55/82 ratio and 43-month floor by default).

    mode='ratio' instead anchors the zero-experience duration at each tech's
    ReEDS default (no level shift at the anchor year) and applies the
    lam-interpolated INL series-reduction RATIO relative to series 2. The SMR
    floor is not applied in ratio mode (the curve ratio bottoms out at
    curve(10)/curve(2) of the tech's own default).

    Returns (months, series).
    """
    n_own = (N / m) if m > 0 else 0.0
    series = int(np.clip(2 + math.floor(n_own / 2.0), 2, len(inl)))
    mod = inl['moderate'].to_numpy(float)
    opt = inl['optimistic'].to_numpy(float)
    if mode == 'ratio':
        curve = opt + lam * (mod - opt)
        return reeds_default * float(curve[series - 1] / curve[1]), series
    base = float(opt[series - 1] + lam * (mod[series - 1] - opt[series - 1]))
    if is_smr:
        base = max(base * smr_ratio, smr_floor)
    return base, series


def _resample_schedule(frac, n_years):
    """Stretch/compress a spend-fraction profile to `n_years` bins (sum to 1)."""
    frac = np.asarray(frac, float)
    n0 = len(frac)
    if n_years == n0:
        return frac / frac.sum()
    cdf = np.concatenate([[0.0], np.cumsum(frac)])
    xq = np.linspace(0.0, 1.0, n_years + 1)
    cdf_q = np.interp(xq, np.linspace(0.0, 1.0, n0 + 1), cdf)
    new = np.diff(cdf_q)
    return new / new.sum()


def ccmult_from_duration(duration_mo, interest_base, canonical_frac):
    """Construction-financing (IDC) multiplier for a learned duration.

    Reproduces reeds.financials.calc_financial_multipliers' CCmult convention:
    CCmult = 1 + sum_k x[k] * (interest_base**(k+0.5) - 1), where interest_base is
    the (1+i) gross nominal rate and row k sits (k+0.5) years before completion.
    """
    n_years = int(round(duration_mo / 12.0))
    n_years = max(1, min(n_years, 10))  # ReEDS IDC exponent grid covers rows 0..9
    x = _resample_schedule(canonical_frac, n_years)
    exps = np.arange(n_years) + 0.5
    return 1.0 + float(np.sum(x * (interest_base ** exps - 1.0)))


#%% ===========================================================================
### --- VALIDATION (ported item 11 asserts; run every invocation) ---
### ===========================================================================
def self_test(inl):
    omega, m = 1.0 / 3.0, 5.0
    # (a) anchor: zero experience -> factor == 1 (both conventions)
    for c in (0, 1):
        f = occ_factor(0.0, 0.0, 0.08, omega, m, 0.0, c, 0.0, 140.0, 44.0, 0.0)
        assert abs(f - 1.0) < 1e-9, f'anchor check failed (c={c}): {f}'
    # (b) s=0, c=0 -> re-anchored generalized eq. (12): [(1-LR)(1-wLR)]^log2(1+N/2m)
    for N in (4.0, 40.0):
        f = occ_factor(N, 0.0, 0.08, omega, m, 0.0, 0, 0.0, 140.0, 44.0, 0.0)
        analytic = ((1 - 0.08) * (1 - omega * 0.08)) ** math.log2(1 + N / (2 * m))
        assert abs(f - analytic) < 1e-9, f'eq.(12) identity failed: {f} vs {analytic}'
    # (c) autarky (s=0, c=0, no cross-tech): CES sweep is exactly flat across rho
    base = occ_factor(40.0, 0.0, 0.08, omega, m, 0.0, 0, 0.0, 140.0, 44.0, 0.0)
    for rho in (-2.0, -1.0, 0.0, 1.0):
        f = occ_factor(40.0, 0.0, 0.08, omega, m, 0.0, 0, rho, 140.0, 44.0, 0.0)
        assert abs(f - base) < 1e-9, f'autarky flatness failed (rho={rho}): {f} vs {base}'
    # (d) INL curve anchors
    mod = inl['moderate'].to_numpy(float)
    opt = inl['optimistic'].to_numpy(float)
    assert mod[0] == 118 and mod[-1] == 50 and opt[-1] == 36, 'INL anchors wrong'
    assert mod[1] == 88 and opt[1] == 70, 'INL next-build (series 2) anchors wrong'
    assert (np.diff(mod) <= 0).all() and (np.diff(opt) <= 0).all(), 'INL not monotone'
    # (e) notebook worked example (derivation Step 7): m=5, LR=8%, s=0.4, tiny base,
    #     N=20, S_KV=15 -> OCC/BOAK = 0.876 * 0.950 = 0.832
    f = occ_factor(20.0, 0.0, 0.08, omega, m, 0.4, 0, 0.0, 135.0, 84.27, 15.0)
    assert abs(f - 0.83219) < 1e-4, f'worked example failed: {f} vs 0.83219'
    # (f) notebook Step 8 CES extension of the worked example: cost decreasing in rho
    #     when the cross channel grows faster than the own channel
    for rho, expect in ((1.0, 0.8220), (0.0, 0.8322), (-1.0, 0.8374)):
        f = occ_factor(20.0, 0.0, 0.08, omega, m, 0.4, 0, rho, 135.0, 84.27, 15.0)
        assert abs(f - expect) < 1e-3, f'CES worked example failed (rho={rho}): {f} vs {expect}'
    # (g) duration model: next build (series 2) at lam=0.5 = (70+88)/2 = 79 months;
    #     SMR floor binds at NOAK; series advances at 2 own units per vendor
    d, ser = duration_months(0.0, 5.0, inl, 0.5, 55.0 / 82.0, 43.0, 72.0, 'absolute', False)
    assert ser == 2 and abs(d - 79.0) < 1e-9, f'duration next-build failed: {d}, series {ser}'
    d, ser = duration_months(100.0, 5.0, inl, 0.5, 55.0 / 82.0, 43.0, 36.0, 'absolute', True)
    assert ser == 10 and abs(d - 43.0) < 1e-9, f'SMR NOAK floor failed: {d}, series {ser}'
    d, ser = duration_months(0.0, 5.0, inl, 0.5, 55.0 / 82.0, 43.0, 72.0, 'ratio', False)
    assert abs(d - 72.0) < 1e-9, f'ratio-mode anchor failed: {d}'
    # (h) CCmult convention: 72-month '6' schedule at 8% nominal reproduces the
    #     ReEDS-computed value 1.268124 (verified against ccmult.csv)
    ccm = ccmult_from_duration(72.0, 1.08, np.array([0.1, 0.2, 0.2, 0.2, 0.2, 0.1]))
    assert abs(ccm - 1.268124) < 1e-5, f'CCmult regression failed: {ccm}'


#%% ===========================================================================
### --- MAIN ---
### ===========================================================================
def main(cur_year, case):
    cur_year = int(cur_year)
    sw = reeds.io.get_switches(case)

    if int(sw.get('GSw_NuclearLearning', 0)) != 1:
        return

    # --- Scope guards (fail fast; the engine is only valid for sequential runs) ---
    if str(sw.get('timetype', 'seq')) != 'seq':
        raise ValueError(
            'GSw_NuclearLearning is only supported for timetype=seq (the endogenous '
            'between-years mechanism does not apply to intertemporal/window solves).')
    if int(sw.get('GSw_WaterMain', 0)) == 1:
        raise ValueError(
            'GSw_NuclearLearning does not yet support GSw_WaterMain=1 (water-cooled '
            'nuclear cost variants are not handled). Disable one of the two switches.')

    anchor = int(float(sw['GSw_NuclearLearning_AnchorYear']))
    # No OCC learning before the anchor year; d_solveoneyear.gms also skips the load.
    if cur_year < anchor:
        return

    years = get_modeled_years(case)
    tprev = int(years[years < cur_year].max()) if cur_year > years.min() else cur_year

    do_occ = int(sw.get('GSw_NuclearLearning_OCC', 1)) == 1
    do_dur = int(sw.get('GSw_NuclearLearning_Duration', 1)) == 1
    pool_hybrid = int(sw.get('GSw_NuclearLearning_PoolHybrid', 1)) == 1
    cross_tech = int(sw.get('GSw_NuclearLearning_CrossTech', 0)) == 1

    omega = float(sw['GSw_NuclearLearning_Omega'])
    m = float(sw['GSw_NuclearLearning_Vendors'])
    s = float(sw['GSw_NuclearLearning_Spillover'])
    c = int(sw['GSw_NuclearLearning_Convention'])
    rho = float(sw['GSw_NuclearLearning_CES_rho'])
    lam = float(sw['GSw_NuclearLearning_Dur_Lambda'])
    dur_mode = str(sw.get('GSw_NuclearLearning_DurAnchorMode', 'absolute')).strip().lower()

    lr = {'large': float(sw['GSw_NuclearLearning_LR_large']),
          'smr': float(sw['GSw_NuclearLearning_LR_smr'])}
    unit_mw = {'large': float(sw['GSw_NuclearLearning_UnitSize_large']),
               'smr': float(sw['GSw_NuclearLearning_UnitSize_smr'])}
    smr_ratio = float(sw['GSw_NuclearLearning_Dur_SMR_Ratio'])
    smr_floor = float(sw['GSw_NuclearLearning_Dur_SMR_Floor'])
    boak_override = {'large': float(sw['GSw_NuclearLearning_BOAK_large']),
                     'smr': float(sw['GSw_NuclearLearning_BOAK_smr'])}

    # --- Static inputs ---
    inl = pd.read_csv(os.path.join(case, 'inputs_case', 'inl_duration_curves.csv'))
    self_test(inl)
    boak_atb = read_atb_boak(case, anchor)
    h_us, h_kv = read_historical_stock(case)
    foreign_cum = read_foreign_cum(case)
    canonical = read_canonical_schedules(case)
    interest_base = read_interest_base(case, cur_year)
    s_kv = foreign_stock_postanchor(foreign_cum, cur_year, anchor)

    # --- Endogenous experience (cumulative post-anchor investment through tprev) ---
    exp_mw = read_experience_mw(case, tprev, pool_hybrid)
    n_units = {p: exp_mw[p] / unit_mw[p] for p in ('large', 'smr')}

    # --- BOAK anchor (ATB by default; optional override in 2022$/kW -> 2004$/MW) ---
    deflator = None
    boak = {}
    for itech, parent in BASE_TECHS.items():
        if boak_override[parent] > 0:
            if deflator is None:
                dfl = pd.read_csv(os.path.join(case, 'inputs_case', 'deflator.csv'))
                dfl.columns = [x.lstrip('*') for x in dfl.columns]
                deflator = dict(zip(dfl['Dollar.Year'].astype(int), dfl['Deflator'].astype(float)))
            boak[parent] = boak_override[parent] * deflator.get(2022, 1.0) * 1000.0
        else:
            boak[parent] = boak_atb.get(parent, np.nan)
    if do_occ and not all(np.isfinite(v) for v in boak.values()):
        raise ValueError(
            'nuclear_learning: could not resolve a BOAK anchor OCC for '
            f'{ {p: boak[p] for p in boak} }. Provide GSw_NuclearLearning_BOAK_* '
            'overrides or ensure nuclear/nuclear-smr appear in plantcharout.csv.')

    # --- Apply the learning engine per parent ---
    occ_rows, ccmult_rows, factor_rows, diag = [], [], [], []
    for itech, parent in BASE_TECHS.items():
        N = n_units[parent]
        other = 'smr' if parent == 'large' else 'large'
        # CrossTech: the other technology's builds enter this tech's cross-firm
        # channel expressed in THIS tech's unit-equivalents (capacity-consistent:
        # 1 GW of SMRs teaches a large vendor as much as 1 GW of foreign reactors)
        n_other = (exp_mw[other] / unit_mw[parent]) if cross_tech else 0.0

        factor = occ_factor(N, n_other, lr[parent], omega, m, s, c, rho, h_us, h_kv, s_kv)
        learned_occ = boak[parent] * factor

        reeds_default_mo = 12.0 * len(canonical[parent])
        dur_mo, series = duration_months(
            N, m, inl, lam, smr_ratio, smr_floor, reeds_default_mo, dur_mode,
            is_smr=(parent == 'smr'))
        ccm = ccmult_from_duration(dur_mo, interest_base, canonical[parent])

        if do_occ and np.isfinite(learned_occ):
            occ_rows.append({'i': itech, 't': str(cur_year), 'learning_cost_cap': round(learned_occ, 2)})
            # OCC learning ratio (learned/BOAK) for the GSw_NuclearLearning_TESIsland
            # path: d_solveoneyear.gms scales the wrapper's shared TES power-cycle
            # capex by the gen tech's factor so the turbine island learns with the plant
            factor_rows.append({'i': itech, 't': str(cur_year), 'learning_factor': round(factor, 6)})
        if do_dur:
            ccmult_rows.append({'i': itech, 't': str(cur_year), 'learning_ccmult': round(ccm, 6)})
        diag.append({
            'year': cur_year, 'tech': itech, 'parent': parent,
            'experience_mw': round(exp_mw[parent], 1), 'N_units': round(N, 3),
            'N_other_units': round(n_other, 3), 'occ_factor': round(factor, 6),
            'boak_2004usd_per_mw': round(boak[parent], 2),
            'learned_occ_2004usd_per_mw': round(learned_occ, 2),
            'series': series, 'duration_months': round(dur_mo, 2), 'ccmult': round(ccm, 6),
        })

    # --- Write the per-year override gdx (re-read by d_solveoneyear.gms) ---
    outdir = os.path.join(case, 'outputs', 'nuclear_learning_data')
    os.makedirs(outdir, exist_ok=True)
    # Only write non-empty symbols; d_solveoneyear.gms loads learning_cost_cap only
    # under the OCC guard and learning_ccmult only under the Duration guard, so each
    # symbol that a guard loads is guaranteed present.
    data = {}
    if occ_rows:
        data['learning_cost_cap'] = pd.DataFrame(occ_rows)[['i', 't', 'learning_cost_cap']]
        data['learning_factor'] = pd.DataFrame(factor_rows)[['i', 't', 'learning_factor']]
    if ccmult_rows:
        data['learning_ccmult'] = pd.DataFrame(ccmult_rows)[['i', 't', 'learning_ccmult']]
    if data:
        gdxpds.to_gdx(data, os.path.join(outdir, f'nuclear_learning_{cur_year}.gdx'))

    # --- Diagnostics (observability artifact) ---
    pd.DataFrame(diag).to_csv(
        os.path.join(outdir, f'diagnostics_{cur_year}.csv'), index=False)
    if not (exp_mw['large'] + exp_mw['smr']) and cur_year > anchor + 1:
        print('nuclear_learning: WARNING no post-anchor nuclear investment yet; '
              'OCC is pinned at BOAK. (Small single-region runs may barely move the '
              'series index — verify the region is national for magnitude studies.)')
    print(f'nuclear_learning: year {cur_year} '
          f'(experience MW large={exp_mw["large"]:.0f}, smr={exp_mw["smr"]:.0f})')


#%% ===========================================================================
### --- POST-RUN VERIFICATION (`python nuclear_learning.py check <casedir>`) ---
### ===========================================================================
def _read_applied(case, year):
    """GAMS-applied values dumped by d3_data_dump.gms AFTER the year's solve."""
    gdx = os.path.join(case, 'outputs', 'nuclear_learning_data', f'cumulative_inv_{year}.gdx')
    if not os.path.isfile(gdx):
        return None
    dfs = gdxpds.to_dataframes(gdx)
    out = {}
    for sym in ('nuc_cost_cap_applied', 'nuc_ccmult_applied', 'nuc_sh_p_applied',
                'nuc_sh_s_applied'):
        df = dfs.get(sym)
        out[sym] = ({} if df is None or not len(df)
                    else {_canon(r[df.columns[0]]): float(r[df.columns[-1]]) for _, r in df.iterrows()})
    return out


def check(case):
    """Verify a finished learning-enabled run end-to-end. Returns #failures."""
    sw = reeds.io.get_switches(case)
    if int(sw.get('GSw_NuclearLearning', 0)) != 1:
        print('check: GSw_NuclearLearning=0 for this case; nothing to verify.')
        return 0
    do_occ = int(sw.get('GSw_NuclearLearning_OCC', 1)) == 1
    do_dur = int(sw.get('GSw_NuclearLearning_Duration', 1)) == 1
    pool_hybrid = int(sw.get('GSw_NuclearLearning_PoolHybrid', 1)) == 1
    anchor = int(float(sw['GSw_NuclearLearning_AnchorYear']))
    years = get_modeled_years(case)
    outdir = os.path.join(case, 'outputs', 'nuclear_learning_data')

    # wrapper -> gen-tech i-name map, for the storage-hybrid check
    wrapper_gentech = {}
    try:
        gt = pd.read_csv(os.path.join(case, 'inputs_case', 'storage_hybrid_gentechs.csv'))
        gt.columns = [c.lstrip('*') for c in gt.columns]
        for _, r in gt.iterrows():
            if _canon(r['gen_tech']) in BASE_TECHS:
                wrapper_gentech[_canon(r['storage-hybrid_type'])] = _canon(r['gen_tech'])
    except FileNotFoundError:
        pass

    # wrapper -> storage-tech map + frozen (unlearned) storage capcost by year,
    # for the GSw_NuclearLearning_TESIsland check
    tes_island = int(sw.get('GSw_NuclearLearning_TESIsland', 1)) == 1
    wrapper_stortech = {}
    try:
        st = pd.read_csv(os.path.join(case, 'inputs_case', 'storage_hybrid_storagetechs.csv'))
        st.columns = [c.lstrip('*') for c in st.columns]
        wrapper_stortech = {
            _canon(r.iloc[0]): _canon(r.iloc[1]) for _, r in st.iterrows()
        }
    except FileNotFoundError:
        pass
    frozen_capcost = {}
    try:
        pc = pd.read_csv(os.path.join(case, 'inputs_case', 'plantcharout.csv'))
        pc.columns = [c.lstrip('*') for c in pc.columns]
        pc = pc[pc['variable'] == 'capcost']
        frozen_capcost = {
            (_canon(r['i']), int(r['t'])): float(r['value']) for _, r in pc.iterrows()
        }
    except FileNotFoundError:
        pass

    fails, checks, last_factor = 0, 0, {}
    any_experience = False
    for y in [int(y) for y in years if y >= anchor]:
        dpath = os.path.join(outdir, f'diagnostics_{y}.csv')
        if not os.path.isfile(dpath):
            print(f'FAIL {y}: diagnostics_{y}.csv missing (engine did not run?)')
            fails += 1
            continue
        diag = pd.read_csv(dpath).set_index('tech')
        tprev = int(years[years < y].max()) if y > years.min() else y
        exp_mw = read_experience_mw(case, tprev, pool_hybrid)
        applied = _read_applied(case, y)

        for itech, parent in BASE_TECHS.items():
            row = diag.loc[itech]
            # (1) experience path: diagnostics == the INV dump they were derived from
            checks += 1
            if abs(row['experience_mw'] - exp_mw[parent]) > 0.5:
                print(f'FAIL {y} {itech}: diagnostics experience {row["experience_mw"]:.1f} MW '
                      f'!= dump-derived {exp_mw[parent]:.1f} MW')
                fails += 1
            any_experience |= exp_mw[parent] > 0
            # (2) GAMS applied what the engine wrote
            if applied is not None:
                if do_occ:
                    checks += 1
                    got = applied['nuc_cost_cap_applied'].get(itech)
                    if got is None or abs(got - row['learned_occ_2004usd_per_mw']) > 0.05:
                        print(f'FAIL {y} {itech}: GAMS-applied cost_cap {got} != learned '
                              f'{row["learned_occ_2004usd_per_mw"]}')
                        fails += 1
                if do_dur:
                    checks += 1
                    got = applied['nuc_ccmult_applied'].get(itech)
                    if got is None or abs(got - row['ccmult']) > 1e-5:
                        print(f'FAIL {y} {itech}: GAMS-applied ccmult {got} != learned {row["ccmult"]}')
                        fails += 1
            # (3) storage-hybrid gen-side cost tracks the learned base-tech OCC
            if applied is not None and do_occ:
                for wrap, val in applied['nuc_sh_p_applied'].items():
                    if wrapper_gentech.get(wrap) == itech:
                        checks += 1
                        if abs(val - row['learned_occ_2004usd_per_mw']) > 0.05:
                            print(f'FAIL {y} {wrap}: SH gen-side cost {val} != learned '
                                  f'{row["learned_occ_2004usd_per_mw"]} ({itech})')
                            fails += 1
            # (3b) storage-hybrid TES power-cycle cost: frozen storage capcost scaled
            # by the gen tech's occ_factor when GSw_NuclearLearning_TESIsland=1,
            # or exactly frozen when 0
            if applied is not None and do_occ:
                for wrap, val in applied.get('nuc_sh_s_applied', {}).items():
                    if wrapper_gentech.get(wrap) != itech:
                        continue
                    base = frozen_capcost.get((wrapper_stortech.get(wrap), y))
                    if base is None:
                        continue
                    expected = base * row['occ_factor'] if tes_island else base
                    checks += 1
                    # occ_factor is rounded to 6 decimals in diagnostics, so allow
                    # the corresponding absolute slack on a ~1e6 $/MW base
                    if abs(val - expected) > max(0.5, 2e-6 * base):
                        print(f'FAIL {y} {wrap}: SH TES-side cost {val} != expected '
                              f'{expected:.2f} (frozen {base:.2f} x factor '
                              f'{row["occ_factor"] if tes_island else 1.0}, '
                              f'TESIsland={int(tes_island)})')
                        fails += 1
            # (4) occ_factor non-increasing while experience is non-decreasing
            checks += 1
            prev = last_factor.get(itech)
            if prev is not None and row['occ_factor'] > prev + 1e-6:
                print(f'FAIL {y} {itech}: occ_factor rose {prev} -> {row["occ_factor"]}')
                fails += 1
            last_factor[itech] = row['occ_factor']

    # (5) demo prescriptions (if any) must show up as experience.
    # Gate on GSw_NuclearDemo just as writecapdat.py does: the file can exist in
    # inputs_case while the switch is off, in which case the rows never become
    # prescriptions and zero experience is correct.
    demo_path = os.path.join(case, 'inputs_case', 'demonstration_plants.csv')
    if (os.path.isfile(demo_path) and os.path.getsize(demo_path) > 0 and len(years)
            and int(sw.get('GSw_NuclearDemo', 0)) == 1):
        demo = pd.read_csv(demo_path)
        demo.columns = [str(c).strip().lstrip('﻿*') for c in demo.columns]
        # Base-tech demo rows always count; storage-hybrid wrapper demo rows
        # count via their gen tech when hybrid experience pooling is on
        # (otherwise their INV is genuinely not recorded as experience).
        demo_tech = demo['i'].map(_canon)
        is_base = demo_tech.isin(BASE_TECHS)
        is_pooled_wrapper = demo_tech.isin(wrapper_gentech) if pool_hybrid else False
        nuke_demo = demo[is_base | is_pooled_wrapper]
        tprev_final = int(years[years < years.max()].max())
        expected = nuke_demo.loc[
            (nuke_demo['t'] > anchor) & (nuke_demo['t'] <= tprev_final), 'value'].sum()
        got = sum(read_experience_mw(case, tprev_final, pool_hybrid).values())
        checks += 1
        if expected > 0 and got < expected - 0.5:
            print(f'FAIL: prescribed demo builds {expected:.0f} MW through {tprev_final} '
                  f'but only {got:.0f} MW of experience recorded')
            fails += 1

    if not any_experience:
        print('WARNING: no post-anchor nuclear investment in this run — the build-driven '
              'learning path was never exercised (checks 1-4 only verify the no-build state).')
    print(f'check: {checks - fails}/{checks} checks passed'
          + (' — ALL PASS' if fails == 0 else f' — {fails} FAILURES'))
    return fails


#%% ===========================================================================
### --- CLI ---
### ===========================================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Endogenous nuclear learning (between-years)')
    parser.add_argument('cur_year', type=str,
                        help="current solve year, or 'check' to verify a finished run")
    parser.add_argument('case', type=str, help='path to ReEDS run folder')
    args = parser.parse_args()

    if args.cur_year.lower() == 'check':
        raise SystemExit(1 if check(case=args.case) else 0)

    log = reeds.log.makelog(
        scriptname=__file__,
        logpath=os.path.join(args.case, 'gamslog.txt'),
    )
    main(cur_year=int(args.cur_year), case=args.case)
