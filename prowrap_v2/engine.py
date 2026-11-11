"""Shared evaluator. Failed checks never expose an installation schedule."""
import math
from copy import deepcopy
from .schema import default_case, FIELD_DEFINITIONS, LOAD_FIELDS
from .materials import get_material
from .physics import calculate_structural, bond_stress, component_factor, tee_pressure_limit
from .sealing import solve_seal
from .assessment import substrate_capacity, b31g_factor_details, axial_capacity_details
from .procurement import quantities

class Hold(ValueError):pass
class InputError(ValueError):pass

def _required(c,*keys):
    missing=[FIELD_DEFINITIONS.get(k,{}).get('label',k) for k in keys if c.get(k) is None or c.get(k)=='']
    if missing:raise InputError('Missing required input: '+', '.join(missing)+'.')

def _validate(c):
    for k,f in FIELD_DEFINITIONS.items():
        v=c.get(k)
        if f['kind']=='number' and v is not None:
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise InputError(f"{f['label']} must be a finite number.")
        if f['kind']=='bool' and not isinstance(v,bool):raise InputError(f"{f['label']} must be an explicit true/false value.")
        if f['kind']=='select' and v not in f['choices']:raise InputError(f"Unknown {f['label']} selection.")
    _required(c,'od_mm','wall_mm','smys_mpa','pressure_bar','min_pressure_bar','temperature_c','min_temperature_c','install_pressure_bar','install_temperature_c','cure_temperature_c','remaining_wall_mm','defect_length_mm','defect_width_mm','load_basis','landing_mode')
    for k in ('od_mm','wall_mm','smys_mpa','steel_modulus_mpa','defect_length_mm','defect_width_mm','design_life_years','initial_service_life_years','cure_hours','quantity'):
        if c[k]<=0:raise InputError(f'{k} must be greater than zero.')
    if c['wall_mm']>=c['od_mm']/2:raise InputError('Nominal wall must be below half the outside diameter.')
    if not 0<=c['remaining_wall_mm']<=c['wall_mm']:raise InputError('Remaining wall must be between zero and nominal wall.')
    if c['quantity']!=int(c['quantity']):raise InputError('Quantity must be a whole number.')
    if c['pressure_bar']<=0 or not 0<=c['min_pressure_bar']<=c['pressure_bar'] or not 0<=c['install_pressure_bar']<=c['pressure_bar']:raise InputError('Pressure bounds and installation pressure must lie between zero and design pressure.')
    if c['min_temperature_c']>c['temperature_c']:raise InputError('Minimum temperature exceeds maximum temperature.')
    if c.get('zone_length_mm') is not None and c['zone_length_mm']<c['defect_length_mm']:raise InputError('Repair-zone span cannot be smaller than the entered defect length.')
    for k in ('corrosion_rate_mm_year','assessed_mawp_bar','axial_mawp_bar','assessed_axial_capacity_kn','other_thickness_mm','dent_depth_mm','effective_diameter_mm','effective_axial_mm','effective_circ_mm','landing_left_mm','landing_right_mm','thicker_repair_limit_mm'):
        if c.get(k) is not None and c[k]<0:raise InputError(f'{k} cannot be negative.')
    if c['load_basis']=='Pressure-only confirmed':
        if any(c.get(k) not in (None,0) for k in ('axial_kn','shear_kn','bending_knm','torsion_knm')):raise InputError('Pressure-only confirmation conflicts with entered additional loads.')
        for k in ('axial_kn','shear_kn','bending_knm','torsion_knm'):c[k]=0.
    else:
        _required(c,'axial_kn','shear_kn','bending_knm','torsion_knm','loads_ref')
    if c['cyclic']:
        _required(c,'cycles','cycle_min_bar','cycle_max_bar')
        if c['cycles']<0 or not c['min_pressure_bar']<=c['cycle_min_bar']<=c['cycle_max_bar']<=c['pressure_bar'] or c['cycle_max_bar']<=0:
            raise InputError('Cycle count and pressure bounds must fit the design pressure envelope.')
    if c['repair_class']<3 and c['service_category'] in ('Hydrocarbon','Produced water','Flammable / toxic / aggressive'):raise Hold('This hazardous-service case requires Class 3 or an explicit service-class assessment.')
    if c['repair_class']<3 and c['pressure_bar']>20:raise Hold('Classes 1 and 2 are limited to design pressure up to 20 bar.')
    if c['repair_class']==1 and (c['temperature_c']>40 or c['service_category']=='Fire water'):raise Hold('Class 1 is limited to 40°C and utility services; fire water requires at least Class 2.')
    if c['repair_class']==2 and c['temperature_c']>100:raise Hold('Class 2 is limited to design temperature up to 100°C.')
    if c['mechanism'] in ('Crack','Dent w/crack'):raise Hold('Crack-associated damage requires a separate referenced crack-growth, fatigue and repair assessment; this evaluator does not establish acceptance.')
    if c['external_pressure'] or c['reversing_loads']:
        raise Hold('External pressure or reversing/complex loads require a dedicated engineering assessment outside this evaluator.')
    if c['component']!='Straight' and (not c['component_qualified'] or not c['component_ref']):raise Hold('Fitting geometry requires an applicable fitting assessment and reference.')
    if c['component']=='Tee':_required(c,'run_od_mm','branch_od_mm')
    if c['cure_basis']=='Report schedule' and (c['cure_temperature_c']<20 or c['cure_hours']<24):raise Hold('The report cure schedule requires at least 20°C for 24 hours.')
    if c['cure_basis']=='Confirmed qualified schedule' and not c['cure_ref']:raise Hold('A confirmed qualified cure schedule requires its procedure reference.')

