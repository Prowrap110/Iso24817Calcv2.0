"""Pure ISO 24817:2026 normative calculation functions, MPa/N/mm internally.

Clause and equation references refer to ISO printed pages, not PDF offsets.
Route qualification, defect assessment and installation acceptance belong to engine.
"""
import math


def _number(value, name, minimum=None, positive=False):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        value=float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{name} must be a finite number') from None
    if not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    if positive and value <= 0:
        raise ValueError(f'{name} must be positive')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name} must be at least {minimum}')
    return value


def _n(data, key, **kw):
    return _number(data.get(key), key, **kw)


def _cyclic(case):
    """9.4, equations (3)–(5): base-10 log, capped cycles and 0.4 floor."""
    if case.get('reversing_loads'):
        raise ValueError('Reversing loads require a separate cyclic assessment')
    if not case.get('cyclic'):
        return 1.
    n=_n(case,'cycles',minimum=0)
    low=_n(case,'cycle_min_bar',minimum=0)
    high=_n(case,'cycle_max_bar',positive=True)
    if low > high:
        raise ValueError('Cycle minimum exceeds maximum')
    if n <= 7000:
        return 1.
    ratio=low/high
    slope=-.289*(1-ratio) if ratio>.4 else -.173
    return max(.4,min(1.,1+slope*math.log10(min(n,150e6)/7000)))


def _strain_and_factors(case, material, repair_type):
    """9.1, 9.3–9.5; Tables 5–8, equations (1)–(8), pp.21–25.

    Both thermal extremes are checked using the maximum-temperature derating;
    this conservatively envelopes cold mismatch without relaxing hot design strain.
    """
    life=_n(case,'design_life_years',minimum=2)
    initial=_n(case,'initial_service_life_years',positive=True)
    klass=_n(case,'repair_class')
    if klass not in (1,2,3):
        raise ValueError('Repair class must be 1, 2 or 3')
    maxlife=20 if repair_type=='B' and klass in (2,3) else 50
    maxinitial=life if repair_type=='B' and klass in (2,3) else min(life,20)
    if life>maxlife or initial>maxinitial:
        raise ValueError('Design or initial service life exceeds Table 5 limit')
    basis=case.get('strain_basis')
    if basis not in ('Default','LTS'):
        raise ValueError('Unknown allowable strain basis')
    if basis=='Default' and life>20:
        raise ValueError('Default strain route is limited to 20 years')
    temp=_n(case,'temperature_c')
    cold=_n(case,'min_temperature_c')
    install=_n(case,'install_temperature_c')
    if cold>temp:
        raise ValueError('Minimum temperature exceeds maximum temperature')
    margin=30 if repair_type=='B' and klass==3 and life>2 else 20
    maximum=_n(material,'tg_c')-margin
    if temp>maximum:
        raise ValueError(f'Design temperature exceeds {maximum:g} °C maximum')
    cure=case.get('cure_basis')
    if cure not in ('Report schedule','Confirmed qualified schedule'):
        raise ValueError('Unknown cure basis')
    factor_tm=temp if cure=='Report schedule' else maximum
    ambient=_n(material,'t_ambient_c',minimum=15)
    qualified=_n(material,'t_qualified_c')
    def derate(delta):
        return min(1.,62.5e-6*delta*delta+1.25e-3*delta+.7)
    f1=derate(factor_tm-temp)
    f2=derate(factor_tm-temp+qualified-ambient)
    fc=_cyclic(case)
    ec=_n(material,'ec_mpa',positive=True)
    ea=_n(material,'ea_mpa',positive=True)
    coeff,power={1:(.004214,.01135),2:(.003634,.00813),3:(.003061,.0044)}[klass]
    e0c=coeff*10**(-power*life)
    e0a=e0c if ea>=.5*ec else (.002768*10**(-.0221*life) if klass==1 else .001)
    delta=max(abs(temp-install),abs(cold-install))
    alpha_s=_n(case,'steel_cte')
    thermal_c=delta*abs(alpha_s-_n(material,'alpha_c'))
    thermal_a=delta*abs(alpha_s-_n(material,'alpha_a'))
    epsilon_c=fc*(f1*e0c-thermal_c)
    epsilon_a=fc*(f1*e0a-thermal_a)
    if basis=='LTS':
        perfclass=3 if life>20 else klass
        route=material.get('lts_test_route','Design-life data')
        if route=='Design-life data':
            coeff,power={1:(1.046,.00965),2:(.873,.00575),3:(.760,.00273)}[perfclass]
        elif route=='1000 h data':
            coeff,power={1:(.878,.0122),2:(.692,.007),3:(.612,.0043)}[perfclass]
        else:
            raise ValueError('Unknown performance test route')
        epsilon_c=fc*(coeff*10**(-power*life)*f2*_n(material,'lts',positive=True)-thermal_c)
    if epsilon_c<=0 or epsilon_a<=0:
        raise ValueError('Nonpositive design strain at a service temperature extreme')
    return dict(fc=fc,fT1=f1,fT2=f2,epsilon_c=epsilon_c,epsilon_a=epsilon_a,
                tm_c=maximum,factor_tm_c=factor_tm)


