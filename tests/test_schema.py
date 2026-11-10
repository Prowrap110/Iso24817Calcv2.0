from prowrap_v2.schema import FIELD_DEFINITIONS, default_case

def test_schema_has_units_and_independent_defaults():
    a,b=default_case(),default_case()
    assert a['product']=='PRW110+'
    assert a['od_mm'] is None
    a['product']='PRW110'
    assert b['product']=='PRW110+'
    assert FIELD_DEFINITIONS['pressure_bar']['label']=='Design pressure [bar]'
    assert {'defect_mode','dent_mode','cycles','install_pressure_bar','min_pressure_bar'} <= a.keys()
