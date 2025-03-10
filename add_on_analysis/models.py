from django.db import models

# Create your models here.
class Vertex(models.Model):
    name = models.CharField(max_length=200)
    
    def __str__(self):
        return self.name

class Nace(models.Model):
    code = models.CharField(max_length=10)
    description = models.CharField(max_length=200)
    
    def __str__(self):
        return self.code + " - " + self.description

class AddOn(models.Model):
    name = models.CharField(verbose_name='Naam', max_length=200)
    comp_num = models.CharField(max_length=200, default="")
    status = models.CharField(max_length=200, default="active")
    street = models.CharField(max_length=200, default="")
    number = models.CharField(max_length=10, default="")
    zipcode = models.CharField(max_length=10, default="")
    city = models.CharField(max_length=200, default="")
    
    vertex = models.ForeignKey(Vertex, on_delete=models.CASCADE, null=True)
    activities = models.ManyToManyField(Nace)

    ebitda = models.DecimalField(verbose_name="EBITDA", max_digits=10, decimal_places=2, default=0)
    bezoldigingen = models.DecimalField(verbose_name="BEZ.", max_digits=10, decimal_places=2, default=0)
    mva = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    capex_noden_avg_3j = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    netto_schuldpositie = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    winst_verlies = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    eigen_vermogen = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return self.name
    
    def calc_ebitda(self):
        winstVoorBel = self.fin_data_set.order_by("year").last().winst_verlies_v_belasting
        afschrijvingen = self.fin_data_set.order_by("year").last().afschrijvingen
        rente = self.fin_data_set.order_by("year").last().fin_kosten
        ebitda = winstVoorBel + afschrijvingen + rente
        return ebitda
    
    def calc_bezoldigingen(self):
        return self.fin_data_set.order_by("year").last().bezoldigingen
    
    def calc_mva(self):
        return self.fin_data_set.order_by("year").last().mva
    
    def calc_capex_noden_avg_3j(self):
        capex_list = []
        for i in [0, 1]:
            mva_2 = self.fin_data_set.order_by("-year")[i].mva
            mva_1 = self.fin_data_set.order_by("-year")[(i+1)].mva
            capex = mva_2 - mva_1 + self.fin_data_set.order_by("year")[i].afschrijvingen
            capex_list.append(capex)
        return sum(capex_list) / len(capex_list)

    
    def calc_netto_schuldpositie(self):
        liq_middelen = self.fin_data_set.order_by("year").last().liq_middelen
        schuld_meer_1j = self.fin_data_set.order_by("year").last().schuld_meer_1j
        schuld_hoogst_1j = self.fin_data_set.order_by("year").last().schuld_hoogst_1j
        return (liq_middelen - schuld_meer_1j - schuld_hoogst_1j)

    def calc_winst_verlies(self):
        return self.fin_data_set.order_by("year").last().winst_verlies
    
    def calc_eigen_vermogen(self):
        return self.fin_data_set.order_by("year").last().eigen_vermogen
    
class Fin_Data(models.Model):
    year = models.DateField("Financial year")
    bezoldigingen = models.DecimalField(max_digits=10, decimal_places=2)
    mva = models.DecimalField(max_digits=10, decimal_places=2)
    afschrijvingen = models.DecimalField(max_digits=10, decimal_places=2)
    liq_middelen = models.DecimalField(max_digits=10, decimal_places=2)
    schuld_meer_1j = models.DecimalField(max_digits=10, decimal_places=2)
    schuld_hoogst_1j = models.DecimalField(max_digits=10, decimal_places=2)
    winst_verlies_v_belasting = models.DecimalField(max_digits=10, decimal_places=2)
    winst_verlies = models.DecimalField(max_digits=10, decimal_places=2)
    eigen_vermogen = models.DecimalField(max_digits=10, decimal_places=2)
    fin_kosten = models.DecimalField(max_digits=10, decimal_places=2)
    
    add_on = models.ForeignKey(AddOn, on_delete=models.CASCADE)