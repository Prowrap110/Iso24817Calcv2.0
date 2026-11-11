"""Excel transport for the shared single-case calculator."""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from math import isfinite
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.datavalidation import DataValidation

from .schema import DEFECT_FIELDS, FIELD_DEFINITIONS, LOAD_FIELDS, SECTIONS, default_case

SETUP = "Batch Setup"
LINES = "Line Defaults"
CASES = "Repair Cases"
DEFECTS = "Defect Details"
ENGINEERING = "Load and Engineering Details"
STANDARD = "ISO 24817:2026"
VERSION = "PROWRAP CalcBatch v2.0"
FIRST_ROW = 5
MAX_FILE_MB = 10
LIMITS = {LINES: 150, CASES: 150, DEFECTS: 5000, ENGINEERING: 1500}
STATUSES = ("CALCULATED", "ESTIMATE", "INPUT_ERROR", "ENGINEERING_HOLD", "NO_VALID_DESIGN")
VALID_STATUSES = frozenset(STATUSES[:2])
NAVY = "102A43"
BLUE = "1D4B75"
PALE_BLUE = "E9F2FA"
GRAY = "62778B"

DEFECT_CASE_FIELDS = (
    "dent_mode", "dent_depth_mm", "no_crack_confirmed", "dent_ffs_ref", "dent_mawp_bar",
    "dent_complex", "fatigue_assessment_ref", "seal_shape", "effective_diameter_mm",
    "effective_axial_mm", "effective_circ_mm", "effective_geometry_ref", "stopgap_ref",
)
CORE_CASE_FIELDS = (
    "repair_id", "line_id", "mechanism", "defect_mode", "defect_location", "through_wall",
    "prevent_containment", "component", "od_mm", "wall_mm", "remaining_wall_mm",
    "defect_length_mm", "defect_width_mm", "zone_length_mm", "growth_basis", "growth_ref",
    "corrosion_rate_mm_year", "eol_wall_mm", "inspection_ref", "quantity",
)
COMMON_FIELDS = tuple(key for key in FIELD_DEFINITIONS if key != "repair_id")
LINE_FIELDS = ("line_id",) + tuple(
    key for key in COMMON_FIELDS if FIELD_DEFINITIONS[key]["section"] in (3, 4, 6)
) + tuple(
    key for key in COMMON_FIELDS if FIELD_DEFINITIONS[key]["section"] not in (3, 4, 6)
)
CASE_FIELDS = CORE_CASE_FIELDS + tuple(
    key for key in COMMON_FIELDS if key not in CORE_CASE_FIELDS
)
ENGINEERING_CASE_FIELDS = (
    "pressure_basis", "maop_bar",
    "install_pressure_bar", "install_temperature_c", "run_od_mm", "branch_od_mm",
    "component_qualified", "component_ref", "load_basis", "external_pressure",
    "external_assessment_ref", "other_thickness_mm", "substrate_route", "sharing_basis",
    "ffs_method", "ffs_ref", "assessed_mawp_bar", "axial_mawp_bar", "assessed_axial_capacity_kn",
    "qualified_wall_loss_pct", "qualification_ref", "b31g_safety_factor",
    "original_design_factor", "landing_mode", "landing_left_mm", "landing_right_mm",
    "procedure_ref", "cure_basis", "cure_ref", "cure_temperature_c", "cure_hours",
    "thicker_repair_limit_mm", "thicker_repair_ref", "feasibility_ref",
)
RATE_FIELDS = ("currency", "fabric_rate", "epoxy_rate")
EXTRA_FIELDS = {
    "line_id": ("Line ID", "text"),
    "defect_id": ("Defect ID", "text"),
    "load_id": ("Load ID", "text"),
    "length_mm": ("Measured axial length [mm]", "number"),
    "width_mm": ("Measured circumferential width [mm]", "number"),
    "separation_mm": ("Measured clear separation [mm]", "number"),
    "currency": ("Currency (e.g. EUR)", "text"),
    "fabric_rate": ("Fabric unit rate [currency/m²]", "number"),
    "epoxy_rate": ("Epoxy and putty unit rate [currency/kg]", "number"),
}
RESULT_FIELDS = {
    "required_thickness_mm": "Required laminate [mm]",
    "installed_plies": "Installed plies",
    "installed_thickness_mm": "Installed laminate [mm]",
    "total_repair_length_mm": "Required repair length [mm]",
    "overlap_mm": "Required overlap per side [mm]",
    "count_500": "500 mm bands · total",
    "count_300": "300 mm bands · total",
    "fabric_area_m2": "Fabric total [m²]",
    "laminate_epoxy_kg": "Laminate epoxy total [kg]",
    "putty_kg": "Putty total [kg]",
    "total_epoxy_kg": "Epoxy including putty [kg]",
    "quantity": "Identical repairs",
}


