"""Dent inputs expose assessed capacity without inheriting corrosion controls."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from prowrap_v2.schema import default_case
from prowrap_v2.ui_logic import active_fields, case_for_calculation


@pytest.mark.parametrize('geometry', ['Measured', '60/40 population'])
def test_dent_inputs_keep_assessment_and_stress_override_visible(geometry):
    case = default_case()
    case.update(mechanism='Dent no-crack', purpose='Estimate', dent_mode=geometry,
                substrate_route='Full laminate', original_design_factor=.72,
                allowable_stress_mpa=280, axial_mawp_bar=20)
    fields = set(active_fields(case))
    assert {'dent_mawp_bar', 'dent_ffs_ref', 'inspection_ref', 'no_crack_confirmed',
            'dent_complex', 'cyclic', 'original_design_factor', 'allowable_stress_mpa',
            'axial_mawp_bar', 'assessed_axial_capacity_kn', 'qualified_wall_loss_pct',
            'qualification_ref'} <= fields
    assert not {'substrate_route', 'sharing_basis', 'ffs_method', 'ffs_ref',
                'b31g_safety_factor', 'assessed_mawp_bar', 'smts_mpa'} & fields
    submitted = case_for_calculation(case)
    assert submitted['original_design_factor'] == .72
    assert submitted['allowable_stress_mpa'] == 280
    assert submitted['axial_mawp_bar'] == 20


def test_single_app_shows_derived_dent_stress_and_manual_override():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py'), default_timeout=20).run()
    app.selectbox(key='case_mechanism').set_value('Dent no-crack').run()
    assert not app.exception
    assert 'case_substrate_route' not in {item.key for item in app.selectbox}
    assert 'case_ffs_method' not in {item.key for item in app.selectbox}
    assert 'case_b31g_safety_factor' not in {item.key for item in app.number_input}
    app.number_input(key='case_smys_mpa').set_value(415).run()
    app.number_input(key='case_original_design_factor').set_value(.72).run()
    assert any('298.800 MPa' in item.value for item in app.caption)
    app.number_input(key='case_allowable_stress_mpa').set_value(250).run()
    assert any('250.000 MPa' in item.value and 'Manual' in item.value for item in app.caption)
    assert not app.exception


def test_dent_submission_discards_stale_corrosion_capacity_fields():
    case = default_case()
    case.update(mechanism='Dent no-crack', substrate_route='Substrate sharing',
                sharing_basis='Restore original capacity', ffs_method='Modified B31G',
                b31g_safety_factor=4, assessed_mawp_bar=100, ffs_ref='Corrosion assessment',
                dent_mawp_bar=30, dent_ffs_ref='Dent assessment', original_design_factor=.72)
    submitted = case_for_calculation(case)
    assert submitted['b31g_safety_factor'] is None
    assert submitted['assessed_mawp_bar'] is None
    assert submitted['ffs_ref'] == ''
    assert submitted['sharing_basis'] == 'Known allowable stress'
    assert submitted['dent_mawp_bar'] == 30
    assert submitted['dent_ffs_ref'] == 'Dent assessment'

