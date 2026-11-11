"""PROWRAP single-repair calculator v2.0; shares evaluator with CalcBatch."""
import re
from math import isfinite
import pandas as pd
import streamlit as st
from prowrap_v2 import __version__
from prowrap_v2.schema import FIELD_DEFINITIONS, SECTIONS, DEFECT_FIELDS, LOAD_FIELDS, default_case
from prowrap_v2.ui_logic import (
    OPENING_FIELDS, active_fields, case_for_calculation, uses_measured_defects,
)
from prowrap_v2.materials import get_material
from prowrap_v2.assessment import b31g_factor_details
from prowrap_v2.pressure import pressure_basis_details
from prowrap_v2.engine import evaluate_case, expand_population
from prowrap_v2.examples import example_case
from prowrap_v2.reporting import report_pdf, report_json

st.set_page_config(page_title='PROWRAP Calculator v2.0',page_icon='◉',layout='wide')
st.markdown('''<style>
.block-container {max-width:1180px;padding-top:2rem;padding-bottom:4rem;}
h1,h2,h3 {color:#142c40;} [data-testid="stMetric"] {border:1px solid #dbe3ea;border-radius:8px;padding:14px;}
[data-testid="stExpander"] {border-color:#dbe3ea;} .stButton button[kind="primary"] {background:#184d72;}
</style>''',unsafe_allow_html=True)


def clear_result(): st.session_state.pop('calculation_results',None)
def replace_case(case):
    for key in FIELD_DEFINITIONS: st.session_state['case_'+key]=case.get(key)
    for key in ['defect_editor','load_editor','calculation_results']: st.session_state.pop(key,None)
    st.session_state['defect_records']=[];st.session_state['load_records']=[]

def current_case(): return {k:st.session_state.get('case_'+k,v['default']) for k,v in FIELD_DEFINITIONS.items()}

for key,value in default_case().items():
    st.session_state.setdefault('case_'+key,value)
st.session_state.setdefault('defect_records',[])
st.session_state.setdefault('load_records',[])

st.title('PROWRAP Calculator v2.0')
st.caption('ISO 24817:2026 · Single repair · PRW110+ material basis')
left,right=st.columns([3,2])
with left: st.write('Enter the repair conditions, review the calculated checks, and download the calculation record.')
with right:
    a,b=st.columns(2)
    a.button('New calculation',key='clear',on_click=lambda:replace_case(default_case()),width='stretch')
    b.button('Load example',key='example',on_click=lambda:replace_case(example_case()),width='stretch')