class WorkbookError(ValueError):
    """The workbook cannot be read as a v2.0 input template."""


@dataclass
class InputRow:
    sheet: str
    number: int
    values: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    legacy_schema: bool = False
    missing_fields: frozenset = field(default_factory=frozenset)

    @property
    def location(self):
        return f"{self.sheet} · row {self.number}"


@dataclass
class PreparedRepair:
    source: InputRow
    case: dict
    origins: dict
    defects: list[dict] = field(default_factory=list)
    loads: list[dict] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass
class PreparedBatch:
    repairs: list[PreparedRepair]
    warnings: list[tuple]
    rates: dict


def _definition(key):
    if key in EXTRA_FIELDS:
        label, kind = EXTRA_FIELDS[key]
        return {"label": label, "kind": kind}
    return FIELD_DEFINITIONS[key]


def _label(key):
    return _definition(key)["label"]


def _write(sheet, row, values):
    for index, value in enumerate(values, 1):
        if isinstance(value, float) and not isfinite(value):
            value = str(value)
        if value is not None and not isinstance(value, (str, int, float, bool)):
            value = str(value)
        cell = sheet.cell(row, index, value)
        if isinstance(value, str):
            # Explicit string typing keeps spreadsheet-like text literal on export.
            cell.data_type = "s"
        elif isinstance(value, float):
            cell.number_format = "0.000E+00" if 0 < abs(value) < 0.0001 or abs(value) >= 1e10 else "0.####"


def _save(workbook):
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _header(sheet, row, labels):
    _write(sheet, row, labels)
    sheet.row_dimensions[row].height = 43
    for cell in sheet[row]:
        cell.font = Font(name="Calibri", color="FFFFFF", bold=True, size=11)
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _banner(sheet, title, instruction):
    _write(sheet, 1, (title,))
    sheet["A1"].font = Font(name="Calibri", size=17, bold=True, color=NAVY)
    _write(sheet, 2, (instruction,))
    sheet["A2"].font = Font(name="Calibri", size=11, color=GRAY)
    sheet.row_dimensions[1].height = 27
    sheet.row_dimensions[2].height = 21
    sheet.sheet_view.showGridLines = False


def _add_choice_validation(sheet, key, cells):
    definition = _definition(key)
    choices = definition.get("choices")
    if definition["kind"] == "bool":
        choices = ["Yes", "No"]
    if choices:
        options = ",".join(str(choice) for choice in choices if choice != "")
        validation = DataValidation(type="list", formula1=f'"{options}"', allow_blank=True)
        validation.error = "Choose a value from the list."
        validation.errorTitle = "Invalid option"
        validation.showErrorMessage = True
        sheet.add_data_validation(validation)
        validation.add(cells)


def _input_table(workbook, title, instruction, fields, visible):
    sheet = workbook.create_sheet(title)
    _banner(sheet, title, instruction)
    _write(sheet, 3, fields)
    sheet.row_dimensions[3].hidden = True
    _header(sheet, 4, [_label(key) for key in fields])
    sheet.freeze_panes = "C5"
    sheet.auto_filter.ref = f"A4:{get_column_letter(len(fields))}{4 + LIMITS[title]}"
    for index, key in enumerate(fields, 1):
        letter = get_column_letter(index)
        width = max(16, min(36, len(_label(key)) * 0.72 + 7))
        dimension = sheet.column_dimensions[letter]
        dimension.width = width
        if _definition(key)["kind"] == "text":
            dimension.number_format = "@"
        if index > visible:
            dimension.outlineLevel = 1
            dimension.hidden = True
        _add_choice_validation(sheet, key, f"{letter}{FIRST_ROW}:{letter}{4 + LIMITS[title]}")
        if key in ('pressure_basis', 'maop_bar', 'min_pressure_bar', 'b31g_safety_factor', 'original_design_factor', 'ffs_ref', 'grouping_ref', 'qualification_ref', 'qualified_wall_loss_pct', 'axial_mawp_bar', 'assessed_axial_capacity_kn'):
            sheet.cell(4, index).comment = Comment(_setup_note(key), 'PROWRAP')
        for row in range(FIRST_ROW, 15):
            cell = sheet.cell(row, index)
            cell.fill = PatternFill("solid", fgColor=PALE_BLUE if row % 2 else "F7FAFD")
            if _definition(key)["kind"] == "text":
                cell.number_format = "@"
    if visible < len(fields):
        sheet.sheet_properties.outlinePr.summaryRight = False
        sheet.column_dimensions[get_column_letter(visible)].collapsed = True
    return sheet


