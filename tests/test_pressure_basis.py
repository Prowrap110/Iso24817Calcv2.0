"""Chosen pressure must control the whole repair assessment and remain auditable."""
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from prowrap_v2.engine import evaluate_case
from prowrap_v2.reporting import report_pdf, report_json
from prowrap_v2.schema import default_case
from test_engine import valid_case
from test_qualification_reference import credit_case


def test_minimum_pressure_defaults_zero_and_manual_value_changes_bond_check():
    assert default_case()['min_pressure_bar'] == 0
    case = valid_case(); case.update(pressure_bar=60,install_pressure_bar=20)
    case.pop('min_pressure_bar')
    zero = evaluate_case(case)
    manual = evaluate_case(dict(case,min_pressure_bar=10))
    assert zero['status'] == manual['status'] == 'CALCULATED'
    assert zero['inputs']['min_pressure_bar'] == 0
    assert manual['inputs']['min_pressure_bar'] == 10
    bond = lambda r: next(c['value'] for c in r['checks'] if c['name'].startswith('Bond stress'))
    assert bond(manual) < bond(zero)


@pytest.mark.parametrize('route',['Full laminate','Substrate sharing','Substrate stress limit','Type B'])
def test_maop_matches_direct_pressure_for_all_routes_and_preserves_entered_values(route):
    case = credit_case() if route.startswith('Substrate') else valid_case()
    if route == 'Type B':
        case.update(prevent_containment=True,effective_diameter_mm=20,effective_geometry_ref='OPEN-1')
    else:case['substrate_route'] = route
    case.update(pressure_basis='MAOP',pressure_bar=70,maop_bar=30)
    actual = evaluate_case(case)
    expected = evaluate_case(dict(case,pressure_basis='Design pressure',pressure_bar=30))
    assert actual['status'] == expected['status'] == 'CALCULATED', actual['issues']
    assert actual['results'] == expected['results']
    assert actual['checks'] == expected['checks']
    assert actual['inputs']['pressure_bar'] == 70
    assert actual['inputs']['maop_bar'] == 30
    assert actual['details']['pressure_basis']['calculation_pressure_bar'] == 30
    for left,right in zip(actual['details']['load_cases'],expected['details']['load_cases']):
        assert left['structural'] == right['structural']
        assert left['sealing'] == right['sealing']
        assert left['axial_capacity'] == right['axial_capacity']


def test_maop_can_be_selected_without_entering_unused_design_pressure():
    result=evaluate_case(dict(valid_case(),pressure_basis='MAOP',pressure_bar=None,maop_bar=30))
    assert result['status']=='CALCULATED',result['issues']
    assert result['inputs']['pressure_bar'] is None


@pytest.mark.parametrize('changes',[
    {'pressure_basis':'MAOP','maop_bar':None}, {'pressure_basis':'MAOP','maop_bar':0},
    {'pressure_basis':'MAOP','maop_bar':-1}, {'pressure_basis':'MAOP','maop_bar':float('nan')},
    {'pressure_basis':'MAOP','maop_bar':float('inf')}, {'pressure_basis':'MAOP','maop_bar':True},
    {'pressure_basis':'Invalid','maop_bar':30}, {'pressure_bar':None,'maop_bar':30},
    {'pressure_basis':'MAOP','maop_bar':30,'pressure_bar':float('nan')},
    {'pressure_basis':'MAOP','maop_bar':30,'min_pressure_bar':31},
    {'pressure_basis':'MAOP','maop_bar':30,'install_pressure_bar':31},
    {'min_pressure_bar':-1},
])
def test_invalid_selected_pressure_or_bounds_never_issue_quantities(changes):
    result=evaluate_case(dict(valid_case(),pressure_bar=70,**changes)) if 'pressure_bar' not in changes else evaluate_case(dict(valid_case(),**changes))
    assert result['status']=='INPUT_ERROR',result
    assert not result['results']


