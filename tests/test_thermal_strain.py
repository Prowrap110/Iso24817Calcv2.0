"""Independent ISO 24817:2017 Equation (10) and paired-app regression checks."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from prowrap_v2.batch import template_workbook
from prowrap_v2.materials import get_material
from prowrap_v2.physics import _strain_and_factors
from test_engine import valid_case


def thermal_case(**changes):
    case = valid_case()
    case.update(temperature_c=40, min_temperature_c=40,
                install_temperature_c=60, strain_basis='Default')
    case.update(changes)
    return case


@pytest.mark.parametrize('product', ['PRW110', 'PRW110+'])
@pytest.mark.parametrize('basis', ['Default', 'LTS'])
def test_heating_and_cooling_same_magnitude_always_deduct_strain(product, basis):
    material = get_material(product)
    case = thermal_case(product=product, strain_basis=basis)
    hot_install = _strain_and_factors(case, material, 'A')
    cold_install = _strain_and_factors(dict(case, install_temperature_c=20), material, 'A')
    zero = _strain_and_factors(dict(case, install_temperature_c=40), material, 'A')
    for direction, alpha in [('c', 'alpha_c'), ('a', 'alpha_a')]:
        deduction = 20 * abs(case['steel_cte'] - material[alpha])
        expected = zero['epsilon_' + direction] - zero['fc'] * deduction
        assert hot_install['epsilon_' + direction] == pytest.approx(expected)
        assert cold_install['epsilon_' + direction] == pytest.approx(expected)
        assert expected < zero['epsilon_' + direction]


@pytest.mark.parametrize('basis', ['Default', 'LTS'])
def test_both_service_extremes_use_largest_absolute_mismatch(basis):
    case = thermal_case(min_temperature_c=0, install_temperature_c=80, strain_basis=basis)
    material = get_material('PRW110+')
    actual = _strain_and_factors(case, material, 'A')
    zero = _strain_and_factors(dict(case, min_temperature_c=40, install_temperature_c=40), material, 'A')
    for direction, alpha in [('c', 'alpha_c'), ('a', 'alpha_a')]:
        deduction = 80 * abs(case['steel_cte'] - material[alpha])
        assert actual['epsilon_' + direction] == pytest.approx(
            zero['epsilon_' + direction] - zero['fc'] * deduction)


def test_nonpositive_strain_from_absolute_mismatch_is_rejected():
    material = get_material('PRW110+')
    material['alpha_c'] = -60e-6
    with pytest.raises(ValueError, match='Nonpositive design strain'):
        _strain_and_factors(thermal_case(install_temperature_c=80), material, 'A')


def test_tender_temperature_witness():
    actual = _strain_and_factors(thermal_case(
        temperature_c=60, min_temperature_c=60, install_temperature_c=80),
        get_material('PRW110+'), 'A')
    assert actual['epsilon_c'] == pytest.approx(0.0018893000488677135)
    assert actual['epsilon_a'] == pytest.approx(0.0017063000488677135)


def test_single_and_batch_apps_use_the_same_corrected_thermal_strain():
    case = thermal_case(temperature_c=60, min_temperature_c=60, install_temperature_c=80)
    root = Path(__file__).parents[1]
    single = AppTest.from_file(str(root / 'app.py'), default_timeout=30)
    for key, value in case.items():
        single.session_state['case_' + key] = value
    single.run().button(key='calculate').click().run()
    assert not single.exception
    one = single.session_state['calculation_results'][0]
    assert one['status'] == 'CALCULATED', one['issues']

    book = load_workbook(BytesIO(template_workbook()))
    setup = book['Batch Setup']
    rows = {setup.cell(r, 3).value: r for r in range(10, setup.max_row + 1)}
    for key, value in case.items():
        if key in rows:
            setup.cell(rows[key], 2).value = value
    book['Repair Cases']['A5'] = case['repair_id']
    content = BytesIO()
    book.save(content)
    batch = AppTest.from_file(str(root / 'batch_app.py'), default_timeout=30).run()
    batch.get('file_uploader')[0].upload('thermal-regression.xlsx', content.getvalue()).run()
    batch.button[0].click().run()
    assert not batch.exception
    paired = batch.session_state['batch_upload']['output'][1][0]
    assert paired['status'] == 'CALCULATED', paired['issues']
    for result in (one, paired):
        structural = result['details']['load_cases'][0]['structural']
        assert structural['epsilon_c'] == pytest.approx(0.0018893000488677135)
        assert structural['epsilon_a'] == pytest.approx(0.0017063000488677135)
    assert one['results'] == paired['results']
