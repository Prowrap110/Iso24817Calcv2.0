"""Putty input transport preserves per-repair overrides and legacy workbooks."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from prowrap_v2 import batch
from test_batch import _add, _inputs, _pack, _set_defaults
from test_pressure_batch import remove_fields


PUTTY = "putty_kg_per_repair"


def test_putty_override_is_visible_without_hiding_existing_inputs():
    book = load_workbook(BytesIO(batch.template_workbook()))
    setup = book[batch.SETUP]
    setup_rows = {setup.cell(row, 3).value: row for row in range(10, setup.max_row + 1)}
    assert PUTTY in setup_rows
    assert setup.cell(setup_rows[PUTTY], 2).value is None
    assert setup.cell(setup_rows[PUTTY], 4).value is None
    assert setup["B120"].value is None
    assert setup["B121"].value is None
    assert all(setup.cell(row, 4).alignment.horizontal == "center"
               for row in range(9, setup.max_row + 1))
    for title in (batch.LINES, batch.CASES):
        sheet = book[title]
        columns = {cell.value: cell.column for cell in sheet[3]}
        assert PUTTY in columns
        assert columns[PUTTY] == columns["quantity"] + 1
        assert not sheet.column_dimensions[sheet.cell(3, columns[PUTTY]).column_letter].hidden
        assert sheet.cell(4, columns[PUTTY]).comment is not None
    assert book[batch.LINES]["B3"].value == "quantity"
    assert not book[batch.LINES].column_dimensions["Y"].hidden


def test_putty_override_precedence_and_quantity_are_applied_once():
    book = _inputs(batch)
    _set_defaults(book, putty_kg_per_repair=4.5)
    _add(book, batch.LINES, line_id="A", quantity=7, putty_kg_per_repair=3.5)
    _add(book, batch.CASES, repair_id="BATCH", quantity=2)
    _add(book, batch.CASES, row=6, repair_id="LINE", line_id="A")
    _add(book, batch.CASES, row=7, repair_id="REPAIR", line_id="A", putty_kg_per_repair=1.25)
    _add(book, batch.CASES, row=8, repair_id="ZERO", line_id="A", putty_kg_per_repair=0)
    prepared = batch.prepare_workbook(_pack(book))
    assert [repair.case[PUTTY] for repair in prepared.repairs] == [4.5, 3.5, 1.25, 0]
    assert [repair.origins[PUTTY] for repair in prepared.repairs] == [
        "Batch Setup", "Line Defaults · A", "Repair Cases · row 7", "Repair Cases · row 8",
    ]
    output, results = batch.calculate_batch(prepared)
    assert [record["status"] for record in results] == ["CALCULATED"] * 4
    assert [record["results"]["putty_per_repair_kg"] for record in results] == [4.5, 3.5, 1.25, 0]
    assert [record["results"]["putty_kg"] for record in results] == [9, 24.5, 8.75, 0]
    exported = load_workbook(BytesIO(output), data_only=True)
    sheet = exported["Results"]
    columns = {cell.value: cell.column for cell in sheet[4]}
    assert columns["Putty per defect [kg]"] == columns["Identical repairs"] + 1
    assert [sheet.cell(row, columns["Putty per defect [kg]"]).value for row in range(5, 9)] == [4.5, 3.5, 1.25, 0]
    assert exported["Summary and Cost"]["F5"].value == 42.25


@pytest.mark.parametrize("scope", [batch.SETUP, batch.LINES, batch.CASES])
@pytest.mark.parametrize("value", [-0.1, "nan", "inf", "-inf", True])
def test_invalid_putty_override_is_reported_before_calculation(scope, value):
    book = _inputs(batch)
    _add(book, batch.CASES, repair_id="BAD", line_id="A")
    _add(book, batch.LINES, line_id="A")
    if scope == batch.SETUP:
        _set_defaults(book, putty_kg_per_repair=value)
    else:
        _add(book, scope, putty_kg_per_repair=value)
    prepared = batch.prepare_workbook(_pack(book))
    assert prepared.repairs[0].issues
    assert any("Putty" in issue for issue in prepared.repairs[0].issues)
    _, results = batch.calculate_batch(prepared)
    assert results[0]["status"] == "INPUT_ERROR"
    assert not results[0]["results"]


def test_valid_explicit_zero_can_override_an_invalid_inherited_putty_value():
    book = _inputs(batch)
    _set_defaults(book, putty_kg_per_repair=-1)
    _add(book, batch.LINES, line_id="A", putty_kg_per_repair=-2)
    _add(book, batch.CASES, repair_id="ZERO", line_id="A", putty_kg_per_repair=0)
    prepared = batch.prepare_workbook(_pack(book))
    assert not prepared.repairs[0].issues
    assert len(prepared.warnings) == 2
    _, results = batch.calculate_batch(prepared)
    assert results[0]["status"] == "CALCULATED"
    assert results[0]["results"]["putty_kg"] == 0


@pytest.mark.parametrize("earlier_fields", [set(), {"axial_mawp_bar"},
    {"pressure_basis", "maop_bar"}, {"pressure_basis", "maop_bar", "axial_mawp_bar"}])
def test_previous_workbook_without_putty_override_uses_automatic_quantity(earlier_fields):
    book = _inputs(batch)
    _add(book, batch.CASES, repair_id="OLD", quantity=3)
    remove_fields(book, {PUTTY} | earlier_fields)
    prepared = batch.prepare_workbook(_pack(book))
    assert prepared.repairs[0].case[PUTTY] is None
    _, results = batch.calculate_batch(prepared)
    assert results[0]["status"] == "CALCULATED"
    assert results[0]["results"]["putty_per_repair_kg"] == 2
    assert results[0]["results"]["putty_kg"] == 6


def test_batch_preview_shows_resolved_putty_and_zero():
    book = _inputs(batch)
    _set_defaults(book, putty_kg_per_repair=4)
    _add(book, batch.CASES, repair_id="INHERITED")
    _add(book, batch.CASES, row=6, repair_id="ZERO", putty_kg_per_repair=0)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "batch_app.py"), default_timeout=20).run()
    app.get("file_uploader")[0].upload("putty.xlsx", _pack(book)).run()
    assert not app.exception
    label = batch.FIELD_DEFINITIONS[PUTTY]["label"]
    assert list(app.dataframe[0].value[label]) == [4, 0]
    app.button[0].click().run()
    assert not app.exception
    assert next(metric.value for metric in app.metric if metric.label == "Calculated") == "2"
