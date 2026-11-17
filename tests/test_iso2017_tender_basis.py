import math

import pytest

from prowrap_v2.assessment import substrate_capacity
from prowrap_v2.materials import get_material
from prowrap_v2.physics import calculate_structural
from prowrap_v2.schema import default_case


def base_case(**overrides):
    case = default_case()
    case.update(od_mm=355.6, wall_mm=7.92, remaining_wall_mm=2.376,
                temperature_c=60, min_temperature_c=60, install_temperature_c=80,
                pressure_bar=92, install_pressure_bar=30, smys_mpa=415, smts_mpa=520,
                original_design_factor=.72, material_grade='API 5L X60', design_code='ASME B31.8',
                load_basis='Pressure-only confirmed', substrate_route='Substrate sharing')
    case.update(overrides)
    return case


def test_isolated_pit_credit_uses_2017_annex_worked_example_stress_basis():
    case = base_case()
    pit = dict(length_mm=10, width_mm=10, eol_wall_mm=2.376)
    p, _ = substrate_capacity(case, [pit], 2.376)
    assert p == pytest.approx(2 * .72 * 415 * 2.376 / (355.6 - 2.376))


def test_strain_sharing_uses_live_hoop_term_and_2017_axial_check():
    case = base_case()
    m = get_material('PRW110+')
    r = calculate_structural(case, m, 'A', ps_mpa=4)
    d, p, t, ec, ea, nu = 355.6, 9.2, r['hoop_mm'], m['ec_mpa'], m['ea_mpa'], m['nu']
    feq = math.pi * d**2 * p / 4
    assert r['equations'] == '5/6'
    expected_hoop_strain = ((p - 4) * d / 2 + nu * feq / (math.pi * d)) / (ec * t)
    expected_hoop_strain -= 3 * d / (2 * (ec * t + case['steel_modulus_mpa'] * 2.376))
    assert r['epsilon_c'] == pytest.approx(expected_hoop_strain)
    assert r['axial_mm'] == pytest.approx(
        (feq / (math.pi * d * ea) - p * d * nu / (2 * ec)) / r['epsilon_a'])
    assert r['axial_mm'] == calculate_structural(case, m, 'A', ps_mpa=6)['axial_mm']


def test_stress_limit_for_dent_uses_allowable_stress_in_denominator():
    case = base_case(substrate_route='Substrate stress limit', remaining_wall_mm=7.92,
                     allowable_stress_mpa=298.8)
    m = get_material('PRW110+')
    r = calculate_structural(case, m, 'A', ps_mpa=6)
    expected = (355.6 * case['steel_modulus_mpa'] / (2 * 298.8 * m['ec_mpa'])
                * (9.2 * (1 + m['nu'] / 2) - 6))
    assert r['equations'] == '1/2'
    assert r['hoop_mm'] == pytest.approx(expected)
    assert r['hoop_mm'] == calculate_structural(
        dict(case, install_pressure_bar=0), m, 'A', ps_mpa=6)['hoop_mm']