def template_workbook():
    """Return the editable XLSX template with controlled v2 field definitions."""
    workbook = Workbook()
    setup = workbook.active
    setup.title = SETUP
    _banner(setup, VERSION, "Enter common values once. Use the current template for each batch.")
    _write(setup, 1, (VERSION, STANDARD))
    setup["B1"].font = Font(name="Calibri", color=BLUE, bold=True)
    guide = (
        "1   Enter only defaults that apply to every repair, or enter named defaults by line.",
        "2   Add one row per continuous repair zone. Use the same Repair ID on linked tabs.",
        "3   Repair entry overrides line and batch defaults. Blank inherits. Enter zero explicitly.",
        "4   Use Defect Details or Load and Engineering Details only for applicable inputs.",
        "5   Upload to preview, calculate and export. Inputs accept values. Paste formulas as values.",
    )
    for row, note in enumerate(guide, 3):
        setup.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        _write(setup, row, (note,))
        setup.row_dimensions[row].height = 19
    _header(setup, 9, ("Input field", "Common value", "Field key", "Default"))
    row = 10
    for section, title in SECTIONS.items():
        _header(setup, row, (f"{section}   {title}", None, None, None))
        row += 1
        for key in COMMON_FIELDS:
            if FIELD_DEFINITIONS[key]["section"] != section:
                continue
            _write(setup, row, (_label(key), None, key, _setup_note(key)))
            _setup_cell(setup, row, key)
            row += 1
    _header(setup, row, ("Commercial rates · optional", None, None, None))
    for key in RATE_FIELDS:
        row += 1
        _write(setup, row, (_label(key), None, key, "Enter all three values to calculate material cost."))
        _setup_cell(setup, row, key)
    setup.freeze_panes = "B10"
    setup.column_dimensions["A"].width = 54
    setup.column_dimensions["B"].width = 28
    setup.column_dimensions["C"].hidden = True
    setup.column_dimensions["D"].width = 58
    _input_table(
        workbook, LINES, "Optional. Use one row per named line. Select the same Line ID on Repair Cases.",
        LINE_FIELDS, 24,
    )
    _input_table(
        workbook, CASES, "One row per repair zone. Expand the column group for overrides and additional inputs.",
        CASE_FIELDS, len(CORE_CASE_FIELDS),
    )
    _input_table(
        workbook, DEFECTS,
        "Add one row per measured defect with a Defect ID. Leave Defect ID blank for dent or opening inputs.",
        tuple(DEFECT_FIELDS) + DEFECT_CASE_FIELDS, len(DEFECT_FIELDS) + len(DEFECT_CASE_FIELDS),
    )
    _input_table(
        workbook, ENGINEERING,
        "Use a Load ID for each load case. Leave it blank for repair-level engineering inputs.",
        tuple(LOAD_FIELDS) + ENGINEERING_CASE_FIELDS, len(LOAD_FIELDS) + len(ENGINEERING_CASE_FIELDS),
    )
    return _save(workbook)


