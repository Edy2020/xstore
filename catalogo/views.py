from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count, F, Case, When, ExpressionWrapper, FloatField
from django.db import transaction, connection
from django.utils import timezone
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
import bcrypt
from .models import Productos, Ventas, DetalleVentas, LogActividades, Users, Roles, Perfiles


def _format_price(value):
    return f"${value:,.0f}".replace(",", ".")


def buscar_live(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'productos': []})

    productos = Productos.objects.filter(
        Q(nombre__icontains=query) | Q(descripcion__icontains=query),
        estado='activo'
    ).order_by('-stock', 'nombre')[:6]

    results = []
    for p in productos:
        results.append({
            'id': p.id,
            'nombre': p.nombre,
            'precio': p.precio_formateado,
            'imagen': p.imagen_url if p.tiene_imagen else None,
            'url': f'/producto/{p.id}/'  # URL directa para evitar reverse innecesario en loop
        })

    return JsonResponse({'productos': results})


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
    query = request.GET.get('q', '')
    categoria_actual = request.GET.get('categoria', '')
    orden = request.GET.get('orden', '')  # Nuevo parámetro para ordenamiento
    
    categorias = Productos.objects.filter(estado='activo').values_list('categoria', flat=True).distinct()
    categorias = [c for c in categorias if c]

    # Consulta base con anotación para calcular el precio REAL (con descuento)
    # Mapping precio_oferta (que es el % de descuento en DB columna 'descuento')
    productos = Productos.objects.filter(estado='activo').annotate(
        precio_final=Case(
            When(precio_oferta__gt=0, precio_oferta__lt=100,
                 then=ExpressionWrapper(
                     F('precio') * (1.0 - (F('precio_oferta') / 100.0)),
                     output_field=FloatField()
                 )),
            default=ExpressionWrapper(F('precio'), output_field=FloatField()),
            output_field=FloatField()
        )
    )

    if query:
        productos = productos.filter(nombre__icontains=query)
    
    if categoria_actual:
        productos = productos.filter(categoria=categoria_actual)

    # Aplicar ordenamiento
    if orden == 'precio_asc':
        productos = productos.order_by('precio_final')
    elif orden == 'precio_desc':
        productos = productos.order_by('-precio_final')
    else:
        # Recomendados / Por defecto
        productos = productos.order_by('-id')

    paginator = Paginator(productos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'catalogo/catalogo.html', {
        'page_obj': page_obj,
        'query': query,
        'categoria_actual': categoria_actual,
        'categorias': categorias,
        'orden_actual': orden,
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


def sobre_nosotros(request):
    return render(request, 'catalogo/sobre_nosotros.html')


def contactanos(request):
    return render(request, 'catalogo/contactanos.html')


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
        # Actualizamos el precio por si cambió (oferta activada/desactivada)
        carrito[pid]['precio'] = producto.precio_actual
    else:
        carrito[pid] = {
            'nombre': producto.nombre,
            'precio': producto.precio_actual,
            'cantidad': min(cantidad, producto.stock),
            'categoria': producto.categoria or '',
            'imagen': producto.imagen,
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

    # Para asegurar que se muestren imágenes y precios originales incluso si no estaban en sesión
    pids = [int(pid) for pid in carrito.keys() if pid.isdigit()]
    productos_db = {str(p.id): p for p in Productos.objects.filter(id__in=pids)}

    for pid, data in carrito.items():
        subtotal = data['precio'] * data['cantidad']
        total += subtotal
        
        prod = productos_db.get(pid)
        imagen = prod.imagen if prod else data.get('imagen')
        
        # Datos de ahorro
        precio_original = prod.precio if prod else data['precio']
        tiene_ahorro = precio_original > data['precio']
        
        items.append({
            'id': pid,
            'nombre': data['nombre'],
            'precio': data['precio'],
            'precio_formateado': _format_price(data['precio']),
            'precio_original_formateado': _format_price(precio_original),
            'tiene_ahorro': tiene_ahorro,
            'ahorro_formateado': _format_price((precio_original - data['precio']) * data['cantidad']),
            'cantidad': data['cantidad'],
            'subtotal': subtotal,
            'subtotal_formateado': _format_price(subtotal),
            'imagen': imagen,
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
    
    # Para asegurar que se muestren imágenes incluso si no estaban en sesión
    pids = [int(pid) for pid in carrito.keys() if pid.isdigit()]
    productos_db = {str(p.id): p.imagen for p in Productos.objects.filter(id__in=pids)}

    for pid, data in carrito.items():
        subtotal = data['precio'] * data['cantidad']
        total += subtotal
        
        imagen = productos_db.get(pid) or data.get('imagen')
        
        items.append({
            'id': pid,
            'nombre': data['nombre'],
            'precio': data['precio'],
            'precio_formateado': _format_price(data['precio']),
            'cantidad': data['cantidad'],
            'subtotal': subtotal,
            'subtotal_formateado': _format_price(subtotal),
            'imagen': imagen,
        })

    return render(request, 'catalogo/checkout.html', {
        'items': items,
        'total': total,
        'total_formateado': _format_price(total),
        'perfil': getattr(request.user, 'perfil', None) if request.user.is_authenticated else None,
    })


# ==================== AUTENTICACIÓN ====================

def login_usuario(request):
    if request.user.is_authenticated:
        return redirect('catalogo:index')
        
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenido de nuevo, {user.name}")
            next_url = request.GET.get('next', 'catalogo:index')
            return redirect(next_url)
        else:
            messages.error(request, "Correo o contraseña incorrectos.")
            
    return render(request, 'catalogo/login.html')


def registro_usuario(request):
    if request.user.is_authenticated:
        return redirect('catalogo:index')
        
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        if password != password_confirm:
            messages.error(request, "Las contraseñas no coinciden.")
        elif Users.objects.filter(email=email).exists():
            messages.error(request, "Este correo ya está registrado.")
        else:
            try:
                # Aseguramos que existe el rol Cliente
                role_cliente, _ = Roles.objects.get_or_create(
                    nombre='Cliente',
                    defaults={'descripcion': 'Cliente de la tienda online'}
                )
                
                # Hasheamos la clave al estilo Bcrypt
                hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
                
                # Creamos el usuario
                user = Users.objects.create(
                    name=nombre,
                    email=email,
                    password=hashed,
                    role=role_cliente,
                    estado='activo',
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )
                
                # Creamos el perfil vacío
                Perfiles.objects.create(user=user)
                
                # Autenticamos e iniciamos sesión
                user_auth = authenticate(request, username=email, password=password)
                if user_auth:
                    login(request, user_auth)
                    messages.success(request, "¡Cuenta creada exitosamente!")
                    return redirect('catalogo:index')
                    
            except Exception as e:
                messages.error(request, f"Error al crear la cuenta: {str(e)}")
                
    return render(request, 'catalogo/registro.html')


def logout_usuario(request):
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('catalogo:index')


def perfil_usuario(request):
    if not request.user.is_authenticated:
        return redirect('catalogo:login')
        
    perfil, created = Perfiles.objects.get_or_create(user=request.user)
    
    # Obtenemos el historial de compras
    ventas_qs = Ventas.objects.filter(user=request.user).order_by('-id')
    
    # Formateamos los precios para el template
    ventas = []
    for v in ventas_qs:
        ventas.append({
            'id': v.id,
            'total_formateado': _format_price(v.total),
            'estado': v.estado,
            'metodo_pago': v.metodo_pago,
            'created_at': v.created_at,
        })
    
    if request.method == 'POST':
        request.user.name = request.POST.get('nombre')
        request.user.save()
        
        perfil.direccion = request.POST.get('direccion')
        perfil.telefono = request.POST.get('telefono')
        perfil.ciudad = request.POST.get('ciudad')
        perfil.save()
        
        messages.success(request, "Perfil actualizado correctamente.")
        return redirect('catalogo:perfil')
        
    return render(request, 'catalogo/perfil.html', {
        'perfil': perfil,
        'ventas': ventas
    })


def eliminar_cuenta(request):
    if request.method != 'POST' or not request.user.is_authenticated:
        return redirect('catalogo:perfil')
        
    try:
        user = Users.objects.get(pk=request.user.id)
        user.estado = 'inactivo'
        user.save()
        
        logout(request)
        messages.info(request, "Tu cuenta ha sido desactivada correctamente. Lamentamos verte partir.")
        return redirect('catalogo:index')
    except Exception as e:
        messages.error(request, f"Error al eliminar la cuenta: {str(e)}")
        return redirect('catalogo:perfil')


def detalle_compra_api(request, venta_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autorizado'}, status=401)
        
    try:
        # Buscamos la venta y validamos que pertenezca al usuario
        venta = Ventas.objects.get(id=venta_id, user=request.user)
        
        # Obtenemos los productos del detalle
        items_qs = DetalleVentas.objects.filter(venta=venta)
        
        items = []
        for item in items_qs:
            items.append({
                'nombre': item.producto_nombre,
                'cantidad': item.cantidad,
                'precio_unitario': _format_price(item.precio_unitario),
                'subtotal': _format_price(item.subtotal)
            })
            
        # Intentamos parsear la información de envío guardada en notas
        info_cliente = {
            'nombre': 'No especificado',
            'envio': 'No especificado',
            'telefono': 'No especificado',
            'notas_cliente': ''
        }
        
        if venta.notas and '[XStore Online]' in venta.notas:
            try:
                # Formato esperado: [XStore Online] Cliente: {nombre}. Envío: {direccion}, {ciudad} ({telefono}). Notas: {notas}
                notas_txt = venta.notas.replace('[XStore Online] ', '')
                if 'Cliente: ' in notas_txt and ' Envío: ' in notas_txt:
                    info_cliente['nombre'] = notas_txt.split('Cliente: ')[1].split('. Envío: ')[0]
                    res_envio = notas_txt.split(' Envío: ')[1]
                    if ' (' in res_envio and '). Notas: ' in res_envio:
                        info_cliente['envio'] = res_envio.split(' (')[0]
                        info_cliente['telefono'] = res_envio.split(' (')[1].split('). Notas: ')[0]
                        info_cliente['notas_cliente'] = res_envio.split('). Notas: ')[1]
                    elif ').' in res_envio:
                         info_cliente['envio'] = res_envio.split(' (')[0]
                         info_cliente['telefono'] = res_envio.split(' (')[1].split(').')[0]
            except:
                pass

        return JsonResponse({
            'ok': True,
            'id': venta.id,
            'fecha': venta.created_at.strftime('%d/%m/%Y %H:%M'),
            'metodo_pago': venta.metodo_pago,
            'info_cliente': info_cliente,
            'total': _format_price(venta.total),
            'items': items
        })
    except Ventas.DoesNotExist:
        return JsonResponse({'error': 'Compra no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
    direccion = request.POST.get('direccion', '')
    ciudad = request.POST.get('ciudad', '')
    telefono = request.POST.get('telefono', '')
    notas_cliente = request.POST.get('notas', '')

    # Combinamos la información de envío en las notas para el admin
    info_envio = f"Envío: {direccion}, {ciudad} ({telefono})"
    notas_final = f"[XStore Online] Cliente: {nombre_cliente}. {info_envio}. Notas: {notas_cliente}".strip()

    try:
        with transaction.atomic():
            subtotal_venta = 0
            total_venta = 0

            # Si el usuario está logueado, usamos su ID
            user_id = request.user.id if request.user.is_authenticated else None

            venta = Ventas(
                user_id=user_id,
                subtotal=0,
                descuento_total=0,
                total=0,
                estado='completada',
                metodo_pago=metodo_pago,
                notas=notas_final,
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
                precio_unitario = producto.precio_actual
                subtotal_item = precio_unitario * cantidad

                DetalleVentas(
                    venta=venta,
                    producto=producto,
                    producto_nombre=producto.nombre,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    descuento_porcentaje=producto.ahorro_porcentaje if producto.en_oferta else 0,
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
                user_id=user_id,
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
