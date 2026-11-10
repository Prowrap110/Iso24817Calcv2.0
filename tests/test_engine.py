import pytest
from prowrap_v2.schema import default_case
from prowrap_v2.engine import evaluate_case, expand_population

def valid_case():
    c=default_case();c.update(repair_id='R1',od_mm=323.9,wall_mm=10,smys_mpa=358,smts_mpa=455,pressure_bar=30,min_pressure_bar=0,temperature_c=40,min_temperature_c=20,install_pressure_bar=0,install_temperature_c=20,defect_length_mm=100,defect_width_mm=50,zone_length_mm=100,remaining_wall_mm=5,growth_basis='No growth confirmed',growth_ref='Inspection 1',load_basis='Pressure-only confirmed',landing_mode='Unrestricted confirmed',inspection_ref='I1',procedure_ref='P1',cure_ref='C1')
    return c

def test_success_no_assumption_warnings():
    r=evaluate_case(valid_case());assert r['status']=='CALCULATED',r
    assert r['results']['installed_thickness_mm']>=2
    assert not any('qualification' in x.lower() for x in r['issues'])
def test_invalid_missing_and_nan_no_installation():
    for key,value in [('od_mm',float('nan')),('pressure_bar',None),('wall_mm',0),('cyclic','false')]:
        c=valid_case();c[key]=value;r=evaluate_case(c)
        assert r['status']=='INPUT_ERROR',r
        assert 'installed_plies' not in r['results']
def test_sealed_leak_remains_type_b():
    c=valid_case();c['through_wall']=True
    r=evaluate_case(c);assert r['status']!='CALCULATED';assert not r['results']
def test_restricted_landing_below_25_rejected():
    c=valid_case();c.update(landing_mode='Restricted',landing_left_mm=20,landing_right_mm=500)
    r=evaluate_case(c);assert r['status']=='NO_VALID_DESIGN';assert not r['results']
def test_dent_requires_assessment():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_depth_mm=19,no_crack_confirmed=True)
    r=evaluate_case(c);assert r['status']=='ENGINEERING_HOLD';assert not r['results']
def test_population_preserves_count():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_mode='60/40 population',purpose='Estimate',quantity=7)
    rs=expand_population(c);assert sum(x['quantity'] for x in rs)==7
    assert all(x['purpose']=='Estimate' for x in rs)
def test_population_never_accepts_design():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_mode='60/40 population')
    assert evaluate_case(c)['status']=='ENGINEERING_HOLD'
def test_quantity_multiplies_procurement_not_dimensions():
    c=valid_case();r1=evaluate_case(c);c['quantity']=3;r3=evaluate_case(c)
    assert r3['results']['installed_plies']==r1['results']['installed_plies']
    assert r3['results']['installed_thickness_mm']==r1['results']['installed_thickness_mm']
    assert r3['results']['total_repair_length_mm']==r1['results']['total_repair_length_mm']
    assert r3['results']['fabric_area_m2']==pytest.approx(3*r1['results']['fabric_area_m2'])

def test_pressure_only_retains_pressure_end_loading():
    r=evaluate_case(valid_case());s=r['details']['load_cases'][0]['structural']
    assert s['feq_a_n']>0 and s['feq_c_n']>0 and s['axial_mm']>0

def test_every_load_case_controls_final_dimensions_and_bond():
    c=valid_case();c.update(pressure_bar=10)
    base=evaluate_case(c)
    r=evaluate_case(c,loads=[dict(load_id='Hot/high',pressure_bar=30,temperature_c=60)])
    assert r['status']=='CALCULATED',r
    assert r['details']['controlling_load_id']=='Hot/high'
    assert r['results']['installed_thickness_mm']>base['results']['installed_thickness_mm']
    assert len([x for x in r['checks'] if x['name'].startswith('Bond')])==2

def test_bond_failure_suppresses_procurement():
    c=valid_case();c.update(pressure_bar=100,install_pressure_bar=100,remaining_wall_mm=1)
    r=evaluate_case(c)
    assert r['status']=='NO_VALID_DESIGN',r
    assert any(x['name'].startswith('Bond') and not x['passed'] for x in r['checks'])
    assert not r['results']

def test_measured_defects_noninteraction_and_minimum_wall():
    c=valid_case();c.update(defect_mode='Measured individual',independence_confirmed=True,grouping_ref='Map1')
    ds=[dict(defect_id='a',length_mm=10,width_mm=10,remaining_wall_mm=3,separation_mm=31)]
    r=evaluate_case(c,ds);assert r['status']=='CALCULATED',r
    assert r['inputs']['remaining_wall_mm']==3
    ds[0]['separation_mm']=30
    assert evaluate_case(c,ds)['status']=='ENGINEERING_HOLD'

