from io import BytesIO

from openpyxl import load_workbook
import pytest

from prowrap_v2.batch import WorkbookError, calculate_batch, prepare_workbook, template_workbook
from test_b31g_factor import independent_estimate


def weighted_workbook(shares=(.6, .4), failed=False):
    wb = load_workbook(BytesIO(template_workbook()))
    case = independent_estimate()
    setup = wb['Batch Setup']
    for label, _, key, _ in setup.iter_rows(min_row=10, values_only=False):
        if key.value in case:
            setup.cell(label.row, 2, case[key.value])
    repairs = wb['Repair Cases']
    columns = {c.value:c.column for c in repairs[3]}
    for row, (ident, span, share) in enumerate(zip(('R-1','R-2'),(200,400),shares),5):
        repairs.cell(row, columns['repair_id'], ident)
        repairs.cell(row, columns['zone_length_mm'], span)
        wb['Estimate Weights'].append((ident,'Group',14,5,share,7.72,.5,'D/8',44.45))
    if failed:
        repairs.cell(6, columns['independence_confirmed'], False)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def test_weighted_export_applies_shares_once_and_rounds_minimum_to_kits():
    export, results = calculate_batch(prepare_workbook(weighted_workbook()))
    book = load_workbook(BytesIO(export), data_only=True)
    total = tuple(c.value for c in book['Tender Takeoff'][5])
    assert total[:2] == ('All repairs', 5)
    area = 3*results[0]['results']['fabric_area_m2'] + 2*results[1]['results']['fabric_area_m2']
    assert total[2:7] == pytest.approx((area,2*area,12,16,2*area+16))
    assert all(r['results']['quantity'] == 1 for r in results)


def test_weighted_group_shares_must_sum_to_one():
    with pytest.raises(WorkbookError, match='totalling 100%'):
        prepare_workbook(weighted_workbook(shares=(.5,.4)))


def test_failed_case_does_not_yield_partial_procurement_total():
    export, results = calculate_batch(prepare_workbook(weighted_workbook(failed=True)))
    book = load_workbook(BytesIO(export), data_only=True)
    assert results[1]['status'] == 'ENGINEERING_HOLD'
    assert book['Tender Takeoff']['A5'].value.startswith('Incomplete weighted estimate')
    assert book['Tender Takeoff']['C5'].value is None
    assert book['Tender Scenarios']['C6'].value == 'ENGINEERING_HOLD'
