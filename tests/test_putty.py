"""Owner-approved putty estimates and per-defect consumption overrides."""
import pytest

from prowrap_v2.engine import evaluate_case, expand_population
from test_engine import valid_case


@pytest.mark.parametrize("product", ["PRW110+", "PRW110"])
@pytest.mark.parametrize("zone, expected_kg", [
    (100, 2), (200, 2), (200.01, 3), (400, 3),
    (400.01, 4), (600, 4), (600.01, 5), (800, 5),
])
def test_corrosion_putty_counts_each_started_200_mm_of_zone(product, zone, expected_kg):
    case = valid_case()
    case.update(product=product, zone_length_mm=zone)
    result = evaluate_case(case)
    assert result["status"] == "CALCULATED", result
    assert result["results"]["putty_kg"] == expected_kg
    assert result["results"]["putty_per_repair_kg"] == expected_kg


def test_corrosion_putty_uses_defect_length_when_zone_is_blank():
    case = valid_case()
    case.update(defect_length_mm=401, zone_length_mm=None, quantity=3)
    result = evaluate_case(case)
    assert result["status"] == "CALCULATED", result
    assert result["results"]["putty_per_repair_kg"] == 4
    assert result["results"]["putty_kg"] == 12


def dent_case():
    case = valid_case()
    case.update(mechanism="Dent no-crack", dent_depth_mm=12,
                defect_length_mm=300, defect_width_mm=100, zone_length_mm=300,
                no_crack_confirmed=True, dent_ffs_ref="Dent assessment",
                dent_mawp_bar=35, remaining_wall_mm=10, original_design_factor=.72)
    return case


@pytest.mark.parametrize("product", ["PRW110+", "PRW110"])
def test_dent_putty_uses_one_third_geometric_volume_at_existing_density(product):
    case = dent_case()
    case.update(product=product, quantity=4)
    result = evaluate_case(case)
    assert result["status"] == "CALCULATED", result
    # 300 x 100 x 12 mm = 0.36 L; one third x 2 kg/L = 0.24 kg/defect.
    assert result["results"]["putty_per_repair_kg"] == pytest.approx(.24)
    assert result["results"]["putty_kg"] == pytest.approx(.96)


@pytest.mark.parametrize("make_case, automatic_kg", [(valid_case, 2), (dent_case, .24)])
def test_blank_putty_override_keeps_automatic_estimate(make_case, automatic_kg):
    case = make_case()
    assert case["putty_kg_per_repair"] is None
    result = evaluate_case(case)
    assert result["status"] == "CALCULATED", result
    assert result["results"]["putty_kg"] == pytest.approx(automatic_kg)


@pytest.mark.parametrize("make_case", [valid_case, dent_case])
@pytest.mark.parametrize("override, expected_total", [(0, 0), (1.25, 5)])
def test_putty_override_scales_once_and_leaves_engineering_unchanged(make_case, override, expected_total):
    case = make_case()
    case["quantity"] = 4
    automatic = evaluate_case(case)
    case["putty_kg_per_repair"] = override
    result = evaluate_case(case)
    assert result["status"] == "CALCULATED", result
    outputs = result["results"]
    assert outputs["putty_per_repair_kg"] == override
    assert outputs["putty_kg"] == expected_total
    assert outputs["total_epoxy_kg"] == pytest.approx(outputs["laminate_epoxy_kg"] + expected_total)
    for key in ("installed_plies", "installed_thickness_mm", "total_repair_length_mm",
                "count_500", "count_300", "fabric_area_m2", "laminate_epoxy_kg"):
        assert outputs[key] == automatic["results"][key]


@pytest.mark.parametrize("value", [-.01, float("nan"), float("inf"), -float("inf"), True, "2"])
def test_invalid_putty_override_blocks_material_schedule(value):
    case = valid_case()
    case["putty_kg_per_repair"] = value
    result = evaluate_case(case)
    assert result["status"] == "INPUT_ERROR", result
    assert not result["results"]
    assert any("putty" in issue.lower() for issue in result["issues"])


def test_dent_population_override_preserves_total_count_and_scales_once():
    case = dent_case()
    case.update(dent_mode="60/40 population", purpose="Estimate", quantity=7,
                putty_kg_per_repair=1.25)
    results = [evaluate_case(group) for group in expand_population(case)]
    assert all(result["status"] == "ESTIMATE" for result in results), results
    assert sum(result["results"]["quantity"] for result in results) == 7
    assert sum(result["results"]["putty_kg"] for result in results) == 8.75
    assert all(result["results"]["putty_per_repair_kg"] == 1.25 for result in results)