def _future(c,remaining):
    if c['growth_basis']=='No growth confirmed':
        if not c['growth_ref']:raise Hold('No-growth confirmation requires an assessment reference.')
        return remaining
    if c['growth_basis']=='Corrosion rate':
        _required(c,'corrosion_rate_mm_year','growth_ref')
        return max(0,remaining-c['corrosion_rate_mm_year']*c['design_life_years'])
    if c['growth_basis']=='Assessed end-of-life':
        _required(c,'eol_wall_mm','growth_ref')
        if not 0<=c['eol_wall_mm']<=remaining:raise InputError('Assessed end-of-life wall must be within current remaining wall.')
        return c['eol_wall_mm']
    raise Hold('Select a supported future-condition basis and reference.')

def _groups(c,defects):
    if c['defect_mode']=='Actual / combined':return [dict(length_mm=c['defect_length_mm'],width_mm=c['defect_width_mm'],remaining_wall_mm=c['remaining_wall_mm'])]
    if c['mechanism']!='Corrosion' or c['defect_location']!='External':raise Hold('Independent-defect treatment is limited to external corrosion.')
    if not c['independence_confirmed'] or not c['grouping_ref']:raise Hold('Independent defects require confirmed dimensions, noninteraction and an inspection/grouping reference.')
    if c.get('zone_length_mm') is None:raise InputError('Independent defects require the overall repair-zone span.')
    if c['defect_mode']=='Independent 10x10':
        return [dict(length_mm=10.,width_mm=10.,remaining_wall_mm=c['remaining_wall_mm'])]
    if not defects:raise InputError('Measured-individual mode requires linked defect records.')
    out=[];ids=set()
    for d in defects:
        if d.get('repair_id') not in (None,'',c['repair_id']):raise InputError('Linked defect Repair ID does not match the case.')
        ident=d.get('defect_id')
        if not ident or ident in ids:raise InputError('Measured defects require unique defect IDs.')
        ids.add(ident)
        for k in ('length_mm','width_mm','remaining_wall_mm'):
            v=d.get(k)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or (k!='remaining_wall_mm' and v==0):raise InputError(f'Measured defect {k} must be finite and within its valid range.')
        if d['remaining_wall_mm']>c['wall_mm']:raise InputError('Measured defect wall exceeds nominal wall.')
        separation=d.get('separation_mm')
        if separation is not None:
            if isinstance(separation,bool) or not isinstance(separation,(int,float)) or not math.isfinite(separation):raise InputError('Defect separation must be finite.')
            if separation<=3*c['wall_mm']:raise Hold('Measured spacing must exceed 3t; use combined/mapped assessment for interacting defects.')
        elif d.get('independence_confirmed') is not True:raise Hold('Each measured defect needs >3t spacing or confirmed noninteraction under the grouping assessment.')
        if d.get('independence_confirmed') not in (None,True,False):raise InputError('Defect independence confirmation must be true/false.')
        out.append(dict(d))
    if max(d['length_mm'] for d in out)>c['zone_length_mm']:raise InputError('Measured flaw is longer than repair-zone span.')
    return out

