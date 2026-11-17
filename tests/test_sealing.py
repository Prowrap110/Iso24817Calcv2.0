import pytest

from prowrap_v2.sealing import leak_factor, solve_seal


MATERIAL = dict(ec_mpa=45460, ea_mpa=43800, nu=.066, g_mpa=2450, gamma_n_mm=.250)


def case(pressure_bar, **overrides):
    data = dict(
        od_mm=323.9, wall_mm=10, seal_shape='Circular',
        effective_diameter_mm=30, pressure_bar=pressure_bar,
        repair_class=3, design_life_years=2,
    )
    data.update(overrides)
    return data


@pytest.mark.parametrize(('repair_class', 'expected'), [
    (1, .33293395690491223), (2, .33298238788147410), (3, .33305367425907840),
])
def test_equation_16_default_service_factors(repair_class, expected):
    assert leak_factor(repair_class, 20) == pytest.approx(expected)


def test_equation_12_fifty_bar_witness():
    result = solve_seal(case(50), MATERIAL, 1, .79375)

    assert result['equation'] == 12
    assert result['f_leak_equation'] == 16
    assert result['f_leak'] == pytest.approx(.6421466617330162)
    assert result['seal_mm'] == pytest.approx(7.926815252)
    assert result['asymptote_mpa'] == pytest.approx(17.459271793)


def test_smaller_circle_accepts_60_point_3_mm_substrate():
    result = solve_seal(case(1, od_mm=60.3, effective_diameter_mm=15), MATERIAL, 1, .7)

    assert result['seal_mm'] == pytest.approx(.109711800)


def test_circle_continues_to_use_15_mm_minimum_design_opening():
    result = solve_seal(case(1, effective_diameter_mm=3), MATERIAL, 1, .7)

    assert result['effective_size_mm'] == 15


def test_solver_uses_geometry_already_adopted_by_caller():
    result = solve_seal(case(1, effective_diameter_mm=30.01), MATERIAL, 1, .7)

    assert result['effective_size_mm'] == 30.01


def test_circle_at_asymptote_has_no_finite_solution():
    result = solve_seal(case(50), MATERIAL, 1, .79375)

    with pytest.raises(ValueError, match='finite'):
        solve_seal(case(10 * result['asymptote_mpa']), MATERIAL, 1, .79375)


def test_circle_geometry_limit():
    opening = case(10, od_mm=609.6, wall_mm=9.53, effective_diameter_mm=200)

    with pytest.raises(ValueError, match='geometry'):
        solve_seal(opening, MATERIAL, 1, 1)


def test_circle_must_enclose_whole_footprint():
    opening = case(10, effective_axial_mm=20, effective_circ_mm=25)

    with pytest.raises(ValueError, match='enclose'):
        solve_seal(opening, MATERIAL, 1, 1)


def test_circumferential_slot_selects_equation_14_from_annex_k_inputs():
    # ISO 24817:2017 Annex K worked example 2 inputs. The printed 5.06 mm
    # does not reproduce from these inputs. Eqs. (13)/(14) give 8.8875/5.4526 mm.
    material = dict(ec_mpa=24000, ea_mpa=8000, nu=.27, g_mpa=2000, gamma_n_mm=.227)
    opening = case(
        10, od_mm=168.3, wall_mm=7.1, repair_class=2, design_life_years=5,
        seal_shape='Circumferential slot', effective_axial_mm=50,
    )

    result = solve_seal(opening, material, 1, .71875)

    assert result['equation'] == 14
    assert result['seal_mm'] == pytest.approx(5.452598644)
    assert result['asymptote_mpa'] is None


def test_circumferential_slot_selects_equation_13_when_thinner():
    opening = case(50, seal_shape='Circumferential slot', effective_axial_mm=20)

    result = solve_seal(opening, MATERIAL, 1, 1)

    assert result['equation'] == 13
    assert result['seal_mm'] == pytest.approx(7.118142547)


def test_circumferential_slot_equation_14_has_no_asymptote():
    opening = case(90, seal_shape='Circumferential slot', effective_axial_mm=200)

    result = solve_seal(opening, MATERIAL, 1, .7)

    assert result['equation'] == 14
    assert result['seal_mm'] == pytest.approx(471.260033644)
    assert result['asymptote_mpa'] is None


def test_axial_slot_applies_corrected_equation_15():
    opening = case(20, od_mm=200, seal_shape='Axial slot', effective_circ_mm=95)

    result = solve_seal(opening, MATERIAL, 1, .7)

    assert result['equation'] == 15
    assert result['seal_mm'] == pytest.approx(20.221404506)


@pytest.mark.parametrize('width', [100, 105])
def test_axial_slot_rejects_angle_of_one_radian_or_more(width):
    opening = case(1, od_mm=200, seal_shape='Axial slot', effective_circ_mm=width)

    with pytest.raises(ValueError, match='radian'):
        solve_seal(opening, MATERIAL, 1, 1)


def test_equation_28_replaces_service_factor_in_active_cyclic_loading():
    result = solve_seal(case(10, cyclic=True, cycles=100000), MATERIAL, .5, .79375)

    assert result['f_leak_equation'] == 28
    assert result['f_leak'] == pytest.approx(.1665)
    assert result['seal_mm'] == pytest.approx(5.11884809298)


def test_cyclic_loading_below_threshold_uses_equation_16():
    result = solve_seal(case(10, cyclic=True, cycles=6999), MATERIAL, 1, .79375)

    assert result['f_leak_equation'] == 16
    assert result['f_leak'] == pytest.approx(.6421466617330162)


def test_optional_qualified_degradation_factor_selects_equation_17():
    material = dict(MATERIAL, leak_degradation_factor=.45)
    result = solve_seal(case(10), material, 1, .79375)

    assert result['f_leak_equation'] == 17
    assert result['f_leak'] == pytest.approx(.2997)
    assert result['seal_mm'] == pytest.approx(2.475692247)


@pytest.mark.parametrize(('key', 'value'), [
    ('ec_mpa', -45460), ('g_mpa', 0), ('gamma_n_mm', float('nan')), ('nu', 1),
])
def test_invalid_sealing_material_cannot_produce_thickness(key, value):
    with pytest.raises(ValueError):
        solve_seal(case(10), dict(MATERIAL, **{key: value}), 1, .79375)
