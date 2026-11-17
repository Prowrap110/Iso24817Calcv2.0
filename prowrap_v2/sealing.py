"""ISO 24817:2026 equations 21–24. MPa, mm, N/mm throughout."""
import math

def leak_factor(repair_class, life):
    a,b={1:(.87,.02088),2:(.78,.01856),3:(.69,.01584)}[repair_class]
    return a*10**(-b*life)

def solve_seal(case, material, fc, ft2):
    D,t=case['od_mm'],case['wall_mm']
    E=math.sqrt(material['ec_mpa']*material['ea_mpa']);nu=material['nu'];G=material['g_mpa'];gamma=material['gamma_n_mm']
    factor=fc*ft2*leak_factor(case['repair_class'],case['design_life_years']);p=case['pressure_bar']/10
    if any(not math.isfinite(x) or x<=0 for x in (D,t,E,G,gamma,factor,p)):
        raise ValueError('Sealing requires finite positive geometry, pressure and material factors.')
    shape=case['seal_shape'];k=(1-nu*nu)/E
    def invert(a,b,c,eq):
        asym=factor*math.sqrt(gamma/c) if c else math.inf
        if p>=asym: return None,asym
        target=gamma*(factor/p)**2
        def den(x): return a/x**3+b/x+c
        hi=1.
        while den(hi)>target:
            hi*=2
            if hi>1e9: raise ValueError('No practical finite sealing solution.')
        lo=0.
        for _ in range(100):
            mid=(lo+hi)/2
            if den(mid)>target:lo=mid
            else:hi=mid
        return hi,asym
    if shape=='Circular':
        d=math.ceil(max(15.,case['effective_diameter_mm'])/5)*5
        if not math.isfinite(d) or d<15 or D<=60.3 or d>math.sqrt(6*D*t):
            raise ValueError('Circular effective-opening geometry is outside ISO 9.8.3 limits.')
        # Optional rectangle dimensions must actually fit within the assessor's circle.
        a=case.get('effective_axial_mm');b=case.get('effective_circ_mm')
        if a is not None or b is not None:
            if a is None or b is None or min(a,b)<=0 or max(a,b)/min(a,b)>=5 or d+1e-9<math.hypot(a,b):
                raise ValueError('Circular geometry must enclose the full footprint with aspect ratio below 5.')
        seal,asym=invert(k*3*d**4/512,3*d*d/(64*G),k*d/math.pi,21);eq=21
    elif shape=='Circumferential slot':
        w=math.ceil(max(15.,case['effective_axial_mm'])/5)*5
        if w<15:raise ValueError('Effective slot width must include the 15 mm minimum footprint.')
        x,asym=invert(k*w**4/24,3*w*w/(16*G)*(4/5+nu/2)/(1+nu),k*math.pi*w/4,22)
        y=(p*D/factor)**2/(8*E*gamma)
        # Both formulae define pressure capacities. The minimum pressure capacity
        # governs, hence the MAXIMUM of their inverted required thicknesses.
        if x is None:raise ValueError('No finite circumferential-slot sealing solution under equation (22).')
        seal,eq=(x,22) if x>=y else (y,23)
    elif shape=='Axial slot':
        w=math.ceil(max(15.,case['effective_circ_mm'])/5)*5
        if w<15:raise ValueError('Effective slot width must include the 15 mm minimum footprint.')
        if w>=D/2:
            seal=(p*D/factor)**2/(8*E*gamma);eq=23;asym=math.inf
        else:
            seal,asym=invert(k*(w**4/24+w**6/(180*D*D)*(E/(4*G)+2)),0,k*math.pi*w/4,24);eq=24
    else:raise ValueError('Unknown effective opening shape.')
    if seal is None or not math.isfinite(seal):raise ValueError('No finite sealing solution: pressure reaches the equation asymptote.')
    return dict(seal_mm=seal,equation=eq,asymptote_mpa=asym if math.isfinite(asym) else None,f_leak=leak_factor(case['repair_class'],case['design_life_years']),effective_size_mm=d if shape=='Circular' else w)
