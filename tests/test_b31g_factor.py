"""Safety-factor selection must change capacity, remain auditable and agree in both apps."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from prowrap_v2.assessment import modified_b31g
from prowrap_v2.batch import template_workbook, prepare_workbook, calculate_batch
from prowrap_v2.engine import evaluate_case
from prowrap_v2.reporting import report_pdf
from prowrap_v2.schema import default_case


def b31g_case(**changes):
    case = default_case()
    case.update(repair_id='B31G', od_mm=457.2, wall_mm=9.53, smys_mpa=359,
                smts_mpa=500, material_grade='API 5L X52', design_code='ASME B31.8',
                ffs_ref='FFS-01', pressure_bar=30, min_pressure_bar=0, temperature_c=40,
                min_temperature_c=20, install_pressure_bar=0, install_temperature_c=20,
                defect_length_mm=100, defect_width_mm=50, remaining_wall_mm=4.5,
                growth_basis='No growth confirmed', growth_ref='INS-01',
                load_basis='Pressure-only confirmed', landing_mode='Unrestricted confirmed',
                substrate_route='Substrate sharing', ffs_method='Modified B31G',
                allowable_stress_mpa=350, assessed_axial_capacity_kn=0,
                qualified_wall_loss_pct=80, qualification_ref='QUAL-01', original_design_factor=.72)
    case.update(changes)
    return case


@pytest.mark.parametrize('factor,pressure', [(.72, 9.951873620726573), (.60, 8.293228017272144),
                                           (.80, 11.05763735636286), (.90, 11.05763735636286)])
def test_automatic_factor_changes_capacity_and_preserves_minimum(factor, pressure):
    assert modified_b31g(b31g_case(original_design_factor=factor), 100, 4.5) == pytest.approx(pressure)


def test_manual_override_controls_capacity_and_can_be_cleared():
    case = b31g_case(original_design_factor=.60, b31g_safety_factor=2.)
    assert modified_b31g(case, 100, 4.5) == pytest.approx(6.911023347726787)
    case['b31g_safety_factor'] = None
    assert modified_b31g(case, 100, 4.5) == pytest.approx(8.293228017272144)
    case.update(original_design_factor=None, b31g_safety_factor=2.)
    assert modified_b31g(case, 100, 4.5) == pytest.approx(6.911023347726787)


@pytest.mark.parametrize('changes', [dict(original_design_factor=None), dict(original_design_factor=0),
    dict(original_design_factor=-.1), dict(original_design_factor=1.1), dict(original_design_factor=float('nan')),
    dict(b31g_safety_factor=0), dict(b31g_safety_factor=1.24), dict(b31g_safety_factor=float('inf'))])
def test_invalid_factor_never_issues_installation_quantities(changes):
    result = evaluate_case(b31g_case(**changes))
    assert result['status'] in ('INPUT_ERROR', 'ENGINEERING_HOLD')
    assert not result['results']


def test_factor_trace_is_preserved_in_engine_and_pdf():
    result = evaluate_case(b31g_case())
    assert result['status'] == 'CALCULATED', result['issues']
    assert result['details']['b31g']['safety_factor'] == pytest.approx(1.388888888888889)
    assert result['details']['b31g']['source'] == 'Automatic from original pipeline design factor'
    assert result['inputs']['b31g_safety_factor'] is None
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(report_pdf(result))).pages)
    assert '1.388888' in text


def factor_workbook():
    book = load_workbook(BytesIO(template_workbook()))
    setup = book['Batch Setup']
    rows = {setup.cell(row, 3).value: row for row in range(1, setup.max_row+1)}
    for key, value in b31g_case().items():
        if key in rows:
            setup.cell(rows[key], 2).value = value
    repairs = book['Repair Cases']
    cols = {cell.value: cell.column for cell in repairs[3]}
    for row, ident, factor, override in [(5,'AUTO-72',.72,None), (6,'AUTO-60',.60,None),
                                        (7,'MANUAL',.60,2.), (8,'INVALID',0,None)]:
        for key, value in dict(repair_id=ident,original_design_factor=factor,b31g_safety_factor=override).items():
            repairs.cell(row, cols[key]).value = value
    content = BytesIO(); book.save(content)
    return content.getvalue()


def test_batch_resolves_factor_per_row_and_exports_actual_value():
    batch = prepare_workbook(factor_workbook())
    output, results = calculate_batch(batch)
    for repair, result, want in zip(batch.repairs, results, [1.388888888888889,1.666666666666667,2.]):
        assert result == evaluate_case(repair.case)
        assert result['status'] == 'CALCULATED', result['issues']
        assert result['details']['b31g']['safety_factor'] == pytest.approx(want)
    assert results[3]['status'] == 'ENGINEERING_HOLD'
    assert not results[3]['results']
    book = load_workbook(BytesIO(output))
    actual = {row[0]:row[3] for row in book['Effective Inputs'].iter_rows(min_row=5,values_only=True)
              if row[2]=='B31G safety factor used'}
    assert actual == pytest.approx({'AUTO-72':1.388888888888889,'AUTO-60':1.666666666666667,'MANUAL':2.})


def test_single_ui_recalculates_factor_and_manual_override():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'app.py'), default_timeout=20)
    for key,value in b31g_case().items():
        app.session_state['case_'+key] = value
    app.run()
    assert not app.exception
    def factor():
        return next(m.value for m in app.metric if m.label == 'B31G safety factor used')
    assert factor() == '1.3889'
    app.number_input(key='case_original_design_factor').set_value(.60).run()
    assert factor() == '1.6667'
    app.number_input(key='case_b31g_safety_factor').set_value(2.).run()
    app.button(key='calculate').click().run()
    assert factor() == '2.0000'
    assert app.session_state['calculation_results'][0]['details']['b31g']['source'] == 'Manual override'
    app.number_input(key='case_b31g_safety_factor').set_value(None).run()
    assert 'calculation_results' not in app.session_state
    assert factor() == '1.6667'


def test_batch_ui_previews_resolved_factors():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'batch_app.py'), default_timeout=20).run()
    app.get('file_uploader')[0].upload('factors.xlsx',factor_workbook()).run()
    assert not app.exception
    table = app.dataframe[0].value
    assert list(table['B31G safety factor used'][:3]) == pytest.approx([1.388888888888889,1.666666666666667,2.])


def test_batch_inherited_override_precedes_automatic_and_row_override_wins():
    book = load_workbook(BytesIO(factor_workbook()))
    setup = book['Batch Setup']
    factor_row = next(row for row in range(10,setup.max_row+1) if setup.cell(row,3).value=='b31g_safety_factor')
    setup.cell(factor_row,2).value = 1.5
    lines = book['Line Defaults']
    line_cols = {cell.value:cell.column for cell in lines[3]}
    lines.cell(5,line_cols['line_id']).value = 'LINE-A'
    lines.cell(5,line_cols['b31g_safety_factor']).value = 1.75
    repairs = book['Repair Cases']; cols = {cell.value:cell.column for cell in repairs[3]}
    repairs.cell(6,cols['line_id']).value = 'LINE-A'
    data = BytesIO(); book.save(data)
    _, results = calculate_batch(prepare_workbook(data.getvalue()))
    assert [r['details']['b31g']['safety_factor'] for r in results[:3]] == [1.5,1.75,2.]
    assert all(r['details']['b31g']['source']=='Manual override' for r in results[:3])
