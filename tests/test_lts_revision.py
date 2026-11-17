"""Owner-selected 0.7% strain is derated, never used as final design strain."""
import pytest
from prowrap_v2.engine import evaluate_case
from prowrap_v2.examples import example_case


@pytest.mark.parametrize('product', ['PRW110', 'PRW110+'])
def test_lts_uses_point_seven_percent_before_life_and_temperature_factors(product):
    c = example_case()
    c.update(product=product, strain_basis='LTS', temperature_c=40,
             min_temperature_c=40, install_temperature_c=40)
    r = evaluate_case(c)
    assert r['status'] == 'ESTIMATE', r
    st = r['details']['load_cases'][0]['structural']
    # Class 3, 20 y, Table 8 with Type A service limit Tg - 20.
    delta = (104.73 if product == 'PRW110+' else 78.18) - 20 - 40
    f_t2 = .7 + .00125*delta + .0000625*delta**2
    assert st['epsilon_c'] == pytest.approx(.007 * .760 * 10**(-.00273*20) * f_t2)
    assert st['epsilon_c'] < .007
    assert r['details']['long_term_strain_input']['value'] == .007
    assert r['details']['long_term_strain_input']['percent'] == pytest.approx(.7)
    default = evaluate_case(dict(c, strain_basis='Default'))
    assert default['details']['load_cases'][0]['structural']['epsilon_c'] == pytest.approx(.003061*10**(-.0044*20)*f_t2)
    assert 'long_term_strain_input' not in default['details']



def test_owner_lts_is_held_for_design_without_annex_e_material_evidence():
    c=example_case()
    r=evaluate_case(dict(c,strain_basis='LTS',purpose='Design'))
    assert r['status']=='ENGINEERING_HOLD'
    assert 'Annex E' in r['issues'][0]