def test_class_dent_and_cycle_bounds_use_selected_maop():
    case=dict(valid_case(),pressure_bar=70,maop_bar=20,pressure_basis='MAOP',
              repair_class=2,service_category='Non-hazardous water / gas')
    assert evaluate_case(case)['status']=='CALCULATED'
    assert evaluate_case(dict(case,maop_bar=21))['status']=='ENGINEERING_HOLD'
    dent=dict(valid_case(),pressure_bar=70,maop_bar=30,pressure_basis='MAOP',
              mechanism='Dent no-crack',dent_depth_mm=10,no_crack_confirmed=True,
              dent_ffs_ref='DENT-1',dent_mawp_bar=35)
    assert evaluate_case(dent)['status']=='CALCULATED'
    assert evaluate_case(dict(dent,maop_bar=36))['status']=='ENGINEERING_HOLD'
    cycles=dict(valid_case(),pressure_bar=70,maop_bar=30,pressure_basis='MAOP',
                cyclic=True,cycles=100,cycle_min_bar=0,cycle_max_bar=31)
    result=evaluate_case(cycles)
    assert result['status']=='INPUT_ERROR'
    assert 'pressure bounds' in ' '.join(result['issues'])


def test_explicit_load_pressure_overrides_selected_base_without_losing_either():
    case=dict(valid_case(),pressure_bar=90,maop_bar=30,pressure_basis='MAOP')
    loads=[dict(load_id='Higher',pressure_bar=60),dict(load_id='Inherited',temperature_c=45)]
    actual=evaluate_case(case,loads=loads)
    expected=evaluate_case(dict(case,pressure_basis='Design pressure',pressure_bar=30),loads=loads)
    assert actual['status']=='CALCULATED',actual['issues']
    assert actual['results']==expected['results']
    assert actual['checks']==expected['checks']
    details=[r['pressure_basis'] for r in actual['details']['load_cases']]
    assert [p['calculation_pressure_bar'] for p in details]==[30,60,30]
    assert [p['basis'] for p in details]==['MAOP','Load-case pressure override','MAOP']
    assert actual['inputs']['pressure_bar']==90
    assert actual['details']['controlling_load_id']=='Higher'
    invalid=evaluate_case(case,loads=[dict(load_id='Zero',pressure_bar=0)])
    assert invalid['status']=='INPUT_ERROR' and not invalid['results']


def test_report_records_original_pressures_and_selected_basis():
    result=evaluate_case(dict(valid_case(),pressure_bar=70,maop_bar=30,pressure_basis='MAOP'))
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(report_pdf(result))).pages)
    assert 'Calculation pressure [bar]: 30 | Basis: MAOP' in text
    assert 'Design pressure [bar]: 70' in text
    assert 'MAOP [bar]: 30' in text
    assert b'"calculation_pressure_bar": 30' in report_json(result)


def test_named_load_called_base_still_records_its_explicit_pressure_override():
    result=evaluate_case(dict(valid_case(),maop_bar=20,pressure_basis='MAOP'),
                         loads=[dict(load_id='Base',pressure_bar=40)])
    assert result['status']=='CALCULATED',result['issues']
    entries=result['details']['load_cases']
    assert entries[0]['pressure_basis']['basis']=='MAOP'
    assert entries[1]['pressure_basis']['basis']=='Load-case pressure override'
    assert entries[1]['pressure_basis']['calculation_pressure_bar']==40


def test_single_ui_selection_minimum_override_and_clear_required_maop():
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=20)
    case=dict(valid_case(),pressure_bar=60,maop_bar=30)
    case.pop('min_pressure_bar')
    for key,value in case.items():app.session_state['case_'+key]=value
    app.run()
    assert app.number_input(key='case_min_pressure_bar').value==0
    assert app.radio(key='case_pressure_basis').value=='Design pressure'
    app.button(key='calculate').click().run()
    design=app.session_state['calculation_results'][0]
    assert design['details']['pressure_basis']['calculation_pressure_bar']==60
    app.radio(key='case_pressure_basis').set_value('MAOP').run()
    assert 'calculation_results' not in app.session_state
    app.number_input(key='case_min_pressure_bar').set_value(5).run()
    app.button(key='calculate').click().run()
    maop=app.session_state['calculation_results'][0]
    assert maop['status']=='CALCULATED'
    assert maop['inputs']['min_pressure_bar']==5
    assert maop['inputs']['pressure_bar']==60
    assert maop['details']['pressure_basis']['calculation_pressure_bar']==30
    assert maop['results']['required_thickness_mm'] < design['results']['required_thickness_mm']
    app.number_input(key='case_maop_bar').set_value(None).run()
    app.button(key='calculate').click().run()
    missing=app.session_state['calculation_results'][0]
    assert missing['status']=='INPUT_ERROR' and not missing['results']
    app.radio(key='case_pressure_basis').set_value('Design pressure').run()
    app.button(key='calculate').click().run()
    assert app.session_state['calculation_results'][0]['status']=='CALCULATED'
    assert not app.exception
