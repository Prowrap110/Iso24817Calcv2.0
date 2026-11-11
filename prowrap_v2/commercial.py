"""Editable commercial worksheet; engineering inputs and results stay unchanged."""

from collections import defaultdict

from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.workbook.properties import CalcProperties


COMMERCIAL_INPUTS = {
    13: ("Currency", "e.g. EUR"),
    14: ("Fabric cost", "currency/m²"),
    15: ("Epoxy + putty cost", "currency/L · common rate"),
    16: ("Sales multiplier", "× material cost"),
    17: ("Mixed saturator density", "kg/L"),
    18: ("Mixed putty density", "kg/L"),
    20: ("Additional supplies sale", "currency · optional"),
    21: ("Packaging / FOB addition", "currency · optional"),
    22: ("Freight addition", "currency · optional"),
}
COMMERCIAL_ROWS = (
    (28, "CALCULATED", "Corrosion"),
    (29, "CALCULATED", "Dents"),
    (30, "CALCULATED", "Other"),
    (31, "ESTIMATE", "Corrosion"),
    (32, "ESTIMATE", "Dents"),
    (33, "ESTIMATE", "Other"),
)


def _literal(cell, value):
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"


def _header(sheet, row, labels):
    for col, label in enumerate(labels, 1):
        cell = sheet.cell(row, col)
        _literal(cell, label)
        cell.fill = PatternFill("solid", fgColor="1D4B75")
        cell.font = Font(name="Calibri", size=11, color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.row_dimensions[row].height = 43


def commercial_groups(results):
    """Aggregate only valid quantities, retaining the engineering status."""
    groups = defaultdict(lambda: [0, 0, 0, 0, 0])
    for result in results:
        status = result["status"]
        if status not in {"CALCULATED", "ESTIMATE"}:
            continue
        mechanism = result.get("inputs", {}).get("mechanism")
        kind = "Corrosion" if mechanism == "Corrosion" else "Dents" if mechanism == "Dent no-crack" else "Other"
        group = groups[status, kind]
        quantities = result["results"]
        group[0] += 1
        for index, key in enumerate(("quantity", "fabric_area_m2", "laminate_epoxy_kg", "putty_kg"), 1):
            group[index] += quantities[key]
    return groups


def _volume(row, mass_col, override_col, density_row):
    # A stated zero overrides the mass conversion; a blank override inherits it.
    return (
        f'=IF(C{row}=0,0,IF(ISNUMBER({override_col}{row}),'
        f'IF({override_col}{row}>=0,{override_col}{row},""),IF({override_col}{row}="",'
        f'IF({mass_col}{row}=0,0,IF(AND(ISNUMBER($B${density_row}),$B${density_row}>0),'
        f'{mass_col}{row}/$B${density_row},"")),"")))'
    )


def _optional_sale(row):
    return f'=IF(B{row}="",0,IF(AND(ISNUMBER(B{row}),B{row}>=0),B{row},""))'


def add_commercial_summary(sheet, results, legacy_rates):
    """Append a formula-driven commercial summary with blank editable controls."""
    sheet.parent.calculation = CalcProperties(calcId=191029, fullCalcOnLoad=True, forceFullCalc=True, calcMode="auto")
    _literal(sheet["H4"], "Legacy material cost [kg rate]")
    _header(sheet, 12, ("Commercial input", "Value", "Unit"))
    for row, (label, unit) in COMMERCIAL_INPUTS.items():
        _literal(sheet.cell(row, 1), label)
        _literal(sheet.cell(row, 3), unit)
        cell = sheet.cell(row, 2)
        cell.value = None
        cell.fill = PatternFill("solid", fgColor="FFF2CC")
        cell.protection = Protection(locked=False)
        cell.number_format = "0.000" if row in (17, 18) else "0.00"
    _literal(sheet["A19"], "Legacy epoxy + putty rate")
    sheet["B19"] = legacy_rates.get("epoxy_rate")
    _literal(sheet["C19"], f'{legacy_rates.get("currency", "currency")}/kg · reference only')
    _literal(sheet["A24"], "Amber cells are editable. Blank litre overrides use density conversion. Sale = material cost × multiplier.")
    _literal(sheet["A25"], "Valid batch cases only; estimates remain estimates. Tender population weights and packaging quantities require a project take-off.")
    for row in (24, 25):
        sheet.cell(row, 1).font = Font(name="Calibri", size=10, italic=True, color="62778B")
    _header(sheet, 27, (
        "Status", "Mechanism", "Result rows", "Repair quantity", "Fabric [m²]", "Saturator [kg]",
        "Putty [kg]", "Saturator override [L]", "Putty override [L]", "Saturator [L]", "Putty [L]",
        "Epoxy + putty [L]", "Fabric cost", "Epoxy + putty cost", "Material cost", "Sale price",
    ))
    groups = commercial_groups(results)
    for row, status, kind in COMMERCIAL_ROWS:
        values = [status, kind, *groups[status, kind]]
        for col, value in enumerate(values, 1):
            _literal(sheet.cell(row, col), value)
        for col in (8, 9):
            cell = sheet.cell(row, col)
            cell.fill = PatternFill("solid", fgColor="FFF2CC")
            cell.protection = Protection(locked=False)
        sheet[f"J{row}"] = _volume(row, "F", "H", 17)
        sheet[f"K{row}"] = _volume(row, "G", "I", 18)
        sheet[f"L{row}"] = f'=IF(COUNT(J{row}:K{row})=2,SUM(J{row}:K{row}),"")'
        sheet[f"M{row}"] = (
            f'=IF(C{row}=0,0,IF(AND($B$13<>"",ISNUMBER($B$14),$B$14>=0),E{row}*$B$14,""))'
        )
        sheet[f"N{row}"] = (
            f'=IF(C{row}=0,0,IF(AND($B$13<>"",ISNUMBER($B$15),$B$15>=0,ISNUMBER(L{row})),L{row}*$B$15,""))'
        )
        sheet[f"O{row}"] = f'=IF(COUNT(M{row}:N{row})=2,SUM(M{row}:N{row}),"")'
        sheet[f"P{row}"] = (
            f'=IF(C{row}=0,0,IF(AND(ISNUMBER(O{row}),ISNUMBER($B$16),$B$16>=0),O{row}*$B$16,""))'
        )
        for cells in sheet.iter_rows(min_row=row, max_row=row, min_col=5, max_col=16):
            for cell in cells:
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(vertical="center", horizontal="right")
    _header(sheet, 37, ("Global offer · valid cases", "Repair quantity", "Unit sale price", "Total sale price"))
    for row, title, first, second in ((38, "Corrosion supply", 28, 31), (39, "Dent supply", 29, 32), (40, "Other repair supply", 30, 33)):
        _literal(sheet.cell(row, 1), title)
        sheet[f"B{row}"] = f"=SUM(D{first},D{second})"
        sheet[f"D{row}"] = f'=IF(COUNT(P{first},P{second})=2,SUM(P{first},P{second}),"")'
        sheet[f"C{row}"] = f'=IF(AND(ISNUMBER(D{row}),B{row}>0),D{row}/B{row},"")'
    for row, title, formula in (
        (41, "Additional supplies / accessories", _optional_sale(20)),
        (42, "TOTAL EXW", '=IF(AND(SUM(C28:C33)>0,COUNT(D38:D41)=4),SUM(D38:D41),"")'),
        (43, "Packaging / FOB addition", _optional_sale(21)),
        (44, "TOTAL FOB", '=IF(COUNT(D42:D43)=2,SUM(D42:D43),"")'),
        (45, "Freight addition", _optional_sale(22)),
        (46, "TOTAL CFR", '=IF(COUNT(D44:D45)=2,SUM(D44:D45),"")'),
    ):
        _literal(sheet.cell(row, 1), title)
        sheet.cell(row, 4, formula)
    for row in (42, 44, 46):
        for cell in sheet[row][:4]:
            cell.fill = PatternFill("solid", fgColor="E9F2FA")
            cell.font = Font(name="Calibri", size=11, bold=True, color="102A43")
    sheet["D36"] = '=IF($B$13="","",$B$13)'
    for row in sheet.iter_rows(min_row=38, max_row=46, min_col=3, max_col=4):
        for cell in row:
            cell.number_format = "#,##0.00"
    for col, width in {"A": 36, "B": 19, "C": 29, "D": 21, "E": 18, "F": 19, "G": 18, "H": 21, "I": 21, "J": 18, "K": 18, "L": 21, "M": 18, "N": 21, "O": 19, "P": 19}.items():
        sheet.column_dimensions[col].width = width
    for row in range(13, 23):
        sheet.row_dimensions[row].height = 25
    for row in range(28, 34):
        sheet.row_dimensions[row].height = 25
    for row in range(38, 47):
        sheet.row_dimensions[row].height = 25
    positive = DataValidation(type="decimal", operator="greaterThan", formula1="0", allow_blank=True)
    nonnegative = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True)
    for validation in (positive, nonnegative):
        validation.errorTitle = "Invalid commercial input"
        validation.error = "Enter a valid nonnegative number; density must be greater than zero."
        validation.showErrorMessage = True
        validation.errorStyle = "stop"
        sheet.add_data_validation(validation)
    positive.add("B17:B18")
    for cells in ("B14:B16", "B20:B22", "H28:I33"):
        nonnegative.add(cells)