def _setup_note(key):
    if key == 'strain_basis':
        return 'LTS uses the owner-selected long-term strain 0.007 (0.7%) for both products before design-life, temperature, cyclic and thermal-strain factors. Default retains the standard strain route.'
    if key == 'substrate_route':
        return 'Corrosion design-route selection. Dent no-crack automatically uses Substrate stress limit with assessed dent MAWP, including existing workbooks that enter Full laminate.'
    if key == 'dent_mawp_bar':
        return 'Assessed dent MAWP supplies remaining-pipe Ps for the dent substrate stress-limit calculation. Required for measured dents and population estimates; no Modified B31G capacity is used for dents.'
    if key == 'dent_ffs_ref':
        return 'Dent assessment reference establishing MAWP and applicability. Required for measured dents and population estimates.'
    if key == 'allowable_stress_mpa':
        return 'For dents, optional manual allowable-stress override; blank uses SMYS × original design factor. Installation stress remains part of the stress-limit calculation. For corrosion, used by the selected route.'
    if key == 'pressure_basis':
        return 'Choose Design pressure (default) or MAOP for the base repair calculation. Enter the selected pressure. Named load cases retain their explicit pressure overrides; blank load pressures inherit the selected base pressure.'
    if key == 'maop_bar':
        return 'Maximum allowable operating pressure [bar]. Used as the base calculation pressure only when Pressure basis is MAOP. Separate from impaired-pipe MAWP and the axial-capacity MAWP override.'
    if key == 'min_pressure_bar':
        return 'Defaults to 0 bar. Enter a manual minimum if required; blank inherits line/batch settings, then 0. Used for pressure bounds and the installation/disbond assessment.'
    if key == 'qualification_ref':
        return 'Optional substrate-credit qualification reference. Blank does not prevent calculation; the confirmed qualified wall-loss limit and all substrate-credit checks still apply.'
    if key == 'qualified_wall_loss_pct':
        return 'Default 81% for PRW110 and PRW110+. Enter a manual limit to override. Blank inherits repair/engineering, line or batch settings; with no entered limit, uses 81%. End-of-life wall loss must be strictly below the selected limit.'
    if key == 'grouping_ref':
        return 'Optional inspection/grouping reference. Blank does not prevent calculation. Confirm dimensions and noninteraction and enter the overall zone span; independent-defect applicability checks still apply.'
    if key == 'axial_mawp_bar':
        return 'Optional axial-only MAWP override in bar. Blank inherits; with no pressure or legacy force override, Fs = A × assessed Ps. Zero means no axial credit. Does not replace hoop Ps.'
    if key == 'assessed_axial_capacity_kn':
        return 'Legacy force override, including zero, is retained. Leave blank for automatic Fs from Ps or the axial MAWP option. Do not populate both force and pressure overrides.'
    if key == 'ffs_ref':
        return 'Optional assessment reference. Blank does not prevent calculation; applicability and capacity checks still apply.'
    if key == 'b31g_safety_factor':
        return 'Optional manual override (minimum 1.25). Blank inherits any line/batch override; if none, automatic = max(1 / original design factor, 1.25).'
    if key == 'original_design_factor':
        return 'Decimal factor, e.g. 0.72. For dents, allowable substrate stress = SMYS × factor unless manually overridden. For Modified B31G, automatic safety factor = max(1 / factor, 1.25).'
    default = FIELD_DEFINITIONS[key]["default"]
    if key in ("growth_basis", "load_basis", "landing_mode"):
        return "Choose the confirmed basis for the repairs in scope."
    if default is None or default == "":
        return ""
    if isinstance(default, bool):
        default = "Yes" if default else "No"
    return f"Calculator default when no value is entered: {default}"


def _setup_cell(sheet, row, key):
    sheet.cell(row, 2).fill = PatternFill("solid", fgColor=PALE_BLUE)
    if _definition(key)["kind"] == "text":
        sheet.cell(row, 2).number_format = "@"
    _add_choice_validation(sheet, key, f"B{row}")


def _is_blank(value):
    return value is None or isinstance(value, str) and not value.strip()


def _parse_cell(cell, key):
    value = cell.value
    if cell.data_type == "f":
        raise ValueError("Excel formula found. Paste the calculated value.")
    if cell.data_type == "e":
        raise ValueError("Excel error value found. Enter a valid value.")
    if _is_blank(value):
        return None
    definition = _definition(key)
    kind = definition["kind"]
    if kind == "text":
        if key in ("inspection_date", "installation_date") and isinstance(value, date):
            return value.isoformat()[:10]
        if isinstance(value, str) or type(value) in (int, float) and isfinite(value):
            return str(value).strip()
        raise ValueError("Enter text.")
    if kind == "bool":
        if isinstance(value, bool):
            return value
        token = str(value).strip().lower()
        if token in ("yes", "no", "true", "false"):
            return token in ("yes", "true")
        raise ValueError("Enter Yes or No.")
    if kind == "select":
        for choice in definition["choices"]:
            if not isinstance(value, bool) and str(value).strip().casefold() == str(choice).casefold():
                return choice
            if type(choice) is int and type(value) is float and value == choice:
                return choice
        raise ValueError("Choose a value from the template list.")
    try:
        if isinstance(value, bool):
            raise ValueError
        number = float(value)
        if not isfinite(number):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Enter a finite number.") from None
    if key == "quantity":
        if number < 1 or not number.is_integer() or number > 2**53 - 1:
            raise ValueError("Enter a positive whole number of identical repairs.")
        return int(number)
    if key in ("fabric_rate", "epoxy_rate") and number < 0:
        raise ValueError("Enter a nonnegative rate.")
    return number


def _read_row(record, cells):
    for key, cell in cells:
        try:
            value = _parse_cell(cell, key)
            if value is not None:
                record.values[key] = value
        except ValueError as error:
            record.errors[key] = f"{record.location} · {_label(key)}. {error}"
    return record


