from io import BytesIO

from openpyxl import Workbook, load_workbook

from prowrap_v2.commercial import COMMERCIAL_INPUTS, add_commercial_summary, commercial_groups


def result(status="CALCULATED", mechanism="Corrosion", quantity=2, area=10, saturator=20, putty=4):
    return {"status": status, "inputs": {"mechanism": mechanism}, "results": {
        "quantity": quantity, "fabric_area_m2": area, "laminate_epoxy_kg": saturator, "putty_kg": putty,
    }}


def exported(results, rates=None):
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Summary and Cost"
    sheet.protection.sheet = True
    add_commercial_summary(sheet, results, rates or {})
    content = BytesIO()
    wb.save(content)
    return load_workbook(BytesIO(content.getvalue()))


def test_only_valid_cases_are_priced_without_mixing_status_or_mechanism():
    rows = [
        result(), result(quantity=3, area=5, saturator=10, putty=1),
        result("ESTIMATE", "Dent no-crack", quantity=4),
        result("CALCULATED", "Leak", quantity=1),
        result("ENGINEERING_HOLD", quantity=900, area=900),
        result("INPUT_ERROR", quantity=900, area=900),
        result("NO_VALID_DESIGN", quantity=900, area=900),
    ]
    grouped = commercial_groups(rows)
    assert grouped["CALCULATED", "Corrosion"] == [2, 5, 15, 30, 5]
    assert grouped["ESTIMATE", "Dents"] == [1, 4, 10, 20, 4]
    assert grouped["CALCULATED", "Other"] == [1, 1, 10, 20, 4]
    assert len(grouped) == 3
    sheet = exported(rows)["Summary and Cost"]
    assert [sheet.cell(28, c).value for c in range(3, 8)] == [2, 5, 15, 30, 5]
    assert [sheet.cell(32, c).value for c in range(3, 8)] == [1, 4, 10, 20, 4]


def test_all_price_controls_are_blank_and_editable_even_with_legacy_rates():
    wb = exported([result()], {"currency": "EUR", "fabric_rate": 20, "epoxy_rate": 30})
    sheet = wb["Summary and Cost"]
    for row in COMMERCIAL_INPUTS:
        assert sheet.cell(row, 2).value is None
        assert sheet.cell(row, 2).protection.locked is False
    assert sheet["B19"].value == 30
    assert "EUR/kg" in sheet["C19"].value
    assert sheet["B19"].protection.locked is True
    assert "kg rate" in sheet["H4"].value
    for row in range(28, 34):
        for col in (8, 9):
            assert sheet.cell(row, col).value is None
            assert sheet.cell(row, col).protection.locked is False
    assert wb.calculation.calcMode == "auto"
    assert wb.calculation.fullCalcOnLoad


def test_formula_dependencies_keep_volume_rate_separate_from_legacy_mass_rate():
    sheet = exported([result()])["Summary and Cost"]
    formulas = {cell.coordinate: cell.value for row in sheet for cell in row if cell.data_type == "f"}
    assert len(formulas) > 50
    assert not any("$B$19" in formula for formula in formulas.values())
    assert "$B$14" in formulas["M28"]
    assert "$B$15" in formulas["N28"]
    assert "$B$16" in formulas["P28"]
    assert "$B$17" in formulas["J28"] and "F28/" in formulas["J28"]
    assert "$B$18" in formulas["K28"] and "G28/" in formulas["K28"]
    assert 'ISNUMBER(H28)' in formulas["J28"] and "H28>=0" in formulas["J28"]
    assert 'ISNUMBER(I28)' in formulas["K28"] and "I28>=0" in formulas["K28"]
    assert 'ISNUMBER($B$15)' in formulas["N28"] and "$B$15>=0" in formulas["N28"]
    assert 'COUNT(D38:D41)=4' in formulas["D42"]
    assert 'COUNT(D44:D45)=2' in formulas["D46"]
    assert {str(dv.sqref) for dv in sheet.data_validations.dataValidation} == {"B17:B18", "B14:B16 B20:B22 H28:I33"}


def test_external_legacy_currency_stays_literal():
    sheet = exported([result()], {"currency": "=1+1", "epoxy_rate": 30})["Summary and Cost"]
    assert sheet["C19"].data_type == "s"
    assert sheet["C19"].value == "=1+1/kg · reference only"