HELP={
 'strain_basis':'LTS uses the owner-selected long-term strain of 0.007 (0.7%), then applies the design-life, temperature, cycling and thermal-strain factors. Default uses the standard strain route.',
 'initial_service_life_years':'Initial service life may be shorter than design life. The design equations use design life.',
 'min_pressure_bar':'Defaults to 0 bar for possible depressurization. Edit to enter a different minimum pressure for the installation/disbond assessment.',
 'pressure_bar':'Entered design pressure. Used for the base calculation when Design pressure is selected below.',
 'maop_bar':'Maximum Allowable Operating Pressure of the pipeline. Used for the base calculation when MAOP is selected below; separate from impaired-pipe MAWP and the axial-capacity MAWP override.',
 'pressure_basis':'Select the pressure used for the base repair calculation. Additional named load cases retain their explicitly entered pressure values.',
 'through_wall':'Includes a hole or leak that has already been temporarily sealed.',
 'zone_length_mm':'Full outer-to-outer span to be covered, distinct from individual pit length.',
 'load_basis':'Pressure-only includes the pressure end load. Select additional loads for axial force, shear, bending or torsion.',
 'cycles':'Total expected cycles over the design life, not cycles per year.',
 'effective_diameter_mm':'Assessor-defined effective opening, covering current and future pressurized/unbonded footprint, filler and stopgap.',
 'qualified_wall_loss_pct':'Defaults to 81% for PRW110 and PRW110+. Edit this value to apply a manual qualification limit. Assessed end-of-life wall loss must be strictly below the selected limit; all other substrate-credit checks still apply.',
 'qualification_ref':'Optional qualification reference for the calculation record. The confirmed qualified wall-loss limit and all substrate-credit checks remain required.',
 'ffs_ref':'Optional reference for the assessment record. Leaving this blank does not bypass applicability or capacity checks.',
 'grouping_ref':'Optional inspection or grouping reference for the calculation record. Dimensions and noninteraction confirmation, overall zone span and applicable measured-defect checks remain required.',
 'axial_mawp_bar':'Optional. Blank calculates axial capacity from the assessed remaining-pipe Ps (Modified B31G by default). Enter the damaged pipe MAWP in bar to override only the pressure used for axial force Fs = π × OD² × MAWP / 40000 [kN]. Hoop Ps remains unchanged; combined-stress thickness can change.',
 'assessed_axial_capacity_kn':'Existing force override retained. Clear it to use automatic Ps or the manual axial MAWP in bar. Do not enter both overrides.',
 'original_design_factor':'Enter the original pipeline design factor as a decimal, for example 0.72. Automatic B31G safety factor = max(1 / design factor, 1.25).',
 'b31g_safety_factor':'Optional manual override. Leave blank to calculate from the original pipeline design factor. The minimum accepted safety factor is 1.25.',
 'dent_mawp_bar':'Assessed maximum allowable pressure of the dented pipe. This is the remaining-pipe Ps used by the dent substrate stress-limit method; it is separate from the selected pipeline calculation pressure.',
 'dent_ffs_ref':'Reference for the assessment establishing dent MAWP and applicability. Required for measured dents and population estimates.',
 'cure_basis':'Report schedule uses the ISO 9.3 temperature-factor fallback. A confirmed qualified schedule requires its procedure reference.',
 'thicker_repair_limit_mm':'Leave blank to apply the normal min(D/6, 25 mm) limit. A larger limit requires its specific supporting test reference.',
 'putty_kg_per_repair':'Optional kg for one defect / repair zone. Blank uses the automatic allowance; zero means no putty. The amount is multiplied by Number of identical repairs exactly once.',
}

def widget(key):
    f=FIELD_DEFINITIONS[key];kw=dict(key='case_'+key,on_change=clear_result,help=HELP.get(key))
    dent = current_case().get('mechanism') == 'Dent no-crack'
    if dent and key == 'original_design_factor':
        kw['help'] = 'Enter the original pipeline design factor, for example 0.72. Dent allowable substrate stress defaults to SMYS × this factor unless a manual allowable-stress override is entered.'
    if dent and key == 'allowable_stress_mpa':
        kw['help'] = 'Optional manual allowable substrate stress. Leave blank to use SMYS × the original pipeline design factor. Installation stress and the assessed dent MAWP remain part of the calculation.'
    if dent and key == 'axial_mawp_bar':
        kw['help'] = 'Optional axial-only MAWP override. Leave blank for Fs = A × assessed dent MAWP. Zero means no axial credit; hoop Ps remains the assessed dent MAWP.'
    if f['kind']=='text': st.text_input({'ffs_ref':'Fitness-for-service reference (optional)','grouping_ref':'Inspection / grouping assessment reference (optional)','qualification_ref':'Substrate-credit qualification reference (optional)'}.get(key,f['label']),**kw)
    elif key=='pressure_basis': st.radio(f['label'],f['choices'],horizontal=True,**kw)
    elif f['kind']=='select': st.selectbox(f['label'],f['choices'],**kw)
    elif f['kind']=='bool': st.checkbox(f['label'],**kw)
    else:
        value=st.session_state.get('case_'+key)
        if value is not None:
            value=float(value)
            st.session_state['case_'+key]=value
        fmt='%.8f' if key=='steel_cte' else '%.3f'
        label='Manual B31G safety factor override (optional)' if key=='b31g_safety_factor' else f['label']
        if key == 'putty_kg_per_repair':label += ' (optional)'
        if dent and key == 'allowable_stress_mpa':label = 'Allowable substrate stress override [MPa] (optional)'
        step=0.000001 if key=='steel_cte' else .01 if key in ('original_design_factor','b31g_safety_factor') else .1 if key=='putty_kg_per_repair' else 1.0
        st.number_input(label,value=None,format=fmt,step=step,**kw)

