"""ISO 24817:2017 sizing and compatibility with legacy axial inputs."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from prowrap_v2.assessment import substrate_capacity
from prowrap_v2.batch import template_workbook, prepare_workbook, calculate_batch, WorkbookError
from prowrap_v2.engine import evaluate_case
from prowrap_v2.reporting import report_pdf
from prowrap_v2.schema import default_case
from test_b31g_factor import b31g_case


def axial_case(**changes):
    case = b31g_case(assessed_axial_capacity_kn=None)
    case.update(changes)
    return case


def capacity(case):
    return substrate_capacity(case, [dict(length_mm=100, eol_wall_mm=4.5)], 4.5)


def test_default_caps_hoop_pressure_at_annex_k_remaining_wall_pressure():
    case = axial_case()
    case['ffs_method'] = default_case()['ffs_method']
    ps, fs = capacity(case)
    # Annex K remaining-wall pressure is below raw Modified B31G (9.9519 MPa).
    assert ps == pytest.approx(2 * 350 * 4.5 / (457.2 - 4.5))
    assert fs is None


@pytest.mark.parametrize('field,value', [
    ('axial_mawp_bar', 20), ('axial_mawp_bar', 0),
    ('assessed_axial_capacity_kn', 125), ('assessed_axial_capacity_kn', 0),
])
def test_legacy_axial_inputs_are_recorded_without_affecting_sizing(field, value):
    baseline = evaluate_case(axial_case())
    result = evaluate_case(axial_case(**{field: value}))
    assert baseline['status'] == result['status'] == 'CALCULATED'
    assert result['inputs'][field] == value
    assert result['results'] == baseline['results']
    assert result['details']['load_cases'] == baseline['details']['load_cases']


def test_both_legacy_axial_fields_can_coexist_without_affecting_sizing():
    baseline = evaluate_case(axial_case())
    result = evaluate_case(axial_case(axial_mawp_bar=20, assessed_axial_capacity_kn=0))
    assert result['status'] == baseline['status'] == 'CALCULATED', result['issues']
    assert result['inputs']['axial_mawp_bar'] == 20
    assert result['inputs']['assessed_axial_capacity_kn'] == 0
    assert result['results'] == baseline['results']
    assert result['details']['load_cases'] == baseline['details']['load_cases']


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), True])
def test_invalid_axial_mawp_never_issues_quantities(value):
    result = evaluate_case(axial_case(axial_mawp_bar=value))
    assert result['status'] == 'INPUT_ERROR'
    assert result['results'] == {}


def test_manual_axial_pressure_does_not_bypass_b31g_scope():
    result = evaluate_case(axial_case(axial_mawp_bar=20, smts_mpa=None))
    assert result['status'] == 'ENGINEERING_HOLD'
    assert not result['results']


def test_legacy_axial_input_does_not_hold_hotter_b31g_load_case():
    loads = [dict(load_id='HOT', temperature_c=45)]
    baseline = evaluate_case(axial_case(), loads=loads)
    result = evaluate_case(axial_case(axial_mawp_bar=20), loads=loads)
    assert baseline['status'] == result['status'] == 'CALCULATED', result['issues']
    assert result['details']['load_cases'] == baseline['details']['load_cases']


def test_external_assessed_hoop_mawp_is_retained_when_legacy_axial_mawp_is_present():
    result = evaluate_case(axial_case(
        ffs_method='External assessment', assessed_mawp_bar=30, axial_mawp_bar=20))
    assert result['status'] == 'CALCULATED', result['issues']
    assert result['details']['substrate_pressure_mpa'] == 3
    assert result['inputs']['axial_mawp_bar'] == 20
    assert result['details']['axial_capacity']['pressure_bar'] is None


def test_pdf_and_calculation_trace_mark_legacy_axial_input_as_record_only():
    result = evaluate_case(axial_case(axial_mawp_bar=20))
    assert result['status'] == 'CALCULATED', result['issues']
    detail = result['details']['axial_capacity']
    assert detail['force_kn'] is None and detail['pressure_bar'] is None
    assert 'ISO 24817:2017' in detail['source']
    assert result['details']['load_cases'][0]['axial_capacity'] == detail
    pdf = PdfReader(BytesIO(report_pdf(result)))
    text = ' '.join(' '.join(page.extract_text().split()) for page in pdf.pages)
    assert 'Legacy workbook field (record only)' in text
    assert 'Axial-capacity MAWP override [bar]: 20' in text


def pack(book):
    content = BytesIO(); book.save(content)
    return content.getvalue()


def axial_workbook():
    book = load_workbook(BytesIO(template_workbook()))
    setup = book['Batch Setup']
    rows = {setup.cell(r, 3).value:r for r in range(10, setup.max_row+1)}
    for key, value in axial_case().items():
        if key in rows:
            setup.cell(rows[key], 2).value = value
    cases = book['Repair Cases']
    cols = {c.value:c.column for c in cases[3]}
    for row, ident, mawp in [(5,'AUTO',None), (6,'MANUAL',20), (7,'ZERO',0), (8,'INVALID',-1)]:
        cases.cell(row,cols['repair_id']).value = ident
        if mawp is not None:
            cases.cell(row,cols['axial_mawp_bar']).value = mawp
    return book


def test_batch_retains_legacy_axial_fields_and_matches_single_sizing():
    batch = prepare_workbook(pack(axial_workbook()))
    output, results = calculate_batch(batch)
    assert [r['status'] for r in results] == ['CALCULATED'] * 3 + ['INPUT_ERROR']
    for repair, result in zip(batch.repairs, results):
        assert result == evaluate_case(repair.case)
    assert [r['results'] for r in results[:3]] == [results[0]['results']] * 3
    book = load_workbook(BytesIO(output))
    inputs = list(book['Effective Inputs'].iter_rows(min_row=5, values_only=True))
    records = {r[0]: (r[3], r[4]) for r in inputs if r[2] == 'Axial-capacity MAWP override [bar]'}
    assert 'AUTO' not in records
    assert records['MANUAL'][0] == 20
    assert records['ZERO'][0] == 0
    assert all('record only' in records[repair_id][1] for repair_id in ('MANUAL', 'ZERO'))
    assert all(r[2] != 'Axial capacity used [kN]' for r in inputs)


def test_batch_inherits_axial_pressure_and_preserves_explicit_zero():
    book = axial_workbook()
    setup = book['Batch Setup']
    row = next(r for r in range(10,setup.max_row+1) if setup.cell(r,3).value=='axial_mawp_bar')
    setup.cell(row,2).value = 30
    lines = book['Line Defaults']
    line_cols = {c.value:c.column for c in lines[3]}
    lines.cell(5,line_cols['line_id']).value = 'A'
    lines.cell(5,line_cols['axial_mawp_bar']).value = 25
    cases = book['Repair Cases']
    cols = {c.value:c.column for c in cases[3]}
    for row in (5,6,7): cases.cell(row,cols['line_id']).value = 'A'
    batch = prepare_workbook(pack(book))
    assert [r.case['axial_mawp_bar'] for r in batch.repairs] == [25,20,0,-1]
    assert batch.repairs[0].origins['axial_mawp_bar'] == 'Line Defaults · A'
    _, results = calculate_batch(batch)
    assert [r['status'] for r in results] == ['CALCULATED']*3+['INPUT_ERROR']
    assert results[0]['inputs']['axial_mawp_bar'] == 25
    assert results[0]['details']['axial_capacity']['force_kn'] is None


def legacy_workbook():
    book = axial_workbook()
    setup = book['Batch Setup']
    for r in range(setup.max_row, 9, -1):
        key = setup.cell(r,3).value
        if key == 'axial_mawp_bar': setup.delete_rows(r)
        elif key == 'ffs_method': setup.cell(r,2).value = None
        elif key == 'assessed_mawp_bar': setup.cell(r,2).value = 20
        elif key == 'assessed_axial_capacity_kn': setup.cell(r,2).value = 0
    for title in ('Line Defaults','Repair Cases','Load and Engineering Details'):
        sheet = book[title]
        col = next(c.column for c in sheet[3] if c.value=='axial_mawp_bar')
        sheet.delete_cols(col)
    return book


def test_old_v2_workbook_preserves_external_default_and_explicit_force():
    batch = prepare_workbook(pack(legacy_workbook()))
    assert all(r.case['ffs_method']=='External assessment' for r in batch.repairs)
    _, results = calculate_batch(batch)
    assert all(r['status']=='CALCULATED' for r in results)
    for result in results:
        assert result['details']['substrate_pressure_mpa'] == 2
        assert result['inputs']['assessed_axial_capacity_kn'] == 0
        assert result['details']['axial_capacity']['force_kn'] is None


def test_new_workbook_with_other_missing_column_is_rejected():
    book = axial_workbook()
    sheet = book['Repair Cases']
    sheet.delete_cols(next(c.column for c in sheet[3] if c.value=='assessed_mawp_bar'))
    with pytest.raises(WorkbookError): prepare_workbook(pack(book))


def test_single_form_omits_withdrawn_axial_substrate_credit_controls():
    app = AppTest.from_file(str(Path(__file__).parents[1] / 'app.py'), default_timeout=20)
    for key, value in axial_case().items():
        app.session_state['case_' + key] = value
    app.run()
    app.button(key='calculate').click().run()
    assert not app.exception
    assert app.session_state['calculation_results'][0]['status'] == 'CALCULATED'
    field_keys = {field.key for field in app.number_input}
    assert 'case_axial_mawp_bar' not in field_keys
    assert 'case_assessed_axial_capacity_kn' not in field_keys


def test_batch_app_upload_calculates_auto_manual_zero_and_invalid():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'batch_app.py'), default_timeout=20).run()
    app.get('file_uploader')[0].upload('axial-capacity.xlsx',pack(axial_workbook())).run()
    app.button[0].click().run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label=='Calculated') == '3'
    assert next(m.value for m in app.metric if m.label=='Require review') == '1'