def _read_setup(sheet):
    if sheet["A1"].value != VERSION or sheet["B1"].value != STANDARD:
        raise WorkbookError("Download the current CalcBatch v2.0 Excel template and copy your values into it.")
    if sheet.max_row > 250 or sheet.max_column > 4:
        raise WorkbookError("Batch Setup contains entries outside its controlled columns or rows.")
    record = InputRow(SETUP, 0)
    keys = set()
    expected = set(COMMON_FIELDS + RATE_FIELDS)
    for number, (label, value, key, _) in enumerate(sheet.iter_rows(min_row=10, max_col=4), 10):
        if key.value is None and value.value is None:
            continue
        if (key.data_type != "s" or key.value not in expected or key.value in keys
                or label.value != _label(key.value)):
            raise WorkbookError(f"Unknown, duplicate, or mislabeled Batch Setup field at row {number}. Use the current template.")
        keys.add(key.value)
        row = _read_row(InputRow(SETUP, number), [(key.value, value)])
        record.values.update(row.values)
        record.errors.update(row.errors)
    missing = expected - keys
    allowed_missing = (
        set(), {'axial_mawp_bar'}, {'pressure_basis', 'maop_bar'},
        {'pressure_basis', 'maop_bar', 'axial_mawp_bar'},
    )
    if missing not in allowed_missing:
        raise WorkbookError("Batch Setup fields are missing. Copy values into a fresh template.")
    record.missing_fields = frozenset(missing)
    record.legacy_schema = 'axial_mawp_bar' in missing
    return record


def _read_table(sheet, expected):
    if sheet.max_row > LIMITS[sheet.title] + 4:
        raise WorkbookError(f"{sheet.title} supports up to {LIMITS[sheet.title]:,} rows.")
    if sheet.max_column != len(expected):
        raise WorkbookError(f"{sheet.title} columns changed. Copy values into a fresh template.")
    keys = [cell.value for cell in sheet[3]]
    if (set(keys) != set(expected) or len(keys) != len(expected)
            or [cell.value for cell in sheet[4]] != [_label(key) for key in keys]):
        raise WorkbookError(f"{sheet.title} columns changed. Copy values into a fresh template.")
    records = []
    for number, cells in enumerate(sheet.iter_rows(min_row=FIRST_ROW), FIRST_ROW):
        if any(not _is_blank(cell.value) for cell in cells):
            records.append(_read_row(InputRow(sheet.title, number), zip(keys, cells)))
    return records


def _matching_id(value):
    return (value or "").casefold()


def _by_id(records, key):
    grouped = defaultdict(list)
    for record in records:
        grouped[_matching_id(record.values.get(key))].append(record)
    return grouped


def _warning(record, repair_id, message):
    return (repair_id, record.sheet, record.number or None, "INPUT_ERROR", message)


def _attach_details(records, known, child_key, child_fields, warnings):
    """Separate linked detail rows from invalid and orphan workbook records."""
    grouped = defaultdict(list)
    duplicate_keys = Counter(
        (_matching_id(record.values.get("repair_id")), _matching_id(record.values.get(child_key)))
        for record in records if record.values.get(child_key)
    )
    for record in records:
        repair_id = record.values.get("repair_id", "")
        key = _matching_id(repair_id)
        if key not in known or not key:
            message = f"Unknown Repair ID '{repair_id}'." if repair_id else "Repair ID is required."
            warnings.append(_warning(record, repair_id, message))
            warnings.extend(_warning(record, repair_id, error) for error in record.errors.values())
            continue
        child_id = record.values.get(child_key)
        actual = record.values.keys() - {"repair_id", child_key}
        if duplicate_keys[key, _matching_id(child_id)] > 1:
            record.errors[child_key] = f"{record.location}. Duplicate {_label(child_key)} '{child_id}'."
        if child_id and actual - set(child_fields):
            record.errors["fields"] = f"{record.location}. Put repair-level inputs on a separate row with a blank {_label(child_key)}."
        if child_key == "defect_id" and not child_id and actual & set(child_fields):
            record.errors["fields"] = f"{record.location}. Enter {_label(child_key)} for these linked inputs."
        if not actual:
            record.errors["empty"] = f"{record.location}. Enter linked input values or remove the row."
        grouped[key].append(record)
    return grouped


