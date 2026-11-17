"""Independent pressure-deficit and applicability regressions for plain dents."""
import pytest
from prowrap_v2.engine import evaluate_case, expand_population
from prowrap_v2.examples import example_case


def dent_case(**changes):
    c = example_case()
    c.update(mechanism='Dent no-crack', remaining_wall_mm=19.1, wall_mm=19.1,
             od_mm=1219.2, smys_mpa=482.9, original_design_factor=.72,
             pressure_bar=71.5, maop_bar=51.48, pressure_basis='MAOP',
             install_pressure_bar=45., temperature_c=80., min_temperature_c=60.,
             install_temperature_c=80., strain_basis='Default',
             defect_length_mm=600., defect_width_mm=250., zone_length_mm=600.,
             dent_depth_mm=73.152, no_crack_confirmed=True,
             dent_ffs_ref='Synthetic assessed dent', dent_mawp_bar=51.48,
             substrate_route='Full laminate', ffs_method='Modified B31G')
    c.update(changes)
    return c


def test_assessed_dent_equal_to_maop_uses_minimum_without_b31g():
    r = evaluate_case(dent_case(smts_mpa=None, material_grade='', design_code=''))
    assert r['status'] == 'ESTIMATE', r
    assert r['results']['installed_plies'] == 3
    assert r['results']['installed_thickness_mm'] == pytest.approx(2.49)
    assert r['details']['substrate_pressure_mpa'] == pytest.approx(5.148)
    # Eq. (1) retains the Poisson contribution from pressure thrust at p = Ps.
    assert r['details']['required_thickness_mm'] == pytest.approx(1.3104133198776944)
    assert r['inputs']['substrate_route'] == 'Substrate stress limit'
    assert r['inputs']['ffs_method'] == 'External assessment'
    assert r['inputs']['pressure_bar'] == 71.5  # entered DP is preserved
    assert r['inputs']['allowable_stress_mpa'] == pytest.approx(347.688)
    assert 'b31g' not in r['details']
    assert r['details']['axial_capacity']['force_kn'] is None


def test_dent_equation_uses_full_allowable_stress_and_pressure_thrust():
    result = evaluate_case(dent_case(dent_mawp_bar=45.))
    assert result['status'] == 'ESTIMATE', result
    structural = result['details']['load_cases'][0]['structural']
    # Eq. (1): D = 1219.2 mm, Es = 200000 MPa, Ec = 45460 MPa, s = 347.688 MPa.
    # The pressure bracket is 5.148 * (1 + 0.066 / 2) - 4.5 MPa.
    assert structural['hoop_mm'] == pytest.approx(6.308811234223643)
    assert structural['axial_mm'] == 0
    assert result['details']['substrate_pressure_mpa'] == 4.5
    offline = evaluate_case(dent_case(dent_mawp_bar=45., install_pressure_bar=0.))
    assert offline['status'] == 'ESTIMATE', offline
    assert offline['details']['required_thickness_mm'] == structural['hoop_mm']


def test_manual_dent_allowable_stress_changes_structural_thickness():
    result = evaluate_case(dent_case(allowable_stress_mpa=300, original_design_factor=None))
    assert result['status'] == 'ESTIMATE', result
    assert result['details']['dent_capacity']['allowable_stress_source'] == 'Manual allowable stress'
    assert result['details']['substrate_pressure_mpa'] == pytest.approx(5.148)
    assert result['details']['required_thickness_mm'] == pytest.approx(1.5187166212054526)


def test_dent_axial_capacity_fields_are_legacy_records():
    baseline = evaluate_case(dent_case())
    for changes in ({'axial_mawp_bar': 40}, {'assessed_axial_capacity_kn': 0}):
        result = evaluate_case(dent_case(**changes))
        assert result['status'] == 'ESTIMATE', result
        assert all(result['inputs'][key] == value for key, value in changes.items())
        assert result['results'] == baseline['results']
        assert result['details']['load_cases'] == baseline['details']['load_cases']


@pytest.mark.parametrize('changes', [
    {'dent_mawp_bar': 44.9}, {'dent_mawp_bar': None}, {'dent_mawp_bar': 0},
    {'no_crack_confirmed': False}, {'dent_ffs_ref': ''}, {'inspection_ref': ''},
    {'dent_complex': True}, {'component': 'Bend', 'component_qualified': True, 'component_ref': 'X'},
    {'remaining_wall_mm': 19}, {'growth_basis': 'Corrosion rate', 'corrosion_rate_mm_year': .01},
    {'through_wall': True}, {'prevent_containment': True},
    {'original_design_factor': None}, {'original_design_factor': 1.01},
    {'allowable_stress_mpa': 0}, {'cyclic': True, 'cycles': 10, 'cycle_min_bar': 0, 'cycle_max_bar': 51.48},
])
def test_unsupported_or_unassessed_dents_never_issue_installation(changes):
    r = evaluate_case(dent_case(**changes))
    assert r['status'] in ('ENGINEERING_HOLD', 'INPUT_ERROR', 'NO_VALID_DESIGN'), r
    assert not r['results']


def test_named_pressure_above_capacity_reinforces_but_hotter_capacity_is_held():
    r = evaluate_case(dent_case(), loads=[{'load_id': 'High', 'pressure_bar': 60}])
    assert r['status'] == 'ESTIMATE', r
    assert r['details']['controlling_load_id'] == 'High'
    assert r['results']['installed_plies'] > 3
    hot = evaluate_case(dent_case(), loads=[{'load_id': 'Hot', 'temperature_c': 81}])
    assert hot['status'] == 'ENGINEERING_HOLD' and not hot['results']


def test_population_estimate_cannot_invent_assessed_capacity_or_bypass_dent_scope():
    for changes in ({'dent_mawp_bar': None}, {'no_crack_confirmed': False}, {'dent_complex': True}):
        rows = expand_population(dent_case(dent_mode='60/40 population', quantity=7, **changes))
        assert all(evaluate_case(c)['status'] == 'ENGINEERING_HOLD' for c in rows)
    rows = expand_population(dent_case(dent_mode='60/40 population', quantity=7))
    results = [evaluate_case(c) for c in rows]
    assert all(r['status'] == 'ESTIMATE' for r in results), results
    assert sum(r['results']['quantity'] for r in results) == 7
    assert all(r['results']['installed_plies'] == 3 for r in results)


def test_held_installation_records_dent_method_without_corrosion_provenance():
    r = evaluate_case(dent_case(dent_mawp_bar=44))
    assert r['status'] == 'ENGINEERING_HOLD' and not r['results']
    assert r['inputs']['substrate_route'] == 'Substrate stress limit'
    assert r['inputs']['ffs_method'] == 'External assessment'
    assert r['inputs']['assessed_mawp_bar'] == 44