def calculate_structural(case, material, repair_type, ps_mpa=0, fs_n=None):
    """9.6–9.7 equations (9)–(20), pp.26–28; straight-component thickness.

    Explicit substrate capacities are trusted only after the caller's FFS gates.
    Type B and full-laminate routes always discard both capacities. Negative
    equation thickness denotes sufficient substrate capacity and is floored at 0.
    """
    if repair_type not in ('A','B'):
        raise ValueError('Repair type must be A or B')
    out=_strain_and_factors(case,material,repair_type)
    d=_n(case,'od_mm',positive=True)
    p=_n(case,'pressure_bar',minimum=0)/10
    area=math.pi*d*d/4
    ec=_n(material,'ec_mpa',positive=True)
    ea=_n(material,'ea_mpa',positive=True)
    nu=_n(material,'nu',minimum=0)
    if nu*nu*ea/ec>=1:
        raise ValueError('Invalid orthotropic Poisson ratio')
    load=[]
    for key,factor in [('axial_kn',1000),('shear_kn',1000),('bending_knm',1e6),('torsion_knm',1e6)]:
        value=case.get(key)
        # A confirmed pressure-only case has explicit zero additional loads.
        if value is None and case.get('load_basis')=='Pressure-only confirmed':
            value=0
        load.append(abs(_number(value,key))*factor)
    axial,shear,bending,torsion=load
    feqc=math.hypot(axial+4*bending/d-area*p,4*torsion/d)
    feqa=math.hypot(axial+4*bending/d+area*p,4*torsion/d)
    peq=p+(shear+2*torsion/d)/area
    ps=_number(ps_mpa,'Substrate pressure capacity',minimum=0)
    fs=area*ps if fs_n is None else _number(fs_n,'Substrate axial capacity',minimum=0)
    route=case.get('substrate_route')
    if route not in ('Full laminate','Substrate sharing','Substrate stress limit'):
        raise ValueError('Unknown substrate design route')
    if repair_type=='B' or route=='Full laminate':
        route='Full laminate'; ps=fs=0.
    pressure_term=peq-ps
    hoop_term=pressure_term-nu*(feqc-fs)/(2*area)
    axial_term=(feqa-fs)/(2*area)-nu*(ea/ec)*pressure_term
    epsc=out['epsilon_c']; epsa=out['epsilon_a']
    if route=='Substrate stress limit':
        es=_n(case,'steel_modulus_mpa',positive=True)
        allowable=_n(case,'allowable_stress_mpa',positive=True)
        pin=_n(case,'install_pressure_bar',minimum=0)/10
        ts=_n(case,'remaining_wall_mm',positive=True)
        margin=allowable-d*pin/(2*ts)
        if margin<=0:
            raise ValueError('Nonpositive substrate stress margin at installation')
        hoop=d*es/(2*margin*ec)*hoop_term
        axial_t=d*es/(2*margin*ea)*axial_term
        equations='13/14'
    else:
        hoop=d/(2*epsc*ec)*hoop_term
        axial_t=d/(2*epsa*ea)*axial_term
        equations='19/20' if route=='Full laminate' else '15/18'
        if route=='Substrate sharing':
            basis=case.get('sharing_basis')
            if basis=='Restore original capacity':
                smys=_n(case,'smys_mpa',positive=True)
                wall=_n(case,'wall_mm',positive=True)
                original=2*smys*wall/d
                hoop=d/(2*epsc*ec)*(original-ps-nu/(2*area)*(area*original-fs))
                equations='16/18'
            elif basis=='Conservative wall loss':
                smys=_n(case,'smys_mpa',positive=True)
                wall=_n(case,'wall_mm',positive=True)
                remaining=_n(case,'eol_wall_mm',minimum=0)
                if remaining>wall:
                    raise ValueError('End-of-life wall exceeds nominal wall')
                hoop=smys*(wall-remaining)/(epsc*ec)
                equations='17/18'
            elif basis!='Known allowable stress':
                raise ValueError('Unknown load-sharing basis')
    out.update(peq_mpa=peq,feq_c_n=feqc,feq_a_n=feqa,hoop_mm=max(0.,hoop),
               axial_mm=max(0.,axial_t),structural_mm=max(0.,hoop,axial_t),
               route=route,equations=equations)
    if any(not math.isfinite(v) for v in out.values() if isinstance(v,(int,float))):
        raise ValueError('Nonfinite structural calculation result')
    return out