def _resolve(source, setup, lines, defects, loads, duplicate):
    repair_id = source.values.get("repair_id", "")
    line_id = source.values.get("line_id", "")
    case = default_case()
    origins = {key: "Calculator default" for key, value in case.items() if not _is_blank(value)}
    if setup.legacy_schema:
        case['ffs_method'] = 'External assessment'
        origins['ffs_method'] = 'Legacy v2.0 default'
    prepared = PreparedRepair(source, case, origins, issues=list(source.errors.values()))
    if not repair_id:
        prepared.issues.append("Repair ID is required.")
    if duplicate:
        prepared.issues.append(f"Duplicate Repair ID '{repair_id}'.")
    overlays = [(setup, SETUP)]
    if line_id:
        if len(lines) != 1:
            issue = "Duplicate" if lines else "Unknown"
            prepared.issues.append(f"{issue} Line ID '{line_id}'.")
        else:
            overlays.append((lines[0], f"{LINES} · {line_id}"))
    explicit = {}
    for record, child_key, destination in (
        *((record, "defect_id", prepared.defects) for record in defects),
        *((record, "load_id", prepared.loads) for record in loads),
        (source, "", None),
    ):
        if record is not source:
            prepared.issues.extend(record.errors.values())
        if child_key and child_key in record.values:
            destination.append({key: value for key, value in record.values.items() if key != "repair_id"})
            continue
        for key, value in record.values.items():
            if key == "line_id" or key == "repair_id" and record is not source:
                continue
            if key in explicit and explicit[key][0] != value:
                prepared.issues.append(f"Conflicting {_label(key)} values at {explicit[key][1]} and {record.location}.")
            explicit[key] = (value, record.location)
    for record, origin in overlays:
        for key, value in record.values.items():
            if key in case:
                case[key] = value
                origins[key] = origin
    # A selected named line supplies the asset ID unless there is a more specific ID.
    if line_id and not case["asset_id"]:
        case["asset_id"] = line_id
        origins["asset_id"] = "Selected Line ID"
    for key, (value, origin) in explicit.items():
        if key in case:
            case[key] = value
            origins[key] = origin
    for record, _ in overlays:
        for key, error in record.errors.items():
            if key in RATE_FIELDS or key in explicit:
                continue
            if record is setup and len(lines) == 1 and key in lines[0].values:
                continue
            prepared.issues.append(error)
    return prepared


