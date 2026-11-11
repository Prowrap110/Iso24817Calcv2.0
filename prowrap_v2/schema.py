"""Shared input vocabulary. Engineering validation belongs to engine.evaluate_case.

UI and workbook use these same keys, labels and explicit defaults. None is unknown.
"""
from copy import deepcopy

FIELD_DEFINITIONS = {}
def _field(key, label, kind, default=None, section=1, choices=None):
    FIELD_DEFINITIONS[key] = dict(label=label, kind=kind, default=default, section=section, choices=choices)

for key,label in [('customer','Customer'),('project','Project / location'),('asset_id','Line / asset ID'),('repair_id','Repair ID'),('report_no','Report number'),('inspection_ref','Inspection reference'),('inspection_date','Inspection date'),('installation_date','Planned installation date')]:
    _field(key,label,'text','',1)
_field('product','Repair system','select','PRW110+',2,['PRW110+','PRW110'])
_field('purpose','Calculation purpose','select','Design',2,['Design','Estimate'])
_field('service_category','Service category','select','Hydrocarbon',2,['Hydrocarbon','Produced water','Flammable / toxic / aggressive','Fire water','Non-hazardous water / gas'])
_field('repair_class','Repair class','select',3,2,[1,2,3])
_field('strain_basis','Allowable strain basis','select','Default',2,['Default','LTS'])
_field('design_life_years','Design life [years]','number',20.0,2)
_field('initial_service_life_years','Initial service life [years]','number',20.0,2)
_field('component','Component','select','Straight',3,['Straight','Bend','Tee','Reducer','Flange'])
_field('material_grade','Steel material specification / grade','text','',3)
_field('design_code','Original design code','text','',3)
for key,label in [('od_mm','Pipe OD [mm]'),('wall_mm','Nominal wall [mm]'),('smys_mpa','SMYS [MPa]'),('smts_mpa','SMTS [MPa]'),('allowable_stress_mpa','Allowable substrate stress [MPa]'),('run_od_mm','Tee run OD [mm]'),('branch_od_mm','Tee branch OD [mm]')]:
    _field(key,label,'number',None,3)
_field('steel_modulus_mpa','Steel modulus [MPa]','number',200000.0,3)
_field('steel_cte','Steel thermal expansion [1/K]','number',12e-6,3)
_field('component_qualified','Applicable fitting assessment confirmed','bool',False,3)
_field('component_ref','Fitting assessment reference','text','',3)
for key,label in [('pressure_bar','Design pressure [bar]'),('min_pressure_bar','Minimum design pressure [bar]'),('temperature_c','Maximum design temperature [°C]'),('min_temperature_c','Minimum design temperature [°C]'),('install_pressure_bar','Installation pressure [bar]'),('install_temperature_c','Installation temperature [°C]')]:
    _field(key,label,'number',None,4)
_field('mechanism','Defect mechanism','select','Corrosion',5,['Corrosion','Dent no-crack','Leak','Crack','Dent w/crack'])
_field('defect_location','Defect location','select','External',5,['External','Internal'])
_field('through_wall','Current / previously through-wall (including sealed)','bool',False,5)
_field('prevent_containment','Design to prevent future loss of containment','bool',False,5)
_field('defect_mode','Corrosion defect basis','select','Actual / combined',5,['Actual / combined','Independent 10x10','Measured individual'])
for key,label in [('defect_length_mm','Defect axial length [mm]'),('defect_width_mm','Defect circumferential width [mm]'),('zone_length_mm','Overall repair-zone span [mm]'),('remaining_wall_mm','Minimum remaining wall [mm]'),('corrosion_rate_mm_year','Corrosion rate [mm/year]'),('eol_wall_mm','Assessed end-of-life wall [mm]')]:
    _field(key,label,'number',None,5)
