from add_on_analysis.models import AddOn, Fin_Data, Nace
from add_on_analysis.api import get_company_data
import pandas as pd


def calc_netto_schuldpositie(schuld_meer_1j, schuld_hoogst_1j, liq_middelen):
    netto_schuld = liq_middelen - schuld_meer_1j - schuld_hoogst_1j
    return netto_schuld

def calc_capex_noden(mva_1, mva_2, afschrijvingen):
    capex = mva_2 - mva_1 + afschrijvingen
    return capex

def calc_ebitda(winstVoorBel, afschrijvingen, rente):
    ebitda = winstVoorBel + afschrijvingen + rente
    return ebitda

def afkorting_soort(soort):
    if soort == 'Besloten Vennootschap':
        afkorting = 'BV'
    elif soort == 'Naamloze Vennootschap':
        afkorting = 'NV'
    else:
        afkorting = soort
    return afkorting

def calc_FTE(bezoldigingen, geschat_jaarloon):
    FTE = bezoldigingen / 65000
    return FTE
    
def create_addon(vat, vertex):
    if AddOn.objects.filter(comp_num=vat, vertex=vertex).exists():
        return
    
    compDet = get_company_data(vat)
    newComp = AddOn(
        name=compDet['name'],
        comp_num=vat,
        street=compDet['street'],
        number=compDet['number'],
        zipcode=compDet['zipcode'],
        city=compDet['city'],
    )
    newComp.save()
    for activity in compDet['activities']:
        nace, created = Nace.objects.get_or_create(
            code=activity['nacecode'],
            description=activity['description'],
        )
        newComp.activities.add(nace)
    for fin_year in compDet['fin']:
        fin_data = Fin_Data(
            year=fin_year['enddate'],
            bezoldigingen=fin_year['62'],
            mva=fin_year['22/27'],
            afschrijvingen=fin_year['630'],
            liq_middelen=fin_year['54/58'],
            schuld_meer_1j=fin_year['17'],
            schuld_hoogst_1j=fin_year['42/48'],
            winst_verlies_v_belasting = fin_year['9903'],
            winst_verlies=fin_year['9904'],
            eigen_vermogen=fin_year['10/15'],
            fin_kosten=fin_year['65/66B'],
            add_on = newComp
        )
        
        fin_data.save()
    newComp.vertex = vertex
    newComp.ebitda = newComp.calc_ebitda()
    newComp.bezoldigingen = newComp.calc_bezoldigingen()
    newComp.mva = newComp.calc_mva()
    newComp.capex_noden_avg_3j = newComp.calc_capex_noden_avg_3j()
    newComp.netto_schuldpositie = newComp.calc_netto_schuldpositie()
    newComp.winst_verlies = newComp.calc_winst_verlies()
    newComp.eigen_vermogen = newComp.calc_eigen_vermogen()
    newComp.save()
    return newComp

def uploadHandler(file, vertex):
    df = pd.read_excel(file, names=['BTW'], dtype=str)
    for index, row in df.iterrows():
        newComp = create_addon(row['BTW'])
        newComp.vertex = vertex
        newComp.save()