def prepare_workbook(content: bytes) -> PreparedBatch:
    """Read the workbook, resolve inputs, and collect import issues before calculation."""
    if not content or len(content) > MAX_FILE_MB * 1024**2:
        raise WorkbookError(f"Upload an Excel workbook up to {MAX_FILE_MB} MB.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(entry.file_size for entry in archive.infolist()) > 50 * 1024**2:
                raise WorkbookError("The expanded Excel workbook exceeds the processing limit.")
            if any(entry.filename.lower().endswith("vbaproject.bin") for entry in archive.infolist()):
                raise WorkbookError("Upload a macro-free Excel .xlsx workbook.")
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        try:
            if not {SETUP, LINES, CASES, DEFECTS, ENGINEERING} <= set(workbook.sheetnames):
                raise WorkbookError("Required input sheets are missing. Download the current CalcBatch Excel template.")
            setup = _read_setup(workbook[SETUP])
            def compatible(fields):
                return tuple(key for key in fields if key not in setup.missing_fields)
            line_rows = _read_table(workbook[LINES], compatible(LINE_FIELDS))
            sources = _read_table(workbook[CASES], compatible(CASE_FIELDS))
            defect_rows = _read_table(workbook[DEFECTS], tuple(DEFECT_FIELDS) + DEFECT_CASE_FIELDS)
            load_rows = _read_table(workbook[ENGINEERING], compatible(tuple(LOAD_FIELDS) + ENGINEERING_CASE_FIELDS))
        finally:
            workbook.close()
    except (BadZipFile, InvalidFileException, KeyError, OSError, ParseError, TypeError, ValueError) as error:
        if isinstance(error, WorkbookError):
            raise
        raise WorkbookError("The Excel file could not be read. Save a new copy as .xlsx and upload it.") from error
    warnings = []
    lines = _by_id(line_rows, "line_id")
    ids = _by_id(sources, "repair_id")
    for record in lines.get("", []):
        warnings.append(_warning(record, "", "Line ID is required."))
        warnings.extend(_warning(record, "", error) for error in record.errors.values())
    # Also report unused invalid defaults so they can be corrected in the source workbook.
    for line, records in lines.items():
        if line and len(records) > 1:
            warnings.extend(
                _warning(record, "", f"Duplicate Line ID '{record.values['line_id']}'.")
                for record in records
            )
    warnings.extend((None, SETUP, None, "INPUT_ERROR", error) for error in setup.errors.values())
    for record in line_rows:
        if record.values.get("line_id"):
            warnings.extend(_warning(record, "", error) for error in record.errors.values())
    linked_defects = _attach_details(defect_rows, ids, "defect_id", DEFECT_FIELDS, warnings)
    linked_loads = _attach_details(
        load_rows, ids, "load_id", LOAD_FIELDS, warnings
    )
    repairs = []
    for source in sources:
        repair = _matching_id(source.values.get("repair_id"))
        line = _matching_id(source.values.get("line_id"))
        repairs.append(_resolve(
            source, setup, lines.get(line, []), linked_defects[repair], linked_loads[repair],
            bool(repair and len(ids[repair]) > 1),
        ))
    rates = {key: setup.values[key] for key in RATE_FIELDS if key in setup.values}
    if rates and len(rates) != len(RATE_FIELDS):
        warnings.append((None, SETUP, None, "COMMERCIAL", "Enter currency and both unit rates to calculate cost."))
        rates = {}
    return PreparedBatch(repairs, warnings, rates)


def _input_error(case, issues):
    return {
        "repair_id": case["repair_id"], "status": "INPUT_ERROR", "issues": issues,
        "inputs": case, "results": {}, "checks": [], "details": {},
    }


def _expanded_cases(batch):
    from .engine import expand_population

    expanded = []
    for repair in batch.repairs:
        cases = [repair.case] if repair.issues else expand_population(repair.case)
        expanded.append((repair, cases))
    return expanded


def _evaluate(batch):
    from .engine import evaluate_case

    expanded = _expanded_cases(batch)
    source_ids = {_matching_id(repair.case["repair_id"]) for repair in batch.repairs}
    group_ids = Counter(
        _matching_id(case["repair_id"])
        for _, cases in expanded for case in cases if case.get("population_estimate")
    )
    conflicts = {key for key, count in group_ids.items() if key in source_ids or count > 1}
    for repair, cases in expanded:
        issues = list(repair.issues)
        if not issues and any(_matching_id(case["repair_id"]) in conflicts for case in cases):
            issues.append("Repair ID conflicts with a 60/40 population group ID. Choose a distinct Repair ID.")
        if issues:
            yield repair, repair.case, _input_error(repair.case, issues)
            continue
        for case in cases:
            yield repair, case, evaluate_case(case, repair.defects, repair.loads)


def _output_table(workbook, title, instruction, headers, rows, widths):
    sheet = workbook.create_sheet(title)
    _banner(sheet, title, instruction)
    _header(sheet, 4, headers)
    for number, values in enumerate(rows, FIRST_ROW):
        _write(sheet, number, values)
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "B5"
    sheet.auto_filter.ref = f"A4:{get_column_letter(len(headers))}{sheet.max_row}"
    sheet.protection.sheet = True
    sheet.protection.autoFilter = False
    return sheet


def _effective_inputs(calculations):
    for repair, case, result in calculations:
        result_id = result["repair_id"]
        effective_case = dict(case)
        dent = result.get('details', {}).get('dent_capacity')
        dent_origins = {}
        ignored_dent_fields = ()
        if dent:
            dent_origins = {
                'substrate_route': 'ISO 24817:2026 · ' + dent['clauses'],
                'ffs_method': dent['source'],
                'assessed_mawp_bar': dent['source'],
                'allowable_stress_mpa': dent['allowable_stress_source'],
            }
            for key in dent_origins:
                value = result['inputs'][key]
                if value != case.get(key) and not _is_blank(case.get(key)):
                    yield result_id, 'Repair', 'Entered ' + _label(key), case[key], repair.origins.get(key)
                effective_case[key] = value
            ignored_dent_fields = ('sharing_basis', 'ffs_ref', 'b31g_safety_factor')
            for key in ignored_dent_fields:
                if not _is_blank(case.get(key)):
                    yield result_id, 'Repair', 'Entered ' + _label(key), case[key], 'Not used for dent assessment; ' + str(repair.origins.get(key) or '')
        pressure = result.get('details', {}).get('pressure_basis')
        if pressure:
            yield result_id, 'Repair', 'Calculation pressure [bar]', pressure['calculation_pressure_bar'], pressure['basis']
        selected = result.get('details', {}).get('b31g')
        if selected:
            yield result_id, 'Repair', 'B31G safety factor used', selected['safety_factor'], selected['source']
        axial = result.get('details', {}).get('axial_capacity')
        if axial and effective_case['substrate_route'] != 'Full laminate':
            yield result_id, 'Repair', 'Axial capacity used [kN]', axial['force_kn'], axial['source']
            if axial['pressure_bar'] is not None:
                yield result_id, 'Repair', 'Axial pressure basis [bar]', axial['pressure_bar'], axial['source']
            yield result_id, 'Repair', 'Remaining-pipe Ps [bar]', result['details']['substrate_pressure_mpa']*10, dent['source'] if dent else case['ffs_method']
        for key, value in effective_case.items():
            if key not in FIELD_DEFINITIONS or key in ignored_dent_fields or _is_blank(value):
                continue
            origin = dent_origins.get(key, repair.origins.get(key))
            if key not in dent_origins and case.get("population_estimate") and value != repair.case.get(key):
                origin = "60/40 dent population"
            yield result_id, "Repair", _label(key), value, origin
        for records, record_key, sheet in (
            (repair.defects, "defect_id", DEFECTS), (repair.loads, "load_id", ENGINEERING),
        ):
            for record in records:
                for key, value in record.items():
                    if key != record_key:
                        yield result_id, record[record_key], _label(key), value, sheet


def _detail_paths(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix} / {key}" if prefix else key
            yield from _detail_paths(item, path)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value, 1):
            yield from _detail_paths(item, f"{prefix} / {index}")
    else:
        yield prefix, value