_field('growth_basis','Future condition basis','select','',5,['','No growth confirmed','Corrosion rate','Assessed end-of-life'])
_field('growth_ref','Growth / end-of-life assessment reference','text','',5)
_field('independence_confirmed','Dimensions and noninteraction confirmed','bool',False,5)
_field('grouping_ref','Inspection / grouping assessment reference','text','',5)
_field('dent_mode','Dent geometry','select','Measured',5,['Measured','60/40 population'])
_field('dent_depth_mm','Dent depth [mm]','number',None,5)
_field('no_crack_confirmed','No-crack inspection confirmed','bool',False,5)
_field('dent_ffs_ref','Dent assessment reference','text','',5)
_field('dent_mawp_bar','Assessed dent MAWP [bar]','number',None,5)
_field('dent_complex','Dent involves weld / gouge / restraint','bool',False,5)
_field('fatigue_assessment_ref','Mechanical damage fatigue assessment reference','text','',5)
_field('seal_shape','Effective opening geometry','select','Circular',5,['Circular','Axial slot','Circumferential slot'])
_field('effective_diameter_mm','Effective circular opening diameter [mm]','number',None,5)
_field('effective_axial_mm','Effective opening axial extent [mm]','number',None,5)
_field('effective_circ_mm','Effective opening circumferential extent [mm]','number',None,5)
_field('effective_geometry_ref','Effective opening / growth / footprint reference','text','',5)
_field('stopgap_ref','Live leak-stopping procedure reference','text','',5)
_field('load_basis','Load basis','select','',6,['','Pressure-only confirmed','Additional loads'])
for key,label in [('axial_kn','Additional axial force [kN]'),('shear_kn','Additional shear force [kN]'),('bending_knm','Additional bending moment [kN·m]'),('torsion_knm','Additional torsional moment [kN·m]')]:
    _field(key,label,'number',None,6)
_field('loads_ref','Load assessment reference','text','',6)
_field('cyclic','Cyclic loading assessment required','bool',False,6)
_field('cycles','Expected cycles over design life','number',None,6)
_field('cycle_min_bar','Cycle minimum pressure [bar]','number',None,6)
_field('cycle_max_bar','Cycle maximum pressure [bar]','number',None,6)
_field('reversing_loads','Reversing or complex cyclic loads','bool',False,6)
_field('external_pressure','Vacuum / external pressure or buckling-sensitive loads','bool',False,6)
_field('external_assessment_ref','Special load assessment reference','text','',6)
_field('other_thickness_mm','Assessed additional minimum thickness [mm]','number',None,6)
_field('substrate_route','Substrate design route','select','Full laminate',7,['Full laminate','Substrate sharing','Substrate stress limit'])
_field('sharing_basis','Load-sharing design basis','select','Known allowable stress',7,['Known allowable stress','Restore original capacity','Conservative wall loss'])
_field('ffs_method','Remaining capacity assessment','select','External assessment',7,['External assessment','Modified B31G'])
_field('ffs_ref','Fitness-for-service reference','text','',7)
_field('assessed_mawp_bar','Assessed impaired-pipe MAWP [bar]','number',None,7)
_field('assessed_axial_capacity_kn','Assessed axial capacity [kN]','number',None,7)
_field('qualified_wall_loss_pct','Confirmed qualified wall-loss limit [%]','number',None,7)
_field('qualification_ref','Substrate-credit qualification reference','text','',7)
_field('original_design_factor','Original pipeline design factor','number',None,7)
_field('b31g_safety_factor','B31G assessment safety factor','number',None,7)
_field('cure_basis','Cure basis','select','Report schedule',8,['Report schedule','Confirmed qualified schedule'])
_field('cure_ref','Cure / working-strength procedure reference','text','',8)
_field('cure_temperature_c','Cure temperature [°C]','number',20.0,8)
_field('cure_hours','Cure time [hours]','number',24.0,8)
_field('landing_mode','Available sound landing','select','',8,['','Unrestricted confirmed','Restricted'])
_field('landing_left_mm','Available left landing [mm]','number',None,8)
_field('landing_right_mm','Available right landing [mm]','number',None,8)
_field('cloth_widths','Available fabric widths [mm]','select','300 and 500',8,['300','500','300 and 500'])
_field('procedure_ref','Preparation / application procedure reference','text','',8)
_field('thicker_repair_limit_mm','Test-supported thickness limit [mm]','number',None,8)
_field('thicker_repair_ref','Thicker-repair test reference','text','',8)
_field('quantity','Number of identical repairs','number',1,9)
_field('feasibility_ref','Feasibility / work-pack reference','text','',9)
_field('notes','Project notes','text','',9)

SECTIONS = {1:'Project information',2:'Product and design basis',3:'Pipe and component',4:'Pressure and temperature',5:'Defect information',6:'Loads and cycling',7:'Existing pipe capacity',8:'Installation and available space',9:'Quantities and reporting'}
DEFECT_FIELDS = ['repair_id','defect_id','length_mm','width_mm','remaining_wall_mm','separation_mm','independence_confirmed']
LOAD_FIELDS = ['repair_id','load_id','pressure_bar','min_pressure_bar','temperature_c','min_temperature_c','axial_kn','shear_kn','bending_knm','torsion_knm','cyclic','cycles','cycle_min_bar','cycle_max_bar','reversing_loads','loads_ref']

def default_case():
    return {k:deepcopy(v['default']) for k,v in FIELD_DEFINITIONS.items()}
