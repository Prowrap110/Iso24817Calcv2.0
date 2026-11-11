from importlib import import_module
from io import BytesIO

import pytest
from openpyxl import load_workbook

from prowrap_v2.schema import default_case


@pytest.fixture
def batch():
    return import_module("prowrap_v2.batch")


def _set_defaults(book, **values):
    sheet = book["Batch Setup"]
    rows = {sheet.cell(row, 3).value: row for row in range(1, sheet.max_row + 1)}
    for key, value in values.items():
        sheet.cell(rows[key], 2, value)


def _add(book, sheet_name, row=5, **values):
    sheet = book[sheet_name]
    cols = {cell.value: cell.column for cell in sheet[3]}
    for key, value in values.items():
        sheet.cell(row, cols[key], value)


def _pack(book):
    content = BytesIO()
    book.save(content)
    return content.getvalue()


def _inputs(batch):
    book = load_workbook(BytesIO(batch.template_workbook()))
    _set_defaults(
        book,
        customer="Operator", project="North site", pressure_bar=40, min_pressure_bar=0,
        temperature_c=50, min_temperature_c=15, install_pressure_bar=0, install_temperature_c=20,
        growth_basis="No growth confirmed", growth_ref="INS-01",
        load_basis="Pressure-only confirmed", landing_mode="Unrestricted confirmed",
        od_mm=323.9, wall_mm=9.53, smys_mpa=359, remaining_wall_mm=7,
        defect_length_mm=75, defect_width_mm=45,
    )
    return book


def test_template_is_editable_xlsx_with_documented_headers(batch):
    book = load_workbook(BytesIO(batch.template_workbook()))
    assert book.sheetnames == [
        "Batch Setup", "Line Defaults", "Repair Cases", "Defect Details", "Load and Engineering Details",
    ]
    assert book["Batch Setup"]["B1"].value == "ISO 24817:2026"
    assert "Repair ID" in [cell.value for cell in book["Repair Cases"][4]]
    assert book["Repair Cases"].freeze_panes == "C5"
    assert len(book["Repair Cases"].data_validations.dataValidation) > 0


def test_preview_preserves_override_precedence_and_zero(batch):
    book = _inputs(batch)
    _add(book, "Line Defaults", line_id="A", pressure_bar=55, install_pressure_bar=15)
    _add(book, "Repair Cases", repair_id="R-01", line_id="A", install_pressure_bar=0)
    prepared = batch.prepare_workbook(_pack(book))
    repair = prepared.repairs[0]
    assert repair.case["customer"] == "Operator"
    assert repair.case["pressure_bar"] == 55
    assert repair.case["install_pressure_bar"] == 0
    assert repair.case["asset_id"] == "A"
    assert repair.origins["customer"] == "Batch Setup"
    assert repair.origins["pressure_bar"] == "Line Defaults · A"
    assert repair.origins["install_pressure_bar"] == "Repair Cases · row 5"
    assert repair.origins["product"] == "Calculator default"
    assert repair.case["corrosion_rate_mm_year"] is None
    assert repair.issues == []


def test_linked_measured_defects_and_loads_match_single_evaluator(batch):
    from prowrap_v2.engine import evaluate_case

    book = _inputs(batch)
    _add(book, "Repair Cases", repair_id="MEASURED", defect_mode="Measured individual",
         zone_length_mm=180, independence_confirmed=True, grouping_ref="INS-01")
    _add(book, "Defect Details", repair_id="MEASURED", defect_id="D-01", length_mm=12,
         width_mm=9, remaining_wall_mm=7, separation_mm=50, independence_confirmed=True)
    _add(book, "Load and Engineering Details", repair_id="MEASURED", load_id="L-01",
         axial_kn=1, shear_kn=0, bending_knm=0, torsion_knm=0, loads_ref="LOAD-01")
    prepared = batch.prepare_workbook(_pack(book))
    repair = prepared.repairs[0]
    assert repair.defects == [{
        "defect_id": "D-01", "length_mm": 12.0, "width_mm": 9.0,
        "remaining_wall_mm": 7.0, "separation_mm": 50.0, "independence_confirmed": True,
    }]
    assert repair.loads == [{
        "load_id": "L-01", "axial_kn": 1.0, "shear_kn": 0.0, "bending_knm": 0.0,
        "torsion_knm": 0.0, "loads_ref": "LOAD-01",
    }]
    direct_case = default_case()
    direct_case.update(
        repair_id="MEASURED", customer="Operator", project="North site", pressure_bar=40,
        min_pressure_bar=0, temperature_c=50, min_temperature_c=15, install_pressure_bar=0,
        install_temperature_c=20, growth_basis="No growth confirmed", growth_ref="INS-01",
        load_basis="Pressure-only confirmed", landing_mode="Unrestricted confirmed", od_mm=323.9,
        wall_mm=9.53, smys_mpa=359, remaining_wall_mm=7, defect_length_mm=75, defect_width_mm=45,
        defect_mode="Measured individual", zone_length_mm=180, independence_confirmed=True,
        grouping_ref="INS-01",
    )
    expected = evaluate_case(direct_case, repair.defects, repair.loads)
    output, results = batch.process_workbook(_pack(book))
    assert expected["status"] == "CALCULATED", expected["issues"]
    assert results == [expected]
    wb = load_workbook(BytesIO(output))
    assert wb["Results"]["A5"].value == "MEASURED"
    assert wb["Results"]["D5"].value == "CALCULATED"