def _summary(results, rates, warnings):
    rows = []
    for status in STATUSES:
        same_status = [record for record in results if record["status"] == status]
        quantities = [record["results"] for record in same_status if status in VALID_STATUSES]
        if not quantities:
            rows.append((status, len(same_status), None, None, None, None, None, None, None))
            continue
        quantity, area, laminate, putty, epoxy = (
            sum(values[key] for values in quantities)
            for key in ("quantity", "fabric_area_m2", "laminate_epoxy_kg", "putty_kg", "total_epoxy_kg")
        )
        cost = None
        if rates:
            cost = area * rates["fabric_rate"] + epoxy * rates["epoxy_rate"]
            if not isfinite(cost):
                cost = None
                warnings.append((None, SETUP, None, "COMMERCIAL", f"{status} material cost exceeds numeric limits."))
        rows.append((status, len(same_status), quantity, area, laminate, putty, epoxy, cost, rates.get("currency")))
    return rows


def calculate_batch(batch: PreparedBatch) -> tuple[bytes, list[dict]]:
    """Evaluate each independent repair and export results with input provenance."""
    calculations = list(_evaluate(batch))
    results = [result for _, _, result in calculations]
    warnings = list(batch.warnings)
    for repair, _, result in calculations:
        warnings.extend(
            (result["repair_id"], repair.source.sheet, repair.source.number, result["status"], issue)
            for issue in result["issues"]
        )

    workbook = Workbook()
    workbook.remove(workbook.active)
    summary = _output_table(
        workbook, "Summary and Cost",
        f"{STANDARD}  |  Calculated and indicative estimate material totals are shown separately.",
        ("Status", "Result rows", "Repair quantity", "Fabric [m²]", "Laminate epoxy [kg]",
         "Putty [kg]", "Epoxy including putty [kg]", "Material cost", "Currency"),
        _summary(results, batch.rates, warnings), (26, 14, 17, 17, 19, 15, 23, 18, 14),
    )
    if batch.rates:
        _write(summary, 12, ("Commercial input", "Rate", "Currency"))
        _write(summary, 13, ("Fabric / m²", batch.rates["fabric_rate"], batch.rates["currency"]))
        _write(summary, 14, ("Epoxy and putty / kg", batch.rates["epoxy_rate"], batch.rates["currency"]))
    else:
        _write(summary, 12, ("Enter currency and both rates on Batch Setup to calculate cost.",))
    headers = ("Repair ID", "Source Repair ID", "Source row", "Status", "Asset / line", "Type", "Governing load") + tuple(RESULT_FIELDS.values())
    _output_table(
        workbook, "Results",
        "Calculation for engineering review. Repair dimensions apply to one repair. Material and band totals include quantity.",
        headers,
        (
            (result["repair_id"], repair.case["repair_id"], repair.source.number, result["status"],
             case["asset_id"], result["details"].get("repair_type"), result["details"].get("controlling_load_id"),
             *(result["results"].get(key) if result["status"] in VALID_STATUSES else None for key in RESULT_FIELDS))
            for repair, case, result in calculations
        ), (24, 24, 12, 24, 23, 12, 19) + (20,) * len(RESULT_FIELDS),
    )
    _output_table(
        workbook, "Warnings", "Review case issues and unused or orphan workbook entries.",
        ("Repair ID", "Input sheet", "Source row", "Status", "Issue"),
        warnings, (24, 32, 14, 26, 100),
    )
    _output_table(
        workbook, "Effective Inputs", "Effective calculation values and origins. Entered values changed by the dent method are recorded separately. Blank inputs are omitted.",
        ("Repair ID", "Record", "Input field", "Value", "Origin"),
        _effective_inputs(calculations), (24, 22, 54, 36, 39),
    )
    _output_table(
        workbook, "Engineering Checks", "Checks emitted by the shared evaluator.",
        ("Repair ID", "Check", "Pass", "Value", "Limit", "Clause"),
        (
            (result["repair_id"], check.get("name"), check.get("passed"), check.get("value"),
             check.get("limit"), check.get("clause"))
            for result in results for check in result["checks"]
        ), (24, 36, 11, 19, 19, 24),
    )
    _output_table(
        workbook, "Calculation Details", "Diagnostic trace. Use Results for reportable repair dimensions and quantities.",
        ("Repair ID", "Calculation path", "Value"),
        (
            (result["repair_id"], path, value)
            for result in results for path, value in _detail_paths(result["details"])
        ), (24, 65, 90),
    )
    return _save(workbook), results


def process_workbook(content: bytes) -> tuple[bytes, list[dict]]:
    return calculate_batch(prepare_workbook(content))