def bond_stress(case, material, installed_mm):
    """9.14.4 equations (38)–(40), pp.35–36; signed interface stress MPa.

    Compressive (negative) q is retained; only positive tension threatens disbond.
    Substrate thickness is actual remaining wall at installation, not EOL wall.
    """
    td=_number(installed_mm,'Installed thickness',positive=True)
    ec=_n(material,'ec_mpa',positive=True)
    es=_n(case,'steel_modulus_mpa',positive=True)
    ts=_n(case,'remaining_wall_mm',minimum=0)
    d=_n(case,'od_mm',positive=True)
    pin=_n(case,'install_pressure_bar',minimum=0)/10
    pmin=_n(case,'min_pressure_bar',minimum=0)/10
    install=_n(case,'install_temperature_c')
    cold=_n(case,'min_temperature_c'); hot=_n(case,'temperature_c')
    if cold>hot:
        raise ValueError('Minimum temperature exceeds maximum temperature')
    da=_n(case,'steel_cte')-_n(material,'alpha_c')
    thermal=max(da*(install-cold),da*(install-hot))
    result=(pin-pmin)*ec*td/(es*ts+ec*td)+thermal*2*ec*td/d
    return _number(result,'Bond stress')


def component_factor(component):
    """9.11 Table 10, printed p.32; geometry qualification remains caller-owned."""
    try:
        return {'Straight':1.,'Bend':1.2,'Tee':2.,'Reducer':1.1,'Flange':1.1}[component]
    except (KeyError,TypeError):
        raise ValueError('Unknown component') from None


def tee_pressure_limit(case, material, epsilon_c, ps_mpa=0, installed_mm=None):
    """9.14.3 equation (37), p.35; final installed thickness and actual run/branch."""
    d=_n(case,'run_od_mm',positive=True)
    branch=_n(case,'branch_od_mm',positive=True)
    td=_number(case.get('installed_thickness_mm') if installed_mm is None else installed_mm,
               'Installed thickness',positive=True)
    ec=_n(material,'ec_mpa',positive=True)
    strain=_number(epsilon_c,'Hoop design strain',positive=True)
    ps=_number(ps_mpa,'Substrate pressure capacity',minimum=0)
    return _number(2*ec*strain*td/(d+branch)+ps,'Tee pressure limit',minimum=0)
