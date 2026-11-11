"""Optional qualification references must preserve numerical substrate-credit gates."""
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest

from prowrap_v2.batch import template_workbook, prepare_workbook, calculate_batch
from prowrap_v2.engine import evaluate_case
from test_engine import valid_case


def credit_case(**changes):
    case = valid_case()
    case.update(substrate_route='Substrate sharing', ffs_method='Modified B31G',
                material_grade='API 5L X52', design_code='ASME B31.8',
                allowable_stress_mpa=200, original_design_factor=.72,
                assessed_mawp_bar=10, qualified_wall_loss_pct=81,
                qualification_ref='')
    case.update(changes)
    return case


@pytest.mark.parametrize('route', ['Substrate sharing', 'Substrate stress limit'])
@pytest.mark.parametrize('method', ['Modified B31G', 'External assessment'])
@pytest.mark.parametrize('reference', ['', None])
def test_optional_qualification_reference_preserves_capacity_and_design(route, method, reference):
    case = credit_case(substrate_route=route, ffs_method=method, qualification_ref=reference)
    actual = evaluate_case(case)
    referenced = evaluate_case(dict(case, qualification_ref='PRW110+ Annex C test'))
    assert actual['status'] == 'CALCULATED', actual['issues']
    assert actual['results'] == referenced['results']
    assert actual['checks'] == referenced['checks']
    assert actual['details'] == referenced['details']
    assert referenced['inputs']['qualification_ref'] == 'PRW110+ Annex C test'


@pytest.mark.parametrize('limit', [None, -1, 101, float('nan'), float('inf'), 50, 49])
def test_missing_invalid_or_reached_limit_still_blocks_substrate_credit(limit):
    result = evaluate_case(credit_case(qualified_wall_loss_pct=limit))
    assert result['status'] in ('INPUT_ERROR', 'ENGINEERING_HOLD')
    assert not result['results']
    if limit is None:
        assert 'Confirmed qualified wall-loss limit [%]' in ' '.join(result['issues'])
        assert 'reference' not in ' '.join(result['issues']).lower()


def qualification_workbook():
    book = load_workbook(BytesIO(template_workbook()))
    setup = book['Batch Setup']
    rows = {setup.cell(r,3).value:r for r in range(10,setup.max_row+1)}
    for key,value in credit_case(qualified_wall_loss_pct=None).items():
        if key in rows: setup.cell(rows[key],2).value=value
    cases = book['Repair Cases']; cols = {c.value:c.column for c in cases[3]}
    data = [dict(repair_id='BLANK-REF', qualified_wall_loss_pct=81),
            dict(repair_id='WITH-REF', qualified_wall_loss_pct=81, qualification_ref='QUAL-01'),
            dict(repair_id='MISSING-LIMIT'),
            dict(repair_id='AT-LIMIT', qualified_wall_loss_pct=50)]
    for row,values in enumerate(data,5):
        for key,value in values.items(): cases.cell(row,cols[key]).value=value
    content = BytesIO(); book.save(content)
    return content.getvalue()


def test_batch_keeps_reference_optional_and_limit_required_per_repair():
    batch = prepare_workbook(qualification_workbook())
    output, results = calculate_batch(batch)
    assert [r['status'] for r in results] == ['CALCULATED']*2+['ENGINEERING_HOLD']*2
    assert results[0]['results'] == results[1]['results']
    for repair,result in zip(batch.repairs,results):
        assert result == evaluate_case(repair.case, repair.defects, repair.loads)
    assert all(not r['results'] for r in results[2:])
    book = load_workbook(BytesIO(output))
    assert any('QUAL-01' in row for row in book['Effective Inputs'].iter_rows(values_only=True))


def test_single_optional_reference_and_required_limit_submission():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'app.py'), default_timeout=20)
    for key,value in credit_case().items(): app.session_state['case_'+key] = value
    app.run()
    assert 'optional' in app.text_input(key='case_qualification_ref').label.lower()
    app.button(key='calculate').click().run()
    assert not app.exception
    assert app.session_state['calculation_results'][0]['status'] == 'CALCULATED'
    app.number_input(key='case_qualified_wall_loss_pct').set_value(None).run()
    app.button(key='calculate').click().run()
    result = app.session_state['calculation_results'][0]
    assert result['status'] == 'ENGINEERING_HOLD'
    assert not result['results']


def test_batch_app_accepts_blank_reference_and_keeps_limit_holds():
    app = AppTest.from_file(str(Path(__file__).parents[1]/'batch_app.py'), default_timeout=20).run()
    app.get('file_uploader')[0].upload('qualification-reference.xlsx', qualification_workbook()).run()
    app.button[0].click().run()
    assert not app.exception
    assert next(m.value for m in app.metric if m.label == 'Calculated') == '2'
    assert next(m.value for m in app.metric if m.label == 'Require review') == '2'