def editor_records(fields, config, key):
    # Streamlit applies the current editor changes to this stable source on each run.
    edited = st.data_editor(
        pd.DataFrame(columns=fields), num_rows="dynamic", hide_index=True, key=key,
        on_change=clear_result, column_config=config, width="stretch",
    )
    return edited.astype(object).where(pd.notna(edited), None).to_dict("records")


for section, title in SECTIONS.items():
    with st.expander(f"{section}. {title}", expanded=section in (1, 2, 3, 4)):
        case = current_case()
        dent = case['mechanism'] == 'Dent no-crack'
        if section == 7 and dent:
            st.info('Assessed dent capacity · Substrate stress limit · ISO 24817:2026, 9.10 / 9.7.2')
            st.caption('The assessed dent MAWP in Defect information supplies the remaining-pipe capacity Ps. Enter the original design factor below or a manual allowable-stress override.')
        if section == 7 and (dent or case['substrate_route'] != 'Full laminate'):
            st.caption('Axial capacity defaults to Fs = A × Ps. Leave the axial MAWP override blank to use the assessed Ps; enter bar to override the axial basis only. Explicit zero means no axial credit.')
            st.caption('Qualified wall-loss limit defaults to 81% for PRW110 and PRW110+. Edit the percentage below for a manual override.')
        visible = active_fields(case)
        if section == 4:
            pressure_cols=st.columns(2)
            with pressure_cols[0]:widget('pressure_bar')
            with pressure_cols[1]:widget('maop_bar')
            widget('pressure_basis')
            try:
                pressure=pressure_basis_details(current_case())
                st.caption(f"Calculation pressure: {pressure['calculation_pressure_bar']:g} bar · {pressure['basis']}")
            except ValueError as ex:st.caption(str(ex))
        cols = st.columns(2)
        keys = [key for key in visible if FIELD_DEFINITIONS[key]["section"] == section and key not in OPENING_FIELDS and key != 'assessed_axial_capacity_kn']
        if section == 4:keys=['min_pressure_bar','install_pressure_bar','temperature_c','min_temperature_c','install_temperature_c']
        if dent and section == 3:keys = [key for key in keys if key != 'allowable_stress_mpa']
        if dent and section == 7:
            keys = ['original_design_factor', 'allowable_stress_mpa'] + [key for key in keys if key != 'original_design_factor']
        if section == 9:
            keys = ['quantity', 'putty_kg_per_repair'] + [key for key in keys if key not in ('quantity', 'putty_kg_per_repair')]
            st.caption('Putty per defect / repair zone: 2 kg up to 200 mm, 3 kg up to 400 mm, then +1 kg per further started 200 mm. Dents use one-third of length × width × depth at 2 kg/L. Leave the override blank to use these defaults.')
        for index, key in enumerate(keys):
            with cols[index % 2]:
                widget(key)
        if section == 7 and 'assessed_axial_capacity_kn' in visible:
            with st.expander('Existing axial-force override (optional)', expanded=case.get('assessed_axial_capacity_kn') is not None):
                widget('assessed_axial_capacity_kn')
        case = current_case()
        if section == 7 and dent:
            allowable = case.get('allowable_stress_mpa')
            source = 'Manual allowable stress'
            if allowable is None:
                smys, factor = case.get('smys_mpa'), case.get('original_design_factor')
                if smys is not None and factor is not None and isfinite(smys) and isfinite(factor) and smys > 0 and 0 < factor <= 1:
                    allowable = smys * factor
                    source = 'SMYS × original design factor'
            if allowable is not None and isfinite(allowable) and allowable > 0:
                st.caption(f'Allowable substrate stress used: {allowable:.3f} MPa · {source}')
            else:
                st.caption('Enter positive SMYS and a design factor greater than 0 and no greater than 1, or a positive manual allowable stress.')
        if section == 7 and not dent and case['substrate_route'] != 'Full laminate' and case['ffs_method'] == 'Modified B31G':
            st.caption('Automatic safety factor = max(1 ÷ original pipeline design factor, 1.25). Leave the manual override blank to use automatic calculation.')
            try:
                selected = b31g_factor_details(case)
                st.metric('B31G safety factor used', f"{selected['safety_factor']:.4f}")
                st.caption(selected['source'])
            except ValueError as error:
                st.info(str(error))
        if section == 2:
            mat = get_material(case["product"])
            st.caption(f"{case['product']} · {mat['ply_mm']:.2f} mm/ply · Hoop modulus {mat['ec_mpa']:,.0f} MPa · Axial modulus {mat['ea_mpa']:,.0f} MPa · Tg reference {mat['tg_c']:.2f}°C")
            if case['strain_basis']=='LTS':st.caption(f"Long-term strain input: {mat['lts']:.3f} ({mat['lts']*100:g}%) before design derating")
        if section == 5:
            independent = case["mechanism"] == "Corrosion" and case["defect_location"] == "External" and case["defect_mode"] != "Actual / combined"
            if independent:
                wall = case.get("wall_mm")
                threshold = f"Current threshold: {3 * wall:.2f} mm." if wall else "Enter nominal wall to display the threshold."
                st.caption(f"Independent-defect rule: separation exceeds 3t. {threshold}")
                if case["defect_mode"] == "Independent 10x10":
                    st.info("Each assessed pit is 10 × 10 mm. Enter Overall repair-zone span [mm] and confirm Dimensions and noninteraction confirmed. The inspection/grouping reference is optional.")
            if uses_measured_defects(case):
                config = {
                    "repair_id": st.column_config.TextColumn("Repair ID"),
                    "defect_id": st.column_config.TextColumn("Defect ID"),
                    "length_mm": st.column_config.NumberColumn("Axial length [mm]"),
                    "width_mm": st.column_config.NumberColumn("Circumferential width [mm]"),
                    "remaining_wall_mm": st.column_config.NumberColumn("Remaining wall [mm]"),
                    "separation_mm": st.column_config.NumberColumn("Minimum edge gap [mm]"),
                    "independence_confirmed": st.column_config.CheckboxColumn("Noninteraction confirmed"),
                }
                st.session_state["defect_records"] = editor_records(DEFECT_FIELDS, config, "defect_editor")
            else:
                st.session_state["defect_records"] = []
            if case["mechanism"] == "Dent no-crack" and case["dent_mode"] == "60/40 population":
                st.info("Population estimate: 60% at 600 × 250 mm; 40% at 300 × 500 mm; depth 6% of OD. Select Estimate and enter the total count in section 9. The no-crack inspection, dent assessment reference and assessed dent MAWP are still required.")
            opening_fields = [key for key in active_fields(case, st.session_state["defect_records"]) if key in OPENING_FIELDS]
            if opening_fields:
                st.caption("Type B includes structural hoop and axial checks plus the effective opening sealing calculation.")
                cols = st.columns(2)
                for index, key in enumerate(opening_fields):
                    with cols[index % 2]:
                        widget(key)
        if section == 6:
            with st.expander("Additional load cases (optional)"):
                st.caption("Base conditions use the selected Design pressure or MAOP. An explicit additional load-case pressure is assessed at that value; a blank pressure inherits the selected base pressure. Other populated fields override base conditions. Use the same Repair ID.")
                config = {
                    "repair_id": st.column_config.TextColumn("Repair ID"),
                    "load_id": st.column_config.TextColumn("Load case ID"),
                }
                column_type = {
                    "bool": st.column_config.CheckboxColumn,
                    "number": st.column_config.NumberColumn,
                }
                for key in LOAD_FIELDS:
                    if key not in config:
                        field = FIELD_DEFINITIONS[key]
                        config[key] = column_type.get(field["kind"], st.column_config.TextColumn)(field["label"])
                st.session_state["load_records"] = editor_records(LOAD_FIELDS, config, "load_editor")