def test_unknown_cycle_bounds_and_invalid_linked_values():
    c=valid_case();c.update(cyclic=True,cycles=100000)
    assert evaluate_case(c)['status']=='INPUT_ERROR'
    c=valid_case()
    assert evaluate_case(c,loads=[dict(load_id='a',pressure_bar=float('inf'))])['status']=='INPUT_ERROR'
    assert evaluate_case(c,loads=[dict(load_id='a'),dict(load_id='a')])['status']=='INPUT_ERROR'

def test_annex_c_and_b31g_gates():
    c=valid_case();c.update(substrate_route='Substrate sharing',ffs_method='Modified B31G',allowable_stress_mpa=200,assessed_axial_capacity_kn=0,ffs_ref='FFS1',material_grade='API 5L X52',design_code='ASME B31.8')
    assert evaluate_case(c)['status']=='ENGINEERING_HOLD'
    c.update(qualified_wall_loss_pct=60,qualification_ref='C1')
    r=evaluate_case(c);assert r['status']=='CALCULATED',r
    c['smts_mpa']=None
    assert evaluate_case(c)['status']=='ENGINEERING_HOLD'

def test_population_estimates_are_labelled_and_quantity_validated():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_mode='60/40 population',purpose='Estimate',quantity=7)
    rs=[evaluate_case(x) for x in expand_population(c)]
    assert all(r['status']=='ESTIMATE' and 'estimate_label' in r['details'] for r in rs),rs
    assert sum(r['results']['quantity'] for r in rs)==7
    c['quantity']=1.2
    assert evaluate_case(c)['status']=='INPUT_ERROR'

def test_unsupported_crack_and_reversing_loads_hold():
    for changes in [dict(mechanism='Crack'),dict(reversing_loads=True,external_assessment_ref='ref')]:
        c=valid_case();c.update(changes);assert evaluate_case(c)['status']=='ENGINEERING_HOLD'

def test_typeb_both_structural_directions_and_three_ply_minimum():
    c=valid_case();c.update(through_wall=True,pressure_bar=1,defect_length_mm=15,defect_width_mm=15,effective_diameter_mm=15,effective_geometry_ref='Footprint1')
    r=evaluate_case(c);assert r['status']=='CALCULATED',r
    assert r['results']['installed_plies']>=3
    s=r['details']['load_cases'][0]['structural'];assert s['axial_mm']>0 and s['hoop_mm']>0

def test_typeb_cap_blocks_installed_schedule():
    c=valid_case();c.update(through_wall=True,pressure_bar=70,effective_diameter_mm=50,effective_geometry_ref='Footprint1',od_mm=609.6,wall_mm=9.53,design_life_years=2,initial_service_life_years=2)
    r=evaluate_case(c);assert r['status']=='NO_VALID_DESIGN',r
    assert not r['results']

def test_procurement_widths_and_putty_use_zone_not_individual_pit():
    c=valid_case();c.update(defect_mode='Independent 10x10',zone_length_mm=450,independence_confirmed=True,grouping_ref='Map',cloth_widths='300')
    r=evaluate_case(c);assert r['status']=='CALCULATED',r
    assert r['results']['count_500']==0
    assert r['results']['putty_kg']==1.5

def test_population_missing_od_stays_invalid_without_exception():
    c=valid_case();c.update(od_mm=None,mechanism='Dent no-crack',dent_mode='60/40 population',purpose='Estimate')
    assert expand_population(c)==[c]
    assert evaluate_case(c)['status']=='INPUT_ERROR'

def test_annex_c_boundary_is_strict_and_internal_independence_held():
    c=valid_case();c.update(substrate_route='Substrate sharing',ffs_ref='FFS',assessed_mawp_bar=10,assessed_axial_capacity_kn=0,allowable_stress_mpa=200,qualified_wall_loss_pct=50,qualification_ref='Q')
    assert evaluate_case(c)['status']=='ENGINEERING_HOLD'
    c=valid_case();c.update(defect_mode='Independent 10x10',defect_location='Internal',independence_confirmed=True,grouping_ref='G')
    assert evaluate_case(c)['status']=='ENGINEERING_HOLD'

