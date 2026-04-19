from .models import Productos, Favoritos
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
            # Obtener el último producto con imagen para esta categoría
            p_img = Productos.objects.filter(categoria=cat['categoria'], estado='activo').exclude(imagen='').order_by('-id').first()
            img_url = p_img.imagen_url if p_img else None
            
            categorias.append({
                'nombre': cat['categoria'],
                'total': cat['total'],
                'imagen': img_url
            })
            
    return {
        'global_categorias': categorias
    }

def user_favoritos(request):
    """
    Retorna una lista de IDs de productos que el usuario tiene en favoritos
    para marcarlos visualmente en las tarjetas.
    """
    if request.user.is_authenticated:
        favoritos_ids = Favoritos.objects.filter(user=request.user).values_list('producto_id', flat=True)
        return {'favoritos_ids': list(favoritos_ids)}
    return {'favoritos_ids': []}
