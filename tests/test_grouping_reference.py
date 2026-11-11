"""An optional grouping reference must not disable independent-defect checks."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from prowrap_v2.batch import template_workbook, prepare_workbook, calculate_batch
from prowrap_v2.engine import evaluate_case
from test_engine import valid_case


def independent_case(**changes):
    case = valid_case()
    case.update(defect_mode='Independent 10x10', zone_length_mm=400,
                independence_confirmed=True, grouping_ref='')
    case.update(changes)
    return case


def measured_defect(**changes):
    defect = dict(defect_id='PIT-1', length_mm=10, width_mm=10,
                  remaining_wall_mm=5, separation_mm=31)
    defect.update(changes)
    return defect


@pytest.mark.parametrize('mode', ['Independent 10x10', 'Measured individual'])
@pytest.mark.parametrize('reference', ['', None])
def test_blank_grouping_reference_preserves_calculated_design(mode, reference):
    defects = [measured_defect()] if mode == 'Measured individual' else None
    referenced = evaluate_case(independent_case(defect_mode=mode, grouping_ref='MAP-01'), defects)
    actual = evaluate_case(independent_case(defect_mode=mode, grouping_ref=reference), defects)
    assert actual['status'] == 'CALCULATED', actual['issues']
    assert actual['results'] == referenced['results']
    assert actual['details'] == referenced['details']
    assert actual['checks'] == referenced['checks']
    assert referenced['inputs']['grouping_ref'] == 'MAP-01'


@pytest.mark.parametrize('changes,status,issue', [
    ({'independence_confirmed':False}, 'ENGINEERING_HOLD', 'confirmed dimensions'),
    ({'defect_location':'Internal'}, 'ENGINEERING_HOLD', 'external corrosion'),
    ({'zone_length_mm':None}, 'INPUT_ERROR', 'overall repair-zone span'),
    ({'defect_mode':'Measured individual'}, 'INPUT_ERROR', 'linked defect records'),
    ({'mechanism':'Dent no-crack','dent_mode':'60/40 population','purpose':'Estimate',
      'defect_length_mm':600.,'defect_width_mm':250.,'zone_length_mm':600.,'dent_depth_mm':.06*323.9,
      'no_crack_confirmed':True,'inspection_ref':'I1','dent_ffs_ref':'D1','dent_mawp_bar':30,
      'original_design_factor':.72,'remaining_wall_mm':10},
     'ENGINEERING_HOLD', 'external corrosion'),
])
def test_blank_reference_does_not_bypass_independent_applicability(changes, status, issue):
    actual = evaluate_case(independent_case(**changes))
    assert actual['status'] == status
    assert issue in ' '.join(actual['issues'])
    assert actual['results'] == {}


@pytest.mark.parametrize('changes,status,issue', [
    ({'separation_mm':30}, 'ENGINEERING_HOLD', 'exceed 3t'),
    ({'separation_mm':None}, 'ENGINEERING_HOLD', 'spacing or confirmed noninteraction'),
    ({'remaining_wall_mm':11}, 'INPUT_ERROR', 'wall exceeds nominal'),
    ({'length_mm':0}, 'INPUT_ERROR', 'valid range'),
])
def test_measured_geometry_checks_remain_without_reference(changes, status, issue):
    actual = evaluate_case(independent_case(defect_mode='Measured individual'), [measured_defect(**changes)])
    assert actual['status'] == status
    assert issue in ' '.join(actual['issues'])
    assert not actual['results']


def pack(book):
    content=BytesIO(); book.save(content)
    return content.getvalue()


def grouping_workbook():
    book = load_workbook(BytesIO(template_workbook()))
    setup = book['Batch Setup']
    rows = {setup.cell(r,3).value:r for r in range(10,setup.max_row+1)}
    for key,value in independent_case().items():
        if key in rows: setup.cell(rows[key],2).value=value
    cases=book['Repair Cases']; cols={c.value:c.column for c in cases[3]}
    data=[dict(repair_id='TEN-BLANK'), dict(repair_id='MEASURED-BLANK',defect_mode='Measured individual'),
          dict(repair_id='SPACING-FAIL',defect_mode='Measured individual'),
          dict(repair_id='CONFIRM-FAIL',independence_confirmed=False)]
    for row,values in enumerate(data,5):
        for key,value in values.items(): cases.cell(row,cols[key]).value=value
    sheet=book['Defect Details']; cols={c.value:c.column for c in sheet[3]}
    for row,repair,gap in [(5,'MEASURED-BLANK',31),(6,'SPACING-FAIL',30)]:
        for key,value in dict(repair_id=repair,**measured_defect(separation_mm=gap)).items():
            sheet.cell(row,cols[key]).value=value
    return pack(book)


def test_batch_blank_reference_matches_single_and_isolates_invalid_rows():
    batch=prepare_workbook(grouping_workbook())
    _,results=calculate_batch(batch)
    assert [r['status'] for r in results] == ['CALCULATED']*2+['ENGINEERING_HOLD']*2
    for repair,result in zip(batch.repairs,results):
        assert not repair.case['grouping_ref']
        assert result == evaluate_case(repair.case,repair.defects,repair.loads)
    assert all(not r['results'] for r in results[2:])


def test_single_optional_reference_submission_keeps_confirmation_required():
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=20)
    for key,value in independent_case().items(): app.session_state['case_'+key]=value
    app.run()
    field=app.text_input(key='case_grouping_ref')
    assert 'optional' in field.label.lower()
    app.button(key='calculate').click().run()
    assert not app.exception
    assert app.session_state['calculation_results'][0]['status']=='CALCULATED'
    app.checkbox(key='case_independence_confirmed').uncheck().run()
    app.button(key='calculate').click().run()
    result=app.session_state['calculation_results'][0]
    assert result['status']=='ENGINEERING_HOLD'
    assert not result['results']


def test_batch_app_accepts_blank_reference_and_preserves_holds():
    app=AppTest.from_file(str(Path(__file__).parents[1]/'batch_app.py'),default_timeout=20).run()
    app.get('file_uploader')[0].upload('grouping-reference.xlsx',grouping_workbook()).run()
    app.button[0].click().run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label=='Calculated')=='2'
    assert next(m.value for m in app.metric if m.label=='Require review')=='2'
