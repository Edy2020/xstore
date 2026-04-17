from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.db import transaction
from django.utils import timezone
from .models import Productos, Ventas, DetalleVentas, LogActividades


def _format_price(value):
    return f"${value:,.0f}".replace(",", ".")


def index(request):
    productos_activos = Productos.objects.filter(estado='activo')

    categorias_qs = (
        productos_activos
        .values('categoria')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    categorias = []
    for cat in categorias_qs:
        nombre = cat['categoria'] or 'Otros'
        categorias.append({
            'categoria': nombre,
            'total': cat['total'],
        })

    productos_destacados = productos_activos.filter(stock__gt=0).order_by('-id')[:8]

    return render(request, 'catalogo/index.html', {
        'categorias': categorias,
        'productos_destacados': productos_destacados,
    })


def catalogo(request):
    productos = Productos.objects.filter(estado='activo')

    query = request.GET.get('q', '').strip()
    categoria_actual = request.GET.get('categoria', '').strip()

    if query:
        productos = productos.filter(
            Q(nombre__icontains=query) | Q(descripcion__icontains=query)
        )

    if categoria_actual:
        productos = productos.filter(categoria=categoria_actual)

    productos = productos.order_by('-stock', '-id')

    categorias = (
        Productos.objects.filter(estado='activo')
        .values_list('categoria', flat=True)
        .distinct()
        .order_by('categoria')
    )
    categorias = [c for c in categorias if c]

    paginator = Paginator(productos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'catalogo/catalogo.html', {
        'page_obj': page_obj,
        'query': query,
        'categoria_actual': categoria_actual,
        'categorias': categorias,
        'total_productos': Productos.objects.filter(estado='activo').count(),
    })


def detalle(request, producto_id):
    producto = get_object_or_404(Productos, id=producto_id, estado='activo')

    relacionados = (
        Productos.objects.filter(categoria=producto.categoria, estado='activo')
        .exclude(id=producto.id)
        .order_by('?')[:4]
    )

    return render(request, 'catalogo/detalle.html', {
        'producto': producto,
        'relacionados': relacionados,
    })


# ==================== CART (Session) ====================

def _get_cart(request):
    return request.session.get('carrito', {})


def _save_cart(request, carrito):
    request.session['carrito'] = carrito
    request.session.modified = True


def _cart_count(request):
    carrito = _get_cart(request)
    return sum(item['cantidad'] for item in carrito.values())


def _cart_total(request):
    carrito = _get_cart(request)
    return sum(item['precio'] * item['cantidad'] for item in carrito.values())


def agregar_carrito(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    producto_id = request.POST.get('producto_id')
    cantidad = int(request.POST.get('cantidad', 1))

    try:
        producto = Productos.objects.get(id=producto_id, estado='activo')
    except Productos.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Producto no encontrado'})

    if not producto.tiene_stock:
        return JsonResponse({'ok': False, 'error': 'Producto sin stock'})

    carrito = _get_cart(request)
    pid = str(producto_id)

    if pid in carrito:
        nueva_qty = carrito[pid]['cantidad'] + cantidad
        if nueva_qty > producto.stock:
            nueva_qty = producto.stock
        carrito[pid]['cantidad'] = nueva_qty
    else:
        carrito[pid] = {
            'nombre': producto.nombre,
            'precio': producto.precio,
            'cantidad': min(cantidad, producto.stock),
            'categoria': producto.categoria or '',
        }

    _save_cart(request, carrito)

    return JsonResponse({
        'ok': True,
        'nombre': producto.nombre,
        'cart_count': _cart_count(request),
    })


def ver_carrito(request):
    carrito = _get_cart(request)
    items = []
    total = 0

    for pid, data in carrito.items():
        subtotal = data['precio'] * data['cantidad']
        total += subtotal
        items.append({
            'id': pid,
            'nombre': data['nombre'],
            'precio': data['precio'],
            'precio_formateado': _format_price(data['precio']),
            'cantidad': data['cantidad'],
            'subtotal': subtotal,
            'subtotal_formateado': _format_price(subtotal),
        })

    return render(request, 'catalogo/carrito.html', {
        'items': items,
        'total': total,
        'total_formateado': _format_price(total),
    })


def actualizar_carrito(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    producto_id = str(request.POST.get('producto_id'))
    cantidad = int(request.POST.get('cantidad', 1))

    carrito = _get_cart(request)

    if producto_id in carrito:
        if cantidad < 1:
            cantidad = 1
        carrito[producto_id]['cantidad'] = cantidad
        _save_cart(request, carrito)

        item_subtotal = carrito[producto_id]['precio'] * cantidad

        return JsonResponse({
            'ok': True,
            'cart_count': _cart_count(request),
            'cart_total': _format_price(_cart_total(request)),
            'item_subtotal': _format_price(item_subtotal),
        })

    return JsonResponse({'ok': False, 'error': 'Producto no está en el carrito'})


def eliminar_carrito(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    producto_id = str(request.POST.get('producto_id'))
    carrito = _get_cart(request)

    if producto_id in carrito:
        del carrito[producto_id]
        _save_cart(request, carrito)

    return JsonResponse({
        'ok': True,
        'cart_count': _cart_count(request),
        'cart_total': _format_price(_cart_total(request)),
    })


def vaciar_carrito(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    request.session['carrito'] = {}
    request.session.modified = True

    return JsonResponse({'ok': True, 'cart_count': 0})


def carrito_count(request):
    return JsonResponse({'count': _cart_count(request)})


# ==================== CHECKOUT ====================

def checkout(request):
    carrito = _get_cart(request)

    if not carrito:
        return redirect('catalogo:ver_carrito')

    items = []
    total = 0
    for pid, data in carrito.items():
        subtotal = data['precio'] * data['cantidad']
        total += subtotal
        items.append({
            'id': pid,
            'nombre': data['nombre'],
            'precio': data['precio'],
            'precio_formateado': _format_price(data['precio']),
            'cantidad': data['cantidad'],
            'subtotal': subtotal,
            'subtotal_formateado': _format_price(subtotal),
        })

    return render(request, 'catalogo/checkout.html', {
        'items': items,
        'total': total,
        'total_formateado': _format_price(total),
    })


def confirmar_compra(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    carrito = _get_cart(request)

    if not carrito:
        return render(request, 'catalogo/compra_resultado.html', {
            'exito': False,
            'error': 'El carrito está vacío.',
        })

    metodo_pago = request.POST.get('metodo_pago', 'Efectivo')
    nombre_cliente = request.POST.get('nombre_cliente', 'Cliente XStore')
    notas = request.POST.get('notas', '')

    try:
        with transaction.atomic():
            subtotal_venta = 0
            total_venta = 0

            venta = Ventas(
                user_id=None,
                subtotal=0,
                descuento_total=0,
                total=0,
                estado='completada',
                metodo_pago=metodo_pago,
                notas=f"[XStore Online] Cliente: {nombre_cliente}. {notas}".strip(),
            )
            venta.save()

            for pid, data in carrito.items():
                producto = Productos.objects.select_for_update().get(id=int(pid))

                if producto.stock < data['cantidad']:
                    raise Exception(
                        f"Stock insuficiente para '{producto.nombre}'. "
                        f"Disponible: {producto.stock}, solicitado: {data['cantidad']}"
                    )

                cantidad = data['cantidad']
                precio_unitario = producto.precio
                subtotal_item = precio_unitario * cantidad

                DetalleVentas(
                    venta=venta,
                    producto=producto,
                    producto_nombre=producto.nombre,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    descuento_porcentaje=0,
                    subtotal=subtotal_item,
                ).save()

                producto.stock -= cantidad
                producto.save()

                subtotal_venta += subtotal_item
                total_venta += subtotal_item

            venta.subtotal = subtotal_venta
            venta.descuento_total = 0
            venta.total = total_venta
            venta.save()

            client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()

            LogActividades(
                user_id=None,
                accion='Creación',
                modulo='Ventas',
                detalle=(
                    f"[XStore Online] Venta #{str(venta.id).zfill(5)} por "
                    f"{_format_price(total_venta)} — Cliente: {nombre_cliente} — "
                    f"Método: {metodo_pago}"
                ),
                ip_address=client_ip,
            ).save()

        request.session['carrito'] = {}
        request.session.modified = True

        return render(request, 'catalogo/compra_resultado.html', {
            'exito': True,
            'venta_id': venta.id,
            'venta_total': _format_price(total_venta),
            'metodo_pago': metodo_pago,
            'nombre_cliente': nombre_cliente,
        })

    except Exception as e:
        return render(request, 'catalogo/compra_resultado.html', {
            'exito': False,
            'error': str(e),
        })
