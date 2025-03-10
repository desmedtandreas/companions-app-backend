from django.shortcuts import render, redirect, HttpResponse
from add_on_analysis.forms import BTWForm, UploadFileForm
from add_on_analysis.models import AddOn, Vertex
from add_on_analysis.functions import create_addon, uploadHandler
from django.contrib import messages
from add_on_analysis.tables import AddOnTable
from django_tables2 import RequestConfig

import openpyxl

# Create your views here.
def vertex_overview(request):
    vertex_list = Vertex.objects.all()
    context = {"vertex_list": vertex_list}
    return render(request, "add_on_analysis/vertex_overview.html", context)
   
def addon_overview(request, vertex_name):
    btwForm = BTWForm()
    vertex = Vertex.objects.get(name=vertex_name)
    active_table = AddOnTable(AddOn.objects.filter(vertex=vertex, status="active"))
    RequestConfig(request).configure(active_table)
    archivedAddons = AddOn.objects.filter(vertex=vertex, status="inactive")
        
    if request.method == "POST":
        btwForm = BTWForm(request.POST)
        if btwForm.is_valid():
            try:
                newComp = create_addon(btwForm.cleaned_data['BTWnr'], vertex)
            except KeyError as e:
                messages.error(request, f"Error creating add-on: {e}")
            btwForm = BTWForm()
            return redirect("add_on_analysis:addon_overview", vertex_name=vertex.name)
    
    context = {
        'active_table': active_table, 
        'archivedAddons': archivedAddons,
        'btwForm': btwForm, 
        'uploadForm': UploadFileForm(),
        'messages': messages.get_messages(request),
        'vertex': vertex
        }
    
    if request.htmx:
        return render(request, 'add_on_analysis/addon_overview_table.html', context)
    else:
        return render(request, 'add_on_analysis/addon_overview.html', context)

def upload_file(request, vertex_name):
    vertex = Vertex.objects.get(name=vertex_name)
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploadHandler(request.FILES["file"], vertex)
            return redirect("add_on_analysis:addon_overview", vertex_name=vertex.name)
    else:
        form = UploadFileForm()
    return redirect("add_on_analysis:addon_overview", vertex_name=vertex.name)


def delete_addon(request, id):
    addon = AddOn.objects.get(id=id)
    vertex = addon.vertex
    addon.status = "inactive"
    addon.save()
    return redirect("add_on_analysis:addon_overview", vertex_name=vertex.name)

def export_addons(request, vertex_name):
    addons = AddOn.objects.filter(status="active")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = vertex_name
    
    headers = [
        'Naam', 
        'EBITDA', 
        'BEZOLDIGINGEN', 
        'MVA',
        'CAPEX',
        'NETTO SCHULDPOSITIE',
        'WINST/VERLIES',
        'EIGEN VERMOGEN',
        ]
    sheet.append(headers)
    
    addons = AddOn.objects.filter(status="active")
    
    for addon in addons:
        sheet.append([
            addon.name, 
            addon.ebitda, 
            addon.bezoldigingen, 
            addon.mva,
            addon.capex_noden_avg_3j,
            addon.netto_schuldpositie,
            addon.winst_verlies,
            addon.eigen_vermogen,
            ])
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{vertex_name}.xlsx"'

    # Save the workbook to the response
    workbook.save(response)

    return response
    