def test_invalid_rows_isolated_and_orphans_audited(batch):
    book = _inputs(batch)
    _add(book, "Repair Cases", repair_id="DUP")
    _add(book, "Repair Cases", row=6, repair_id="DUP")
    _add(book, "Repair Cases", row=7, repair_id="FORMULA", pressure_bar="=40")
    _add(book, "Repair Cases", row=8, repair_id="NAN", remaining_wall_mm="NaN")
    _add(book, "Repair Cases", row=9, repair_id="BOOL", through_wall="maybe")
    _add(book, "Repair Cases", row=10, repair_id="NO LINE", line_id="Absent")
    _add(book, "Repair Cases", row=11, repair_id="VALID")
    _add(book, "Defect Details", repair_id="ORPHAN", defect_id="D-01", length_mm=10)
    output, results = batch.process_workbook(_pack(book))
    assert [record["status"] for record in results] == ["INPUT_ERROR"] * 6 + ["CALCULATED"]
    assert all(record["results"] == {} for record in results[:6])
    wb = load_workbook(BytesIO(output))
    warnings = [str(cell.value) for row in wb["Warnings"].iter_rows() for cell in row]
    for word in ("Duplicate", "formula", "finite", "Yes or No", "Unknown Line", "ORPHAN"):
        assert any(word in warning for warning in warnings)


def test_text_is_preserved_without_exporting_a_formula(batch):
    book = _inputs(batch)
    _add(book, "Repair Cases", repair_id="=1+1")
    book["Repair Cases"]["A5"].data_type = "s"
    output, results = batch.process_workbook(_pack(book))
    assert results[0]["repair_id"] == "=1+1"
    wb = load_workbook(BytesIO(output), data_only=False)
    assert wb["Results"]["A5"].value == "=1+1"
    assert wb["Results"]["A5"].data_type == "s"
    # Formula-driven pricing is authored only on the commercial summary. Input
    # text remains literal everywhere, including identifiers starting with '='.
    assert not any(cell.data_type == "f" for sheet in wb if sheet.title != "Summary and Cost" for row in sheet for cell in row)


def test_case_level_details_override_defaults_but_conflicts_fail(batch):
    book = _inputs(batch)
    _add(book, "Repair Cases", repair_id="R-01", install_pressure_bar=10)
    _add(book, "Repair Cases", row=6, repair_id="R-02")
    _add(book, "Load and Engineering Details", repair_id="R-01", install_pressure_bar=5)
    _add(book, "Load and Engineering Details", row=6, repair_id="R-02", install_pressure_bar=0)
    prepared = batch.prepare_workbook(_pack(book))
    assert "Conflicting" in " ".join(prepared.repairs[0].issues)
    assert prepared.repairs[1].case["install_pressure_bar"] == 0
    assert prepared.repairs[1].origins["install_pressure_bar"] == "Load and Engineering Details · row 6"


def test_batch_commercial_totals_exclude_invalid_quantities(batch):
    book = _inputs(batch)
    _set_defaults(book, currency="EUR", fabric_rate=20, epoxy_rate=10)
    _add(book, "Repair Cases", repair_id="GOOD", quantity=3)
    _add(book, "Repair Cases", row=6, repair_id="BAD", quantity=0)
    output, results = batch.process_workbook(_pack(book))
    valid = results[0]["results"]
    assert results[0]["status"] == "CALCULATED", results[0]["issues"]
    assert results[1]["status"] == "INPUT_ERROR"
    wb = load_workbook(BytesIO(output), data_only=True)
    summary = wb["Summary and Cost"]
    assert summary["A5"].value == "CALCULATED"
    assert summary["C5"].value == 3
    assert summary["D5"].value == pytest.approx(valid["fabric_area_m2"])
    assert summary["H5"].value == pytest.approx(valid["fabric_area_m2"] * 20 + valid["total_epoxy_kg"] * 10)
    assert summary["H7"].value is None


