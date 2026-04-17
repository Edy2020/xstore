from django.shortcuts import render
from .models import Productos

def index(request):
    return render(request, 'index.html')


def lista(request):
    productos = Productos.objects.all()
    return render(request, 'catalogo/lista.html', {'productos': productos})
