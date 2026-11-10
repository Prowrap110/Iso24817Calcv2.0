import math
import pytest
from prowrap_v2.sealing import solve_seal

M = dict(ec_mpa=45460,ea_mpa=43800,nu=.066,g_mpa=2450,gamma_n_mm=.250)
def case(p):
    return dict(od_mm=323.9,wall_mm=10,seal_shape='Circular',effective_diameter_mm=30,pressure_bar=p,repair_class=3,design_life_years=2)
def test_2026_fifty_bar_witness():
    r=solve_seal(case(50),M,.5,.79375)
    assert r['seal_mm']==pytest.approx(39.73581,rel=1e-5)
    assert r['asymptote_mpa']==pytest.approx(8.72029,rel=1e-5)
def test_ninety_bar_no_solution():
    with pytest.raises(ValueError,match='finite'): solve_seal(case(90),M,.5,.79375)
def test_true_circular_geometry_limit():
    c=case(10); c.update(od_mm=609.6,wall_mm=9.53,effective_diameter_mm=200)
    with pytest.raises(ValueError,match='geometry'): solve_seal(c,M,1,1)
def test_od_boundary():
    c=case(1);c.update(od_mm=60.3,effective_diameter_mm=15)
    with pytest.raises(ValueError): solve_seal(c,M,1,1)

def test_circle_must_enclose_whole_footprint():
    c=case(10);c.update(effective_diameter_mm=30,effective_axial_mm=25,effective_circ_mm=100)
    with pytest.raises(ValueError,match='enclose'):solve_seal(c,M,1,1)

def test_slot_equation23_closed_form_and_axial_bound():
    c=case(50);c.update(seal_shape='Axial slot',effective_circ_mm=170,effective_axial_mm=30)
    r=solve_seal(c,M,1,1)
    f=.69*10**(-.01584*2);E=math.sqrt(45460*43800)
    assert r['equation']==23
    assert r['seal_mm']==pytest.approx((5*323.9/f)**2/(8*E*.250))

def test_circumferential_selects_governing_larger_required_thickness():
    c=case(50);c.update(seal_shape='Circumferential slot',effective_axial_mm=20,effective_circ_mm=200)
    r=solve_seal(c,M,1,1);x=r['seal_mm'];f=.69*10**(-.01584*2);E=math.sqrt(45460*43800)
    eq23=(5*323.9/f)**2/(8*E*.250)
    assert x>=eq23
    if r['equation']==22:
        denom=(1-.066**2)/E*(20**4/(24*x**3)+math.pi*20/4)+3*20**2/(16*2450*x)*(.8+.066/2)/(1+.066)
        assert f*math.sqrt(.250/denom)==pytest.approx(5)


def test_circumferential_slot_both_pressure_capacities_must_pass():
    c=case(10);c.update(seal_shape='Circumferential slot',effective_axial_mm=100,effective_circ_mm=500)
    r=solve_seal(c,M,1,.7);x=r['seal_mm'];f=.7*.69*10**(-.01584*2);E=math.sqrt(45460*43800);w=100
    denom=(1-.066**2)/E*(w**4/(24*x**3)+math.pi*w/4)+3*w*w/(16*2450*x)*(.8+.066/2)/(1+.066)
    p22=f*math.sqrt(.250/denom);p23=f/323.9*math.sqrt(8*E*x*.250)
    assert min(p22,p23)==pytest.approx(1.)
    assert x>6.64

def test_circumferential_eq22_asymptote_cannot_be_bypassed():
    c=case(90);c.update(seal_shape='Circumferential slot',effective_axial_mm=100,effective_circ_mm=500)
    with pytest.raises(ValueError,match='finite'):solve_seal(c,M,1,.7)

def test_sealing_effective_size_rounds_up_to_five():
    c=case(10);c['effective_diameter_mm']=30.01
    r=solve_seal(c,M,1,1)
    c['effective_diameter_mm']=35
    assert r['effective_size_mm']==35
    assert r['seal_mm']==pytest.approx(solve_seal(c,M,1,1)['seal_mm'])
