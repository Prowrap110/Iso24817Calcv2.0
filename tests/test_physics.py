"""Independent scalar witnesses from ISO 24817:2026 normative equations."""
import math
import pytest
from prowrap_v2.schema import default_case


def api():
    from prowrap_v2 import physics
    return physics


def fixture():
    from prowrap_v2.materials import get_material
    c=default_case()
    c.update(od_mm=200,wall_mm=10,remaining_wall_mm=2,eol_wall_mm=2,
             pressure_bar=50,min_pressure_bar=10,install_pressure_bar=4,
             temperature_c=20,min_temperature_c=-20,install_temperature_c=20,
             axial_kn=0,shear_kn=0,bending_knm=0,torsion_knm=0,steel_cte=12e-6,
             allowable_stress_mpa=100,smys_mpa=100)
    m=get_material('PRW110+')
    m.update(ec_mpa=40000,ea_mpa=20000,nu=.2,alpha_c=12e-6,alpha_a=12e-6)
    return c,m


def test_modules_exist():
    import importlib.util
    assert importlib.util.find_spec('prowrap_v2.physics') is not None
    assert importlib.util.find_spec('prowrap_v2.materials') is not None


def test_material_profiles_and_independent_copies():
    from prowrap_v2.materials import get_material
    p=get_material('PRW110+')
    assert (p['tg_c'],p['ec_mpa'],p['ea_mpa'],p['lts'],p['gamma_n_mm'],p['g_mpa'],p['min_typeb_plies']) == (104.73,45460,43800,.007,.250,2450,3)
    assert get_material('PRW110')['tg_c']==78.18
    p['tg_c']=0
    assert get_material('PRW110+')['tg_c']==104.73
    with pytest.raises(ValueError): get_material('Other')


def test_report_cure_factors_and_pressure_endload_both_directions():
    c,m=fixture(); r=api().calculate_structural(c,m,'A')
    assert r['fT1']==pytest.approx(.7)
    assert r['epsilon_c']==pytest.approx(.0017496910471100555)
    assert r['feq_c_n']==pytest.approx(157079.63267948964)
    assert r['feq_a_n']==pytest.approx(157079.63267948964)
    assert r['hoop_mm']==pytest.approx(6.4297065579557575)
    assert r['axial_mm']==pytest.approx(5.7152947181828955)
    assert r['structural_mm']==r['hoop_mm']


def test_factors_cap_and_positive_qualification_offset():
    c,m=fixture(); c['cure_basis']='Confirmed qualified schedule'; m['tg_c']=110
    r=api().calculate_structural(c,m,'A'); assert r['fT1']==r['fT2']==1
    c['temperature_c']=60; m['t_qualified_c']=40; m['t_ambient_c']=20
    r=api().calculate_structural(c,m,'A')
    assert r['fT1']==pytest.approx(.79375)
    assert r['fT2']==pytest.approx(.91875)


def test_load_mapping_has_opposite_pressure_signs():
    c,m=fixture(); c.update(axial_kn=-10,shear_kn=-3,bending_knm=-2,torsion_knm=-1)
    r=api().calculate_structural(c,m,'A')
    assert r['feq_c_n']==pytest.approx(108931.39003416065)
    assert r['feq_a_n']==pytest.approx(208043.20289466888)
    assert r['peq_mpa']==pytest.approx(5.413802852038928)


def test_distinct_sharing_equations_and_stress_margin():
    c,m=fixture(); c['substrate_route']='Substrate sharing'
    r=api().calculate_structural(c,m,'A',ps_mpa=2)
    assert r['hoop_mm']==pytest.approx(3.857823934773455)
    assert r['axial_mm']==pytest.approx(3.429176830909737)
    c['sharing_basis']='Restore original capacity'
    assert api().calculate_structural(c,m,'A',ps_mpa=2)['hoop_mm']==pytest.approx(10.287530492729212)
    c['sharing_basis']='Conservative wall loss'
    assert api().calculate_structural(c,m,'A',ps_mpa=2)['hoop_mm']==pytest.approx(11.430589436365791)
    c['substrate_route']='Substrate stress limit'
    r=api().calculate_structural(c,m,'A',ps_mpa=2)
    assert r['hoop_mm']==pytest.approx(16.875)
    assert r['axial_mm']==pytest.approx(15)
    c['install_pressure_bar']=20
    with pytest.raises(ValueError,match='stress margin'): api().calculate_structural(c,m,'A',ps_mpa=2)


def test_type_b_ignores_substrate_credit_and_checks_axial():
    c,m=fixture(); c.update(substrate_route='Substrate sharing',axial_kn=1000)
    r=api().calculate_structural(c,m,'B',ps_mpa=2,fs_n=100000)
    reference=api().calculate_structural(dict(c,substrate_route='Full laminate'),m,'B')
    assert r['structural_mm']==reference['structural_mm']==r['axial_mm']


def test_cyclic_threshold_slope_and_floor():
    c,m=fixture(); c.update(cyclic=True,cycles=7000,cycle_min_bar=20,cycle_max_bar=50)
    assert api().calculate_structural(c,m,'A')['fc']==1
    c['cycles']=70000
    assert api().calculate_structural(c,m,'A')['fc']==pytest.approx(.827)
    c['cycle_min_bar']=30
    assert api().calculate_structural(c,m,'A')['fc']==pytest.approx(.8844)
    c.update(cycles=1e10,cycle_min_bar=0)
    assert api().calculate_structural(c,m,'A')['fc']==.4
    c['reversing_loads']=True
    with pytest.raises(ValueError): api().calculate_structural(c,m,'A')


def test_bond_and_tee_use_final_thickness_and_actual_wall():
    c,m=fixture(); c.update(install_pressure_bar=40,run_od_mm=200,branch_od_mm=100)
    m['alpha_c']=10e-6
    assert api().bond_stress(c,m,5)==pytest.approx(1.16)
    assert api().tee_pressure_limit(c,m,.002,ps_mpa=2,installed_mm=5)==pytest.approx(4.666666666666667)
    c['branch_od_mm']=None
    with pytest.raises(ValueError): api().tee_pressure_limit(c,m,.002,installed_mm=5)
    assert [api().component_factor(x) for x in ('Straight','Bend','Tee','Reducer','Flange')]==[1,1.2,2,1.1,1.1]
    with pytest.raises(ValueError): api().component_factor('unknown')


@pytest.mark.parametrize('key,value', [('od_mm',0),('pressure_bar',-1),('pressure_bar',float('nan')),('temperature_c',float('inf')),('design_life_years',1),('design_life_years',21),('initial_service_life_years',21)])
def test_invalid_domains_rejected(key,value):
    c,m=fixture(); c[key]=value
    with pytest.raises(ValueError): api().calculate_structural(c,m,'A')


def test_temperature_type_b_longlife_cap_and_cold_strain():
    c,m=fixture(); c['temperature_c']=75
    with pytest.raises(ValueError,match='temperature'): api().calculate_structural(c,m,'B')
    c['temperature_c']=20; c['min_temperature_c']=-200; m['alpha_a']=30e-6
    with pytest.raises(ValueError,match='strain'): api().calculate_structural(c,m,'A')


def test_lts_longlife_and_initial_service_envelope():
    c,m=fixture(); c.update(strain_basis='LTS',design_life_years=50,repair_class=1)
    r=api().calculate_structural(c,m,'A')
    assert r['epsilon_c']==pytest.approx(.7*.007*.760*10**(-.00273*50))
    with pytest.raises(ValueError): api().calculate_structural(dict(c,repair_class=3),m,'B')
