"""Conditional form display, never a substitute for engine validation."""

from math import isfinite

from .schema import FIELD_DEFINITIONS, default_case

OPENING_FIELDS = (
    "seal_shape", "effective_diameter_mm", "effective_axial_mm",
    "effective_circ_mm", "effective_geometry_ref", "stopgap_ref",
)


def uses_measured_defects(case):
    return (
        case.get("mechanism") == "Corrosion"
        and case.get("defect_location") == "External"
        and case.get("defect_mode") == "Measured individual"
    )


def likely_type_b(case, defects=()):
    if case.get("through_wall") or case.get("prevent_containment") or case.get("mechanism") == "Leak":
        return True
    remaining = case.get("remaining_wall_mm")
    if uses_measured_defects(case):
        measured = [
            value for defect in defects if isinstance(value := defect.get("remaining_wall_mm"), (int, float))
            and not isinstance(value, bool) and isfinite(value)
        ]
        if measured:
            remaining = min(measured)
    basis = case.get("growth_basis")
    if basis == "Assessed end-of-life":
        remaining = case.get("eol_wall_mm")
    elif basis == "Corrosion rate" and remaining is not None:
        remaining -= (case.get("corrosion_rate_mm_year") or 0) * (case.get("design_life_years") or 0)
    return remaining is not None and remaining < 1


def active_fields(case, defects=()):
    active = set(FIELD_DEFINITIONS)

    def hide(*keys):
        active.difference_update(keys)

    if case.get("component") != "Tee":
        hide("run_od_mm", "branch_od_mm")
    if case.get("component") == "Straight":
        hide("component_qualified", "component_ref")

    if case.get("growth_basis") != "Corrosion rate":
        hide("corrosion_rate_mm_year")
    if case.get("growth_basis") != "Assessed end-of-life":
        hide("eol_wall_mm")
    if case.get("mechanism") != "Corrosion" or case.get("defect_location") != "External":
        hide("defect_mode", "independence_confirmed", "grouping_ref")
    elif case.get("defect_mode") == "Actual / combined":
        hide("independence_confirmed", "grouping_ref")

    if case.get("mechanism") != "Dent no-crack":
        hide("dent_mode", "no_crack_confirmed", "dent_ffs_ref", "dent_mawp_bar")
        if case.get("mechanism") != "Dent w/crack":
            hide("dent_depth_mm", "dent_complex", "fatigue_assessment_ref")
    elif case.get("dent_mode") == "60/40 population" and case.get("purpose") == "Estimate":
        hide("defect_length_mm", "defect_width_mm", "dent_depth_mm", "zone_length_mm")

    if not likely_type_b(case, defects):
        hide(*OPENING_FIELDS)
    elif case.get("seal_shape") == "Circular":
        hide("effective_axial_mm", "effective_circ_mm")
    else:
        hide("effective_diameter_mm")

    if case.get("load_basis") != "Additional loads":
        hide("axial_kn", "shear_kn", "bending_knm", "torsion_knm")
    if not case.get("cyclic"):
        hide("cycles", "cycle_min_bar", "cycle_max_bar")
    if not case.get("external_pressure") and not case.get("reversing_loads"):
        hide("external_assessment_ref")

    if case.get("mechanism") == "Dent no-crack":
        hide("substrate_route", "sharing_basis", "ffs_method", "ffs_ref",
             "assessed_mawp_bar", "b31g_safety_factor", "smts_mpa")
    elif case.get("substrate_route") == "Full laminate":
        hide(
            "sharing_basis", "ffs_method", "ffs_ref", "assessed_mawp_bar", "axial_mawp_bar", "assessed_axial_capacity_kn",
            "qualified_wall_loss_pct", "qualification_ref", "b31g_safety_factor", "original_design_factor",
            "smts_mpa", "allowable_stress_mpa",
        )
    else:
        if case.get("substrate_route") != "Substrate sharing":
            hide("sharing_basis")
        if case.get("ffs_method") != "Modified B31G":
            hide("b31g_safety_factor")
        else:
            hide("assessed_mawp_bar")

    if case.get("landing_mode") != "Restricted":
        hide("landing_left_mm", "landing_right_mm")
    return [key for key in FIELD_DEFINITIONS if key in active]


def case_for_calculation(case, defects=()):
    """Exclude inactive form values from the submitted engineering case."""
    active = active_fields(case, defects)
    submitted = default_case()
    submitted.update({key: case[key] for key in active if key in case})
    if submitted.get("mechanism") == "Dent no-crack":
        submitted.update(substrate_route="Substrate stress limit", ffs_method="External assessment")
    return submitted