case = case_for_calculation(current_case(), st.session_state["defect_records"])
if st.button("Calculate repair", key="calculate", type="primary", width="stretch"):
    records=[]
    try:
        for item in expand_population(case):
            defects=st.session_state['defect_records'];loads=st.session_state['load_records']
            if item['repair_id']!=case['repair_id']:
                defects=[dict(row,repair_id=item['repair_id']) for row in defects]
                loads=[dict(row,repair_id=item['repair_id']) for row in loads]
            records.append(evaluate_case(item,defects=defects,loads=loads))
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        records=[dict(repair_id=case['repair_id'],status='INPUT_ERROR',issues=[str(exc)],inputs=case,results={},checks=[],details={})]
    st.session_state['calculation_results']=records

if st.session_state.get('calculation_results'):
    st.divider();st.header('Calculation results')
    records=st.session_state['calculation_results']
    for index,result in enumerate(records):
        status=result['status'];vals=result.get('results',{});valid=status in ('CALCULATED','ESTIMATE')
        if len(records)>1: st.subheader(result['repair_id'])
        if result.get('details',{}).get('pressure_basis'):
            pressure=result['details']['pressure_basis']
            st.metric('Calculation pressure',f"{pressure['calculation_pressure_bar']:g} bar")
            st.caption('Base pressure basis: '+pressure['basis'])
        if result.get('details',{}).get('dent_capacity'):
            dent_capacity = result['details']['dent_capacity']
            st.caption(f"Dent design: {dent_capacity['route']} · {dent_capacity['source']} {dent_capacity['pressure_bar']:g} bar · Allowable substrate stress {dent_capacity['allowable_stress_mpa']:.3f} MPa ({dent_capacity['allowable_stress_source']})")
        if valid:
            (st.info if status=='ESTIMATE' else st.success)(status+' · Calculated checks completed. Review the record with the project work pack.')
            a,b,c=st.columns(3)
            a.metric('Laminate layers',str(vals['installed_plies']))
            b.metric('Laminate thickness',f"{vals['installed_thickness_mm']:.2f} mm")
            c.metric('Total repair length',f"{vals['total_repair_length_mm']:.1f} mm")
            a,b,c=st.columns(3)
            a.metric('Fabric total',f"{vals['fabric_area_m2']:.2f} m²")
            b.metric('Laminate epoxy total',f"{vals['laminate_epoxy_kg']:.2f} kg")
            c.metric('Putty total',f"{vals['putty_kg']:.2f} kg")
            st.caption(f"Putty: {vals['putty_per_repair_kg']:.3f} kg per defect × {vals.get('quantity',1):g} identical repairs = {vals['putty_kg']:.3f} kg total.")
            st.write(f"Total fabric bands: **{vals['count_500']} × 500 mm** and **{vals['count_300']} × 300 mm**. Total epoxy: **{vals['total_epoxy_kg']:.2f} kg**. Quantity: **{vals.get('quantity',1):g}**.")
            if result['inputs']['substrate_route'] != 'Full laminate':
                axial=result['details']['axial_capacity']
                a,b=st.columns(2)
                a.metric('Remaining-pipe Ps', f"{result['details']['substrate_pressure_mpa']*10:.3f} bar")
                b.metric('Axial capacity used', f"{axial['force_kn']:.3f} kN")
                st.caption(axial['source'] + (f" · Axial pressure basis {axial['pressure_bar']:.3f} bar" if axial['pressure_bar'] is not None else ''))
        else: st.error(status+' · '+ ' '.join(result.get('issues',[])))
        if result.get('checks'):
            with st.expander('Check results',expanded=not valid):st.dataframe(pd.DataFrame(result['checks']),hide_index=True,width='stretch')
        with st.expander('Calculation detail and effective inputs'):
            st.json({'inputs':result.get('inputs',{}),'details':result.get('details',{})},expanded=False)
        name=re.sub(r'[^A-Za-z0-9_.-]+','_',str(result['repair_id'] or 'repair'))
        a,b=st.columns(2)
        a.download_button('Download PDF report',report_pdf(result),file_name=f'PROWRAP_v2_{name}.pdf',mime='application/pdf',key=f'pdf{index}',width='stretch')
        b.download_button('Download calculation data',report_json(result),file_name=f'PROWRAP_v2_{name}.json',mime='application/json',key=f'json{index}',width='stretch')
    if len(records)>1:
        eligible=[r for r in records if r['status'] in ('CALCULATED','ESTIMATE')]
        if len(eligible)==len(records):
            st.subheader('Population material totals')
            st.write({label:round(sum(r['results'][key] for r in eligible),3) for label,key in [('Fabric [m²]','fabric_area_m2'),('Laminate epoxy [kg]','laminate_epoxy_kg'),('Putty [kg]','putty_kg'),('Total epoxy [kg]','total_epoxy_kg')]})
        else:st.warning('Population totals are unavailable until all groups have valid calculation results.')
st.caption(f'PROWRAP · Version {__version__} · ISO 24817:2026 calculation record for engineering review')
