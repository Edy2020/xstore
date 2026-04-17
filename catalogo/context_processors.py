from .models import Productos
from django.db.models import Count

def global_categories(request):
    """
    Retorna la lista de categorías únicas y el conteo de productos activos
    para ser usadas en el sidebar global.
    """
    categorias_qs = (
        Productos.objects.filter(estado='activo')
        .values('categoria')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    
    categorias = []
    for cat in categorias_qs:
        if cat['categoria']:
            categorias.append({
                'nombre': cat['categoria'],
                'total': cat['total'],
            })
            
    return {
        'global_categorias': categorias
    }
