"""Pressure-based axial credit must preserve hoop Ps and workbook semantics."""
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


def test_default_uses_final_capped_ps_for_axial_force():
    case = axial_case()
    case['ffs_method'] = default_case()['ffs_method']
    ps, fs = capacity(case)
    # Original-code limit 2*350*4.5/457.2, below raw MB31G 9.9518736 MPa.
    assert ps == pytest.approx(6.889763779527559)
    assert fs == pytest.approx(1131114.726961737)


@pytest.mark.parametrize('mawp,force', [(20, 328346.446455179), (0, 0)])
def test_manual_bar_override_changes_only_axial_credit(mawp, force):
    ps, fs = capacity(axial_case(axial_mawp_bar=mawp))
    assert ps == pytest.approx(6.889763779527559)
    assert fs == pytest.approx(force)


@pytest.mark.parametrize('force', [0, 125])
def test_legacy_force_override_is_preserved(force):
    ps, fs = capacity(axial_case(assessed_axial_capacity_kn=force))
    assert ps == pytest.approx(6.889763779527559)
    assert fs == force * 1000


def test_conflicting_pressure_and_force_never_issue_quantities():
    result = evaluate_case(axial_case(axial_mawp_bar=20, assessed_axial_capacity_kn=0))
    assert result['status'] == 'ENGINEERING_HOLD'
    assert 'both' in ' '.join(result['issues']).lower()
    assert result['results'] == {}


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), True])
def test_invalid_axial_mawp_never_issues_quantities(value):
    result = evaluate_case(axial_case(axial_mawp_bar=value))
    assert result['status'] == 'INPUT_ERROR'
    assert result['results'] == {}


def test_manual_axial_pressure_does_not_bypass_b31g_scope():
    result = evaluate_case(axial_case(axial_mawp_bar=20, smts_mpa=None))
    assert result['status'] == 'ENGINEERING_HOLD'
    assert not result['results']


@pytest.mark.parametrize('override,status', [(None,'CALCULATED'), (0,'CALCULATED'), (20,'ENGINEERING_HOLD')])
def test_hotter_load_requires_specific_manual_axial_capacity(override, status):
    result = evaluate_case(axial_case(axial_mawp_bar=override), loads=[dict(load_id='HOT', temperature_c=45)])
    assert result['status'] == status, result['issues']
    if status == 'ENGINEERING_HOLD':
        assert not result['results']
        assert 'temperature-specific' in ' '.join(result['issues'])


def test_external_hoop_mawp_and_manual_axial_mawp_remain_separate():
    ps, fs = capacity(axial_case(ffs_method='External assessment', assessed_mawp_bar=30, axial_mawp_bar=20))
    assert ps == 3
    assert fs == pytest.approx(328346.446455179)


def test_capacity_trace_reaches_engine_load_cases_and_pdf():
    result = evaluate_case(axial_case(axial_mawp_bar=20))
    assert result['status'] == 'CALCULATED', result['issues']
    detail = result['details']['axial_capacity']
    assert detail['force_kn'] == pytest.approx(328.346446455179)
    assert detail['pressure_bar'] == 20
    assert detail['source'] == 'Manual axial MAWP'
    assert result['details']['load_cases'][0]['axial_capacity'] == detail
    text = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(report_pdf(result))).pages)
    assert 'Manual axial MAWP' in text and '328.346' in text


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


def test_batch_pressure_override_and_zero_match_single_and_export_basis():
    batch = prepare_workbook(pack(axial_workbook()))
    output, results = calculate_batch(batch)
    assert [r['status'] for r in results] == ['CALCULATED']*3 + ['INPUT_ERROR']
    for repair, result in zip(batch.repairs, results):
        assert result == evaluate_case(repair.case)
    book = load_workbook(BytesIO(output))
    values = {r[0]:r[3] for r in book['Effective Inputs'].iter_rows(min_row=5,values_only=True)
              if r[2] == 'Axial capacity used [kN]'}
    assert values == pytest.approx({'AUTO':1131.114726961737,'MANUAL':328.346446455179,'ZERO':0})


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
    assert results[0]['details']['axial_capacity']['force_kn'] == pytest.approx(410.433058068973)


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
        assert result['details']['axial_capacity']['force_kn'] == 0


def test_new_workbook_with_other_missing_column_is_rejected():
    book = axial_workbook()
    sheet = book['Repair Cases']
    sheet.delete_cols(next(c.column for c in sheet[3] if c.value=='assessed_mawp_bar'))
    with pytest.raises(WorkbookError): prepare_workbook(pack(book))


def test_single_form_override_clear_and_stale_result_removal():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'app.py'), default_timeout=20)
    for key,value in axial_case().items(): app.session_state['case_'+key] = value
    app.run()
    app.button(key='calculate').click().run()
    assert not app.exception
    auto = app.session_state['calculation_results'][0]
    assert auto['details']['axial_capacity']['force_kn'] == pytest.approx(1131.114726961737)
    app.number_input(key='case_axial_mawp_bar').set_value(20).run()
    assert 'calculation_results' not in app.session_state
    app.button(key='calculate').click().run()
    manual = app.session_state['calculation_results'][0]
    assert manual['details']['axial_capacity']['force_kn'] == pytest.approx(328.346446455179)
    assert manual['details']['substrate_pressure_mpa'] == auto['details']['substrate_pressure_mpa']
    app.number_input(key='case_axial_mawp_bar').set_value(None).run()
    app.button(key='calculate').click().run()
    assert app.session_state['calculation_results'][0]['details']['axial_capacity'] == auto['details']['axial_capacity']


def test_existing_single_force_input_stays_visible_until_explicitly_cleared():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'app.py'), default_timeout=20)
    for key,value in axial_case(assessed_axial_capacity_kn=0).items(): app.session_state['case_'+key] = value
    app.run()
    app.button(key='calculate').click().run()
    assert app.session_state['calculation_results'][0]['details']['axial_capacity']['force_kn'] == 0
    app.number_input(key='case_assessed_axial_capacity_kn').set_value(None).run()
    app.button(key='calculate').click().run()
    assert app.session_state['calculation_results'][0]['details']['axial_capacity']['force_kn'] == pytest.approx(1131.114726961737)


def test_batch_app_upload_calculates_auto_manual_zero_and_invalid():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'batch_app.py'), default_timeout=20).run()
    app.get('file_uploader')[0].upload('axial-capacity.xlsx',pack(axial_workbook())).run()
    app.button[0].click().run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label=='Calculated') == '3'
    assert next(m.value for m in app.metric if m.label=='Require review') == '1'
