"""Pressure selection and minimum-pressure defaults remain auditable in batch files."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from prowrap_v2.batch import WorkbookError, template_workbook, prepare_workbook, calculate_batch
from prowrap_v2.engine import evaluate_case
from test_engine import valid_case


def pack(book):
    out = BytesIO(); book.save(out)
    return out.getvalue()


def set_setup(book, **values):
    sheet = book['Batch Setup']
    rows = {sheet.cell(row,3).value:row for row in range(10,sheet.max_row+1)}
    for key,value in values.items():
        sheet.cell(rows[key],2).value = value


def put_row(book, title, row, **values):
    sheet = book[title]; columns = {cell.value:cell.column for cell in sheet[3]}
    for key,value in values.items():
        sheet.cell(row,columns[key]).value = value


def pressure_workbook():
    book = load_workbook(BytesIO(template_workbook()))
    case = valid_case()
    case.update(pressure_bar=70, min_pressure_bar=None)
    case.pop('repair_id')
    set_setup(book, **case)
    put_row(book, 'Repair Cases', 5, repair_id='DESIGN', maop_bar=30)
    put_row(book, 'Repair Cases', 6, repair_id='MAOP', pressure_basis='MAOP', maop_bar=30)
    put_row(book, 'Repair Cases', 7, repair_id='MISSING', pressure_basis='MAOP')
    put_row(book, 'Repair Cases', 8, repair_id='BOUNDS', pressure_basis='MAOP', maop_bar=30, min_pressure_bar=35)
    return book


def test_batch_selects_pressure_defaults_minimum_and_isolates_invalid_rows():
    batch = prepare_workbook(pack(pressure_workbook()))
    assert [r.case['min_pressure_bar'] for r in batch.repairs] == [0,0,0,35]
    assert batch.repairs[0].origins['min_pressure_bar'] == 'Calculator default'
    output,results = calculate_batch(batch)
    assert [r['status'] for r in results] == ['CALCULATED']*2 + ['INPUT_ERROR']*2
    assert [r['details']['pressure_basis']['calculation_pressure_bar'] for r in results[:2]] == [70,30]
    assert results[0]['results']['required_thickness_mm'] > results[1]['results']['required_thickness_mm']
    assert all(not r['results'] for r in results[2:])
    for repair,result in zip(batch.repairs,results):
        assert result == evaluate_case(repair.case, repair.defects, repair.loads)
    book = load_workbook(BytesIO(output))
    values = [row for row in book['Effective Inputs'].iter_rows(min_row=5, values_only=True)]
    selected = {row[0]:(row[3],row[4]) for row in values if row[2] == 'Calculation pressure [bar]'}
    assert selected['DESIGN'] == (70,'Design pressure')
    assert selected['MAOP'] == (30,'MAOP')
    raw = {(row[0],row[2]):row[3] for row in values}
    assert raw['MAOP','Design pressure [bar]'] == 70
    assert raw['MAOP','MAOP [bar]'] == 30


def test_pressure_and_minimum_overrides_follow_batch_line_repair_engineering_precedence():
    book = pressure_workbook()
    set_setup(book, pressure_basis='MAOP', maop_bar=45, min_pressure_bar=5)
    put_row(book, 'Line Defaults', 5, line_id='L1', maop_bar=40, min_pressure_bar=10)
    put_row(book, 'Repair Cases', 5, maop_bar=None)
    put_row(book, 'Repair Cases', 6, line_id='L1', maop_bar=None)
    put_row(book, 'Repair Cases', 7, line_id='L1', maop_bar=35, min_pressure_bar=15)
    put_row(book, 'Repair Cases', 8, line_id='L1', pressure_basis=None, maop_bar=None, min_pressure_bar=None)
    put_row(book, 'Load and Engineering Details', 5, repair_id='BOUNDS', pressure_basis='Design pressure', min_pressure_bar=0)
    batch = prepare_workbook(pack(book))
    assert [r.case['maop_bar'] for r in batch.repairs] == [45,40,35,40]
    assert [r.case['min_pressure_bar'] for r in batch.repairs] == [5,10,15,0]
    _,results = calculate_batch(batch)
    assert all(r['status'] == 'CALCULATED' for r in results), results
    assert [r['details']['pressure_basis']['calculation_pressure_bar'] for r in results] == [45,40,35,70]
    assert batch.repairs[-1].origins['pressure_basis'].startswith('Load and Engineering Details')


def remove_fields(book, fields):
    setup = book['Batch Setup']
    for row in range(setup.max_row,9,-1):
        if setup.cell(row,3).value in fields: setup.delete_rows(row)
    for title in ('Line Defaults','Repair Cases','Load and Engineering Details'):
        sheet = book[title]
        for cell in reversed(list(sheet[3])):
            if cell.value in fields: sheet.delete_cols(cell.column)


@pytest.mark.parametrize('without_axial', [False, True])
def test_previous_workbook_generations_preserve_design_pressure(without_axial):
    book = pressure_workbook()
    set_setup(book, ffs_method=None)
    for row in range(5,9): put_row(book,'Repair Cases',row,min_pressure_bar=None)
    missing = {'pressure_basis','maop_bar'}
    if without_axial: missing.add('axial_mawp_bar')
    remove_fields(book, missing)
    batch = prepare_workbook(pack(book))
    assert all(r.case['pressure_basis'] == 'Design pressure' for r in batch.repairs)
    assert all(r.case['min_pressure_bar'] == 0 for r in batch.repairs)
    assert all(r.case['ffs_method'] == ('External assessment' if without_axial else 'Modified B31G') for r in batch.repairs)
    _,results = calculate_batch(batch)
    assert all(r['status'] == 'CALCULATED' for r in results), results
    assert all(r['details']['pressure_basis']['calculation_pressure_bar'] == 70 for r in results)


@pytest.mark.parametrize('missing', [{'pressure_basis'}, {'maop_bar'}])
def test_partial_pressure_column_migrations_are_rejected(missing):
    book = pressure_workbook(); remove_fields(book, missing)
    with pytest.raises(WorkbookError): prepare_workbook(pack(book))


def test_mixed_old_setup_and_new_table_contract_is_rejected():
    book = pressure_workbook()
    setup = book['Batch Setup']
    for row in range(setup.max_row,9,-1):
        if setup.cell(row,3).value in {'pressure_basis','maop_bar'}: setup.delete_rows(row)
    with pytest.raises(WorkbookError): prepare_workbook(pack(book))


def test_named_load_explicit_pressure_remains_an_override_of_selected_maop():
    book = pressure_workbook()
    put_row(book, 'Load and Engineering Details', 5, repair_id='MAOP', load_id='High load', pressure_bar=60)
    batch = prepare_workbook(pack(book)); _,results = calculate_batch(batch)
    loaded = results[1]
    assert loaded['status'] == 'CALCULATED', loaded['issues']
    entries = loaded['details']['load_cases']
    assert [entry['pressure_basis']['calculation_pressure_bar'] for entry in entries] == [30,60]
    assert loaded['details']['controlling_load_id'] == 'High load'


def test_batch_app_previews_and_calculates_selected_pressure():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'batch_app.py'), default_timeout=20).run()
    app.get('file_uploader')[0].upload('pressure-basis.xlsx',pack(pressure_workbook())).run()
    assert not app.exception
    table = app.dataframe[0].value
    assert list(table['Calculation pressure [bar]'][:2]) == [70,30]
    assert list(table['Pressure basis'][:2]) == ['Design pressure','MAOP']
    app.button[0].click().run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == 'Calculated') == '2'
    assert next(m.value for m in app.metric if m.label == 'Require review') == '2'


@pytest.mark.parametrize('changes', [dict(maop_bar=0),dict(maop_bar=-5),
                                     dict(min_pressure_bar=-1),dict(install_pressure_bar=35)])
def test_batch_invalid_manual_pressure_inputs_never_issue_quantities(changes):
    book = pressure_workbook()
    put_row(book,'Repair Cases',6,**changes)
    _,results = calculate_batch(prepare_workbook(pack(book)))
    assert results[0]['status'] == 'CALCULATED'
    assert results[1]['status'] == 'INPUT_ERROR'
    assert not results[1]['results']
