from prowrap_v2.schema import default_case
from prowrap_v2.ui_logic import active_fields

def test_routine_corrosion_hides_dent_and_sealing_fields():
    case=default_case()
    fields=active_fields(case)
    assert 'od_mm' in fields and 'pressure_bar' in fields
    assert 'dent_depth_mm' not in fields
    assert 'effective_diameter_mm' not in fields
    assert 'cycles' not in fields

def test_sealed_leak_and_conditional_load_inputs_remain_visible():
    case=default_case();case.update(through_wall=True,cyclic=True,load_basis='Additional loads',landing_mode='Restricted')
    fields=active_fields(case)
    assert {'effective_diameter_mm','cycles','axial_kn','landing_left_mm'} <= set(fields)


def test_structural_assessment_inputs_can_be_entered_with_other_hazards_off():
    case = default_case()
    case.update(substrate_route="Substrate sharing", sharing_basis="Known allowable stress")
    assert {"original_design_factor", "other_thickness_mm", "reversing_loads"} <= set(active_fields(case))


def test_cracked_dent_cannot_hide_dimensions_with_population_preset():
    case = default_case()
    case.update(mechanism="Dent w/crack", dent_mode="60/40 population")
    fields = active_fields(case)
    assert {"defect_length_mm", "defect_width_mm"} <= set(fields)
    assert "dent_mode" not in fields