def test_zero_measured_wall_classifies_type_b():
    c=valid_case();c.update(defect_mode='Measured individual',independence_confirmed=True,grouping_ref='Map',effective_geometry_ref='Opening',effective_diameter_mm=15,pressure_bar=1)
    ds=[dict(defect_id='a',length_mm=10,width_mm=10,remaining_wall_mm=0,separation_mm=31)]
    r=evaluate_case(c,ds);assert r['details']['repair_type']=='B',r
    assert r['status']=='CALCULATED',r

def test_additional_assessed_thickness_controls_case():
    c=valid_case();r=evaluate_case(c,loads=[dict(load_id='Other',other_thickness_mm=15)])
    assert r['status']=='CALCULATED',r
    assert r['results']['required_thickness_mm']==15
    assert r['details']['controlling_load_id']=='Other'

def test_dent_additional_pressure_cannot_bypass_ffs():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_depth_mm=10,no_crack_confirmed=True,dent_ffs_ref='D1',dent_mawp_bar=35)
    assert evaluate_case(c)['status']=='CALCULATED'
    assert evaluate_case(c,loads=[dict(load_id='High',pressure_bar=40)])['status']=='ENGINEERING_HOLD'

def test_modified_b31g_reference_mpa_and_smts_cap():
    from prowrap_v2.assessment import modified_b31g
    c=valid_case();c.update(od_mm=457.2,wall_mm=9.53,smys_mpa=359,smts_mpa=500,b31g_safety_factor=1/.72,material_grade='API5L X52',design_code='ASME B31.8',ffs_ref='FFS1')
    assert modified_b31g(c,100,4.5)==pytest.approx(9.951873620726573)
    c['smts_mpa']=400
    assert modified_b31g(c,100,4.5)<9.951873620726573

def test_procurement_minimizes_material_and_covers_with_splices():
    from prowrap_v2.procurement import bands
    # Two 300 mm bands cover 550 mm; one 500 mm band cannot cover it.
    assert bands(550)['count_300']==2
    assert bands(550)['gross_mm']==600
    # A 500+300 pair covers 750 mm with one controlled 50 mm splice.
    assert bands(750)['count_500']==1 and bands(750)['count_300']==1
    assert bands(750)['covered_mm']==750


def test_final_nonfinite_material_quantity_never_issues_schedule():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_depth_mm=1e200,defect_width_mm=1e200,no_crack_confirmed=True,dent_ffs_ref='D1',dent_mawp_bar=35)
    r=evaluate_case(c);assert r['status']=='NO_VALID_DESIGN',r
    assert not r['results']

@pytest.mark.parametrize('changes',[dict(repair_class=1,pressure_bar=21,service_category='Non-hazardous water / gas'),dict(repair_class=2,pressure_bar=21,service_category='Fire water'),dict(repair_class=1,pressure_bar=10,temperature_c=41,service_category='Non-hazardous water / gas'),dict(repair_class=2,pressure_bar=10,service_category='Produced water')])
def test_service_class_limits(changes):
    c=valid_case();c.update(changes);assert evaluate_case(c)['status']=='ENGINEERING_HOLD'

def test_public_population_marker_cannot_bypass_dent_design():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_depth_mm=10,population_estimate=True)
    r=evaluate_case(c);assert r['status']=='ENGINEERING_HOLD' and not r['results']

def test_population_geometry_is_recomputed_not_trusted_marker():
    c=valid_case();c.update(mechanism='Dent no-crack',dent_mode='60/40 population',purpose='Estimate',dent_depth_mm=10,population_estimate=True)
    assert evaluate_case(c)['status']=='ENGINEERING_HOLD'

def test_full_thickness_zone_contains_rounded_slot_footprint():
    c=valid_case();c.update(through_wall=True,pressure_bar=1,effective_geometry_ref='Opening',seal_shape='Axial slot',effective_axial_mm=1000.1,effective_circ_mm=15)
    r=evaluate_case(c);assert r['status']=='CALCULATED',r
    assert r['inputs']['zone_length_mm']==1005
    assert r['results']['total_repair_length_mm']>=1005+2*r['results']['overlap_mm']

@pytest.mark.parametrize('changes',[dict(through_wall=True),dict(od_mm=20,wall_mm=5,pressure_bar=100),dict(product='PRW110'),dict(substrate_route='Full laminate')])
def test_named_load_cannot_change_repair_identity_geometry_or_type(changes):
    c=valid_case();r=evaluate_case(c,loads=[dict(load_id='Unsafe',**changes)])
    assert r['status']=='INPUT_ERROR' and not r['results']
