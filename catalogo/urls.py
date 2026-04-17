from django.urls import path
from . import views

app_name = 'catalogo'

urlpatterns = [
    path('', views.index, name='index'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('producto/<int:producto_id>/', views.detalle, name='detalle'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/', views.agregar_carrito, name='agregar_carrito'),
    path('carrito/actualizar/', views.actualizar_carrito, name='actualizar_carrito'),
    path('carrito/eliminar/', views.eliminar_carrito, name='eliminar_carrito'),
    path('carrito/vaciar/', views.vaciar_carrito, name='vaciar_carrito'),
    path('carrito/count/', views.carrito_count, name='carrito_count'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/confirmar/', views.confirmar_compra, name='confirmar_compra'),
]