def expand_population(case):
    c=deepcopy(case)
    if c.get('dent_mode')!='60/40 population' or c.get('mechanism')!='Dent no-crack':return [c]
    if c.get('purpose')!='Estimate':return [c]
    q=c.get('quantity',1)
    if isinstance(q,bool) or not isinstance(q,(float,int)) or not math.isfinite(q) or q<=0 or q!=int(q):return [c]
    # Largest-remainder allocation, with total count strictly preserved.
    od=c.get('od_mm')
    if isinstance(od,bool) or not isinstance(od,(float,int)) or not math.isfinite(od) or od<=0:return [c]
    n1=int(math.floor(.6*q+.5));n2=int(q)-n1;out=[]
    for suffix,n,L,W in [('60',n1,600.,250.),('40',n2,300.,500.)]:
        if not n:continue
        row=deepcopy(c);row.update(repair_id=str(c.get('repair_id',''))+'-D'+suffix,quantity=n,defect_length_mm=L,defect_width_mm=W,zone_length_mm=L,dent_depth_mm=.06*c['od_mm'],population_estimate=True)
        out.append(row)
    return out

def evaluate_case(case,defects=None,loads=None):
    c=default_case();c.update(deepcopy(case));r=dict(repair_id=c.get('repair_id',''),status='INPUT_ERROR',issues=[],inputs=c,results={},checks=[],details={})
    try:
        _validate(c)
        entered_putty_length=c.get('zone_length_mm') or c['defect_length_mm']
        population_mode=c['purpose']=='Estimate' and c['dent_mode']=='60/40 population' and c['mechanism']=='Dent no-crack'
        if c.get('population_estimate') and not population_mode:
            raise Hold('Population assumptions are permitted only in the explicit 60/40 dent Estimate mode.')
        c['population_estimate']=False
        if c['dent_mode']=='60/40 population' and c['mechanism']=='Dent no-crack':
            if c['purpose']!='Estimate':raise Hold('60/40 assumed dent geometry is an estimate and cannot establish an individual Design.')
            if (c['defect_length_mm'],c['defect_width_mm']) not in ((600.,250.),(300.,500.)) or c.get('dent_depth_mm')!=.06*c['od_mm']:
                raise Hold('Expand the 60/40 population into its prescribed geometry groups before evaluating.')
            c['population_estimate']=True
        if c['mechanism']=='Dent no-crack':
            _required(c,'dent_depth_mm')
            if not c.get('population_estimate'):
                if not c['no_crack_confirmed'] or not c['inspection_ref'] or not c['dent_ffs_ref'] or c['dent_mawp_bar'] is None:raise Hold('Dent assessment requires no-crack inspection and a referenced dent FFS MAWP.')
                if c['pressure_bar']>c['dent_mawp_bar']:raise Hold('Design pressure exceeds the assessed dent MAWP; no nominal-wall pressure credit is substituted.')
                if c['dent_complex']:raise Hold('Dent with weld, gouge or restraint requires a dedicated damage assessment.')
                if c['cyclic']:raise Hold('Cyclic dent life extension requires a dedicated Annex H fatigue assessment outside this evaluator.')
            if c['substrate_route']!='Full laminate':raise Hold('Dent calculations use the full-laminate route; corrosion substrate-credit rules do not establish dent acceptance.')
        gs=_groups(c,defects)
        for g in gs:g['eol_wall_mm']=_future(c,g['remaining_wall_mm'])
        eol=min(g['eol_wall_mm'] for g in gs);c['eol_wall_mm']=eol
        c['remaining_wall_mm']=min(c['remaining_wall_mm'],min(g['remaining_wall_mm'] for g in gs))
        repair_type='B' if c['through_wall'] or c['mechanism']=='Leak' or c['prevent_containment'] or eol<1 else 'A'
        r['details'].update(repair_type=repair_type,eol_wall_mm=eol,defects=gs,independence_threshold_mm=3*c['wall_mm'])
        if repair_type=='B':
            _required(c,'effective_geometry_ref')
            if c['seal_shape']=='Circular':_required(c,'effective_diameter_mm')
            else:_required(c,'effective_axial_mm','effective_circ_mm')
            # The rounded effective opening governs both sealing and full-thickness axial coverage.
            for key in ('effective_diameter_mm','effective_axial_mm','effective_circ_mm'):
                if c.get(key) is not None:
                    if c[key]<=0:raise InputError('Effective opening dimensions must be positive.')
                    c[key]=math.ceil(max(15.,c[key])/5)*5
            axial_footprint=c['effective_diameter_mm'] if c['seal_shape']=='Circular' else c['effective_axial_mm']
            c['zone_length_mm']=max(c.get('zone_length_mm') or c['defect_length_mm'],axial_footprint)
            r['details']['effective_axial_footprint_mm']=axial_footprint
            if c['through_wall'] or c['mechanism']=='Leak':
                if c['install_pressure_bar']>0 and not c['stopgap_ref']:raise Hold('Live through-wall application requires a leak-stopping procedure reference.')
            if c['substrate_route']!='Full laminate':raise Hold('Type B uses full laminate hoop and axial structural checks; substrate credit is unavailable.')
        try:ps,fs=substrate_capacity(c,gs,eol)
        except ValueError as ex:raise Hold(str(ex)) from ex
        if c['substrate_route']!='Full laminate' and c['ffs_method']=='Modified B31G':
            r['details']['b31g']=b31g_factor_details(c)
        material=get_material(c['product']);r['details']['substrate_pressure_mpa']=ps
        r['details']['axial_capacity']=axial_capacity_details(c,ps)
        effective=[('Base',deepcopy(c))];ids=set()
        for i,load in enumerate(loads or []):
            unsupported=set(load).difference(set(LOAD_FIELDS)|{'other_thickness_mm'})
            if unsupported:raise InputError('Named load records cannot override repair state or geometry: '+', '.join(sorted(unsupported))+'.')
            if load.get('repair_id') not in (None,'',c['repair_id']):raise InputError('Linked load Repair ID does not match the case.')
            ident=load.get('load_id')
            if not ident or ident in ids:raise InputError('Load records require unique Load IDs.')
            ids.add(ident);lc=deepcopy(c)
            lc.update({k:v for k,v in load.items() if k not in ('repair_id','load_id') and v is not None and v!=''})
            if any(load.get(k) not in (None,'',0) for k in ('axial_kn','shear_kn','bending_knm','torsion_knm')):lc['load_basis']='Additional loads'
            _validate(lc)
            if c['mechanism']=='Dent no-crack' and not c.get('population_estimate'):
                if lc['pressure_bar']>c['dent_mawp_bar']:raise Hold('Additional load-case pressure exceeds the assessed dent MAWP.')
                if lc['cyclic']:raise Hold('A cyclic dent load case requires a dedicated Annex H fatigue assessment.')
            if c['substrate_route']!='Full laminate' and c['ffs_method']=='External assessment' and lc['temperature_c']>c['temperature_c']:
                raise Hold('The additional hotter load case needs a temperature-specific substrate capacity assessment.')
            if c['substrate_route']!='Full laminate' and lc['temperature_c']>c['temperature_c'] and any((c.get(k) or 0)>0 for k in ('axial_mawp_bar','assessed_axial_capacity_kn')):
                raise Hold('The additional hotter load case needs a temperature-specific manual axial capacity assessment.')
            effective.append((ident,lc))
        entries=[]
        for ident,lc in effective:
            try: load_ps,load_fs=substrate_capacity(lc,gs,eol)
            except ValueError as ex:raise Hold(str(ex)) from ex
            st=calculate_structural(lc,material,repair_type,ps_mpa=load_ps,fs_n=load_fs)
            seal=solve_seal(lc,material,st['fc'],st['fT2']) if repair_type=='B' else dict(seal_mm=0,equation=None)
            d=lc.get('effective_diameter_mm')
            overlap=max(50,4*d) if seal['equation']==21 and d<.5*math.sqrt(lc['od_mm']*lc['wall_mm']) else max(50,2*math.sqrt(lc['od_mm']*lc['wall_mm']))
            transfer=3*material['ea_mpa']*st['epsilon_a']*st['axial_mm']/material['lap_shear_mpa']
            overlap=max(overlap,transfer*(1+1e-9))
            entry=dict(load_id=ident,structural=st,sealing=seal,overlap_mm=overlap,transfer_mm=transfer,other_thickness_mm=lc.get('other_thickness_mm') or 0)
            entry['substrate_pressure_mpa']=load_ps
            entry['axial_capacity']=axial_capacity_details(lc,load_ps)
            entries.append(entry)
        overlap=max(x['overlap_mm'] for x in entries);extent=1.
        if c['landing_mode']=='Restricted':
            _required(c,'landing_left_mm','landing_right_mm')
            available=min(c['landing_left_mm'],c['landing_right_mm'])
            if available<25:raise ValueError('Restricted sound landing is below the 25 mm minimum.')
            extent=max(1,(overlap/available)**(2/3))
            if extent>2.5:raise ValueError('Restricted landing requires an extent factor above 2.5.')
        factor=component_factor(c['component'])
        for entry in entries:entry['required_mm']=factor*extent*max(entry['structural']['structural_mm'],entry['sealing']['seal_mm'],entry['other_thickness_mm'])
        control=max(entries,key=lambda x:x['required_mm']);required=control['required_mm']
        plies=max(2,material['min_typeb_plies'] if repair_type=='B' else 2,math.ceil(max(2,required)/material['ply_mm']))
        installed=plies*material['ply_mm']
        r['details'].update(load_cases=entries,controlling_load_id=control['load_id'],required_thickness_mm=required,candidate_installed_mm=installed,component_factor=factor,extent_factor=extent)
        def check(name,value,limit,clause):
            passed=math.isfinite(value) and value<=limit+1e-9
            r['checks'].append(dict(name=name,passed=passed,value=value,limit=limit,clause=clause))
            if not passed:r['issues'].append(f'{name} failed ({value:.6g} > {limit:.6g}).')
        cap=min(c['od_mm']/6,25)
        if c.get('thicker_repair_limit_mm') is not None:
            if not c['thicker_repair_ref']:raise Hold('A thicker-repair limit requires its supporting test reference.')
            cap=max(cap,c['thicker_repair_limit_mm'])
        check('Installed thickness',installed,cap,'9.14.2 / (36)')
        for (ident,lc),entry in zip(effective,entries):
            check('Bond stress — '+ident,bond_stress(lc,material,installed),material['lap_shear_mpa']/3,'9.14.4 / (38)–(41)')
            if c['component']=='Tee':check('Tee pressure — '+ident,entry['structural']['peq_mpa'],tee_pressure_limit(lc,material,entry['structural']['epsilon_c'],ps_mpa=ps,installed_mm=installed),'9.14.3 / (37)')
        if r['issues']:r['status']='NO_VALID_DESIGN';return r
        zone=c.get('zone_length_mm') or c['defect_length_mm'];taper=5*installed
        if c['landing_mode']=='Restricted':
            lengths=[v if v<overlap else overlap+taper for v in (c['landing_left_mm'],c['landing_right_mm'])];total=zone+sum(lengths)
        else:total=zone+2*(overlap+taper)
        procurement_case=deepcopy(c);procurement_case['zone_length_mm']=entered_putty_length
        outputs=dict(installed_plies=plies,installed_thickness_mm=installed,required_thickness_mm=required,total_repair_length_mm=total,overlap_mm=overlap,**quantities(procurement_case,total,plies,installed))
        if any(not math.isfinite(v) or v<0 for v in outputs.values()):
            raise ValueError('Nonfinite or invalid final dimensions/material quantities; no installation schedule issued.')
        r['results']=outputs
        r['status']='ESTIMATE' if c['purpose']=='Estimate' else 'CALCULATED'
        if r['status']=='ESTIMATE':r['details']['estimate_label']='Estimate — assumed geometry / quantities; individual repair acceptance is not established.'
        return r
    except InputError as ex:r['status']='INPUT_ERROR';r['issues'].append(str(ex))
    except Hold as ex:r['status']='ENGINEERING_HOLD';r['issues'].append(str(ex))
    except (ValueError,ArithmeticError,TypeError,KeyError) as ex:r['status']='NO_VALID_DESIGN';r['issues'].append(str(ex))
    r['results']={}
    return r