def test_population_expansion_preserves_quantity(batch):
    book = _inputs(batch)
    _add(book, "Repair Cases", repair_id="DENT", mechanism="Dent no-crack",
         dent_mode="60/40 population", purpose="Estimate", quantity=7,
         remaining_wall_mm=9.53, no_crack_confirmed=True, inspection_ref="INS-DENT",
         dent_ffs_ref="DENT-FFS", dent_mawp_bar=40, original_design_factor=.72)
    output, results = batch.process_workbook(_pack(book))
    assert len(results) == 2
    assert all(result["status"] == "ESTIMATE" for result in results), results
    assert sorted(result["results"]["quantity"] for result in results) == [3, 4]
    summary = load_workbook(BytesIO(output), data_only=True)["Summary and Cost"]
    assert summary["C6"].value == 7


def test_invalid_file_requires_current_template(batch):
    with pytest.raises(batch.WorkbookError, match="Excel"):
        batch.prepare_workbook(b"not Excel")


def test_named_line_formula_does_not_fall_through_to_batch_default(batch):
    book = _inputs(batch)
    _add(book, "Line Defaults", line_id="A", pressure_bar="=1+1")
    _add(book, "Repair Cases", repair_id="BAD", line_id="A")
    _add(book, "Repair Cases", row=6, repair_id="OVERRIDDEN", line_id="A", pressure_bar=35)
    _add(book, "Repair Cases", row=7, repair_id="OTHER")
    _, results = batch.process_workbook(_pack(book))
    assert [result["status"] for result in results] == ["INPUT_ERROR", "CALCULATED", "CALCULATED"]
    assert results[1]["inputs"]["pressure_bar"] == 35
    assert results[2]["inputs"]["pressure_bar"] == 40


def test_repeated_child_ids_and_wrong_detail_scope_fail_parent_only(batch):
    book = _inputs(batch)
    _add(book, "Repair Cases", repair_id="BAD")
    _add(book, "Repair Cases", row=6, repair_id="VALID")
    _add(book, "Defect Details", repair_id="BAD", defect_id="D1", length_mm=15)
    _add(book, "Defect Details", row=6, repair_id="bad", defect_id="d1", length_mm=15)
    _add(book, "Load and Engineering Details", repair_id="BAD", load_id="L1",
         pressure_bar=30, install_pressure_bar=0)
    _, results = batch.process_workbook(_pack(book))
    assert [result["status"] for result in results] == ["INPUT_ERROR", "CALCULATED"]
    assert any("Duplicate Defect ID" in issue for issue in results[0]["issues"])
    assert any("separate row" in issue for issue in results[0]["issues"])


def test_mislabeled_input_column_requires_fresh_template(batch):
    book = _inputs(batch)
    book["Repair Cases"]["I4"].value = "Nominal wall [mm]"
    with pytest.raises(batch.WorkbookError, match="columns changed"):
        batch.prepare_workbook(_pack(book))


def test_population_generated_id_collision_is_audited(batch):
    book = _inputs(batch)
    _add(book, "Repair Cases", repair_id="DENT", mechanism="Dent no-crack",
         dent_mode="60/40 population", purpose="Estimate", quantity=7)
    _add(book, "Repair Cases", row=6, repair_id="DENT-D60")
    output, results = batch.process_workbook(_pack(book))
    assert [result["status"] for result in results] == ["INPUT_ERROR", "INPUT_ERROR"]
    assert all(not result["results"] for result in results)
    assert all(any("conflicts" in issue for issue in result["issues"]) for result in results)
    summary = load_workbook(BytesIO(output), data_only=True)["Summary and Cost"]
    assert summary["C6"].value is None


def test_template_handles_full_batch_and_more_than_150_linked_defects(batch):
    book = _inputs(batch)
    _add(book, "Line Defaults", line_id="SHARED", pressure_bar=40)
    for number in range(150):
        _add(book, "Repair Cases", row=5 + number, repair_id=f"R-{number}", line_id="SHARED",
             defect_mode="Measured individual", zone_length_mm=180,
             independence_confirmed=True, grouping_ref="INS-01")
        for index in range(2):
            _add(book, "Defect Details", row=5 + number * 2 + index, repair_id=f"R-{number}",
                 defect_id=f"D-{index}", length_mm=12, width_mm=9,
                 remaining_wall_mm=7, separation_mm=50)
    output, results = batch.process_workbook(_pack(book))
    assert len(results) == 150
    assert all(result["status"] == "CALCULATED" for result in results)
    summary = load_workbook(BytesIO(output), read_only=True)["Summary and Cost"]
    assert summary["C5"].value == 150
