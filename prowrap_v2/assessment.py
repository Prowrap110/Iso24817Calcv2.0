"""Narrow Modified B31G assessment and explicit external capacity acceptance."""
import math

def b31g_factor_details(case):
    """Owner-selected automatic basis; retain explicit legacy values as overrides."""
    factor = case.get('original_design_factor')
    override = case.get('b31g_safety_factor')
    if factor is not None and (isinstance(factor, bool) or not isinstance(factor, (int, float))
                               or not math.isfinite(factor) or not 0 < factor <= 1):
        raise ValueError('Original pipeline design factor must be greater than zero and no greater than one.')
    if override is not None:
        if (isinstance(override, bool) or not isinstance(override, (int, float))
                or not math.isfinite(override) or override < 1.25):
            raise ValueError('Modified B31G safety factor must be finite and at least 1.25.')
        sf, source = override, 'Manual override'
    else:
        if factor is None:
            raise ValueError('Enter the original pipeline design factor for automatic B31G safety factor, or enter a manual safety factor override.')
        sf, source = max(1.0 / factor, 1.25), 'Automatic from original pipeline design factor'
        if not math.isfinite(sf):
            raise ValueError('Original pipeline design factor is too small for a finite B31G safety factor.')
    return dict(safety_factor=sf, source=source, original_design_factor=factor,
                manual_override=override, minimum_safety_factor=1.25)

def modified_b31g(case,length,remaining):
    D,t,ys,ts=case['od_mm'],case['wall_mm'],case['smys_mpa'],case['smts_mpa']
    if case['mechanism']!='Corrosion' or case['component']!='Straight':raise ValueError('Modified B31G requires straight-pipe metal-loss corrosion.')
    if not case.get('material_grade') or not case.get('design_code') or not case.get('ffs_ref'):raise ValueError('Modified B31G requires material, design-code and applicability assessment references.')
    if not (0<ys<=483 and ts>=ys and case['temperature_c']<120):raise ValueError('Modified B31G material/temperature scope is exceeded.')
    loss=(t-remaining)/t
    if not 0<=loss<=.8:raise ValueError('Modified B31G metal-loss ratio must be within 0–0.80.')
    sf=b31g_factor_details(case)['safety_factor']
    z=length*length/(D*t);m=math.sqrt(1+.6275*z-.003375*z*z) if z<=50 else .032*z+3.3
    flow=min(ys+69,ts);stress=flow*(1-.85*loss)/(1-.85*loss/m)
    return 2*stress*t/(D*sf)

def substrate_capacity(case, groups, eol):
    if case['substrate_route']=='Full laminate':return 0.,None
    if eol<1:raise ValueError('Substrate credit requires end-of-life wall at least 1 mm.')
    if not case.get('qualification_ref') or case.get('qualified_wall_loss_pct') is None:raise ValueError('Substrate credit requires the Annex C qualified wall-loss envelope and reference.')
    if not 0<=case['qualified_wall_loss_pct']<=100 or 100*(case['wall_mm']-eol)/case['wall_mm']>=case['qualified_wall_loss_pct']:raise ValueError('End-of-life loss exceeds the Annex C qualified wall-loss envelope.')
    if case['substrate_route']=='Substrate stress limit' and not case.get('allowable_stress_mpa'):
        raise ValueError('Substrate stress-limit sizing requires the allowable substrate stress.')
    if case['substrate_route']=='Substrate sharing' and case['sharing_basis'] in ('Known allowable stress','Restore original capacity'):
        if not case.get('allowable_stress_mpa') and not case.get('original_design_factor'):
            raise ValueError('This sharing route requires the original allowable stress or location/design factor.')
        if case.get('original_design_factor') is not None and not 0<case['original_design_factor']<=1:
            raise ValueError('Original pipeline design factor must be greater than zero and no greater than one.')
    if case['ffs_method']=='Modified B31G':
        if case.get('smts_mpa') is None:raise ValueError('Modified B31G requires SMTS.')
        ps=min(modified_b31g(case,g['length_mm'],g['eol_wall_mm']) for g in groups)
        # An original-code allowable limit cannot be exceeded by calculated credit.
        allowable=case.get('allowable_stress_mpa')
        if allowable is None and case.get('original_design_factor') is not None:
            allowable=case['smys_mpa']*case['original_design_factor']
        if allowable is not None:
            if allowable<=0:raise ValueError('Allowable stress must be positive.')
            ps=min(ps,2*allowable*eol/case['od_mm'])
    else:
        if not case.get('ffs_ref') or case.get('assessed_mawp_bar') is None:raise ValueError('Substrate credit requires referenced assessed MAWP.')
        ps=case['assessed_mawp_bar']/10
    fs=case.get('assessed_axial_capacity_kn')
    if fs is None:raise ValueError('Substrate credit requires an assessed axial capacity; unknown capacity is not zero.')
    if ps<0 or fs<0:raise ValueError('Assessed capacities cannot be negative.')
    return ps,fs*1000
