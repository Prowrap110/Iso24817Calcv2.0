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
    # Class 3, 20 y, report cure fT2=.7; no thermal differential.
    assert st['epsilon_c'] == pytest.approx(.007 * .760 * 10**(-.00273*20) * .7)
    assert st['epsilon_c'] < .007
    assert r['details']['long_term_strain_input']['value'] == .007
    assert r['details']['long_term_strain_input']['percent'] == pytest.approx(.7)
    default = evaluate_case(dict(c, strain_basis='Default'))
    assert default['details']['load_cases'][0]['structural']['epsilon_c'] == pytest.approx(.0017496910471100555)
    assert 'long_term_strain_input' not in default['details']
