"""Independent scalar witnesses from ISO 24817:2017 equations."""
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
    assert r['fT1']==pytest.approx(1.)
    e0=.003061 * 10**(-.0044*20)
    assert r['epsilon_c']==pytest.approx(e0)
    feq=math.pi*200**2*5/4
    assert r['feq_c_n']==r['feq_a_n']==pytest.approx(feq)
    assert r['hoop_mm']==pytest.approx((5*100+.2*feq/(math.pi*200))/(40000*e0))
    assert r['axial_mm']==pytest.approx((feq/(math.pi*200*20000)-5*100*.2/40000)/e0)
    assert r['structural_mm']==max(r['hoop_mm'],r['axial_mm'])


def test_factors_cap_and_positive_qualification_offset():
    c,m=fixture(); c['cure_basis']='Confirmed qualified schedule'; m['tg_c']=110
    r=api().calculate_structural(c,m,'A'); assert r['fT1']==r['fT2']==1
    c['temperature_c']=60; m['t_qualified_c']=40; m['t_ambient_c']=20
    r=api().calculate_structural(c,m,'A')
    assert r['fT1']==pytest.approx(.79375)
    assert r['fT2']==pytest.approx(.71875)


def test_equivalent_loads_use_pressure_thrust_and_separate_load_terms():
    c,m=fixture(); c.update(axial_kn=-10,shear_kn=-3,bending_knm=-2,torsion_knm=-1)
    r=api().calculate_structural(c,m,'A')
    area=math.pi*200**2/4
    feq=5*area+math.hypot(10000,6000)+4*math.hypot(2e6,1e6)/200
    assert r['feq_c_n']==r['feq_a_n']==pytest.approx(feq)
    shear_pressure=(3000+2*1e6/200)/area
    assert r['peq_mpa']==pytest.approx(5*(1+(shear_pressure/5)**2))
    c['pressure_bar']=1
    r=api().calculate_structural(c,m,'A')
    assert r['peq_mpa']==pytest.approx(.1+shear_pressure)


def test_old_sharing_options_require_selection_of_2017_basis():
    c,m=fixture(); c['substrate_route']='Substrate sharing'
    for legacy_option in ('Restore original capacity','Conservative wall loss'):
        c['sharing_basis']=legacy_option
        with pytest.raises(ValueError,match='Known allowable stress'):
            api().calculate_structural(c,m,'A',ps_mpa=2)


def test_type_b_ignores_substrate_credit_and_checks_axial():
    c,m=fixture(); c.update(substrate_route='Substrate sharing',axial_kn=1000)
    r=api().calculate_structural(c,m,'B',ps_mpa=2,fs_n=100000)
    reference=api().calculate_structural(dict(c,substrate_route='Full laminate'),m,'B')
    assert r['structural_mm']==reference['structural_mm']==r['axial_mm']


def test_cyclic_threshold_slope_and_floor():
    c,m=fixture(); c.update(cyclic=True,cycles=7000,cycle_min_bar=20,cycle_max_bar=50)
    assert api().calculate_structural(c,m,'A')['fc']==1
    c['cycles']=70000
    logwidth=math.log10(150e6/7000)
    assert api().calculate_structural(c,m,'A')['fc']==pytest.approx(1-.75/logwidth)
    c['cycle_min_bar']=30
    slope=1.25*(.6-1)/logwidth
    assert api().calculate_structural(c,m,'A')['fc']==pytest.approx(
        1+slope*math.log10(70000)-math.tan(slope)*math.log10(7000))
    c.update(cycles=1e10,cycle_min_bar=0)
    assert api().calculate_structural(c,m,'A')['fc']==.25
    c['reversing_loads']=True
    with pytest.raises(ValueError): api().calculate_structural(c,m,'A')


def test_bond_and_tee_use_final_thickness_and_actual_wall():
    c,m=fixture(); c.update(install_pressure_bar=40,run_od_mm=200,branch_od_mm=100)
    m['alpha_c']=10e-6
    assert api().bond_stress(c,m,5)==pytest.approx(1.16)
    assert api().tee_pressure_limit(c,m,.002,ps_mpa=2,installed_mm=5)==pytest.approx(2.666666666666667)
    c['branch_od_mm']=None
    with pytest.raises(ValueError): api().tee_pressure_limit(c,m,.002,installed_mm=5)
    assert [api().component_factor(x) for x in ('Straight','Bend','Tee','Reducer','Flange')]==[1,1.2,2,1.1,1.1]
    with pytest.raises(ValueError): api().component_factor('unknown')


@pytest.mark.parametrize('key,value', [('od_mm',0),('pressure_bar',-1),('pressure_bar',float('nan')),('temperature_c',float('inf')),('design_life_years',1),('initial_service_life_years',21)])
def test_invalid_domains_rejected(key,value):
    c,m=fixture(); c[key]=value
    with pytest.raises(ValueError): api().calculate_structural(c,m,'A')


def test_temperature_type_b_longlife_cap_and_cold_strain():
    c,m=fixture(); c['temperature_c']=75
    with pytest.raises(ValueError,match='temperature'): api().calculate_structural(c,m,'B')
    c['temperature_c']=20; c['min_temperature_c']=-200; m['alpha_a']=30e-6
    with pytest.raises(ValueError,match='strain'): api().calculate_structural(c,m,'A')


def test_lts_uses_the_entered_repair_class_coefficient():
    c,m=fixture(); c.update(strain_basis='LTS',design_life_years=25,repair_class=1)
    r=api().calculate_structural(c,m,'A')
    assert r['epsilon_c']==pytest.approx(.007*1.0455*10**(-.00965*25)*r['fT2'])
