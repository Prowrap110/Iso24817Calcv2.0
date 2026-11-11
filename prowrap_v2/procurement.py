"""Legacy 300/500 mm bands and owner-approved consumption estimating rules."""
import math

def bands(length, widths='300 and 500'):
    if not math.isfinite(length) or not 0<length<=1e7:raise ValueError('Repair length is outside supported procurement range.')
    allowed={'300':(300,), '500':(500,), '300 and 500':(300,500)}[widths]
    # Enumerate one width; the other uses the smallest feasible count. 50 mm splice.
    candidates=[]
    max500=math.ceil(max(0,length-50)/450) if 500 in allowed else 0
    for n500 in range(max500+1):
        n300=max(0,math.ceil((length-50-450*n500)/250)) if 300 in allowed else 0
        n=n300+n500
        if n==0:continue
        gross=300*n300+500*n500;coverage=gross-50*(n-1)
        if coverage+1e-9>=length:candidates.append(((gross,n,-n500),dict(count_500=n500,count_300=n300,gross_mm=gross,covered_mm=coverage)))
    return min(candidates,key=lambda x:x[0])[1]

def quantities(case, length, plies, installed_mm):
    """Return job/group totals, already multiplied by quantity exactly once.

    Engineering length, plies and installed thickness supplied here remain per repair.
    The explicit putty_per_repair_kg result records consumption before quantity scaling.
    """
    plan=bands(length,case['cloth_widths']);q=int(case['quantity'])
    # Sum each layer mid-surface perimeter; exact cylindrical ply-volume area.
    area=math.pi*(case['od_mm']+installed_mm)*plan['gross_mm']*plies/1e6
    putty=case.get('putty_kg_per_repair')
    if putty is None:
        if case['mechanism']=='Dent no-crack':
            # One third of L x W x depth, at the existing 2 kg/L density.
            putty=case['defect_length_mm']*case['defect_width_mm']*case['dent_depth_mm']*.000002/3
        else:
            # 2 kg through 200 mm, then +1 kg for each further started 200 mm.
            putty=1+math.ceil((case.get('zone_length_mm') or case['defect_length_mm'])/200)
    return dict(count_500=plan['count_500']*q,count_300=plan['count_300']*q,fabric_area_m2=area*q,laminate_epoxy_kg=2*area*q,putty_per_repair_kg=putty,putty_kg=putty*q,total_epoxy_kg=(2*area+putty)*q,quantity=q)
