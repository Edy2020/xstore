from django.db import models


class Proveedores(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    ruc = models.CharField(max_length=255, blank=True, null=True)
    contacto = models.CharField(max_length=255, blank=True, null=True)
    telefono = models.CharField(max_length=255, blank=True, null=True)
    email = models.CharField(max_length=255, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    estado = models.CharField(max_length=8)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'proveedores'

    def __str__(self):
        return self.nombre


class Productos(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)
    imagen = models.CharField(max_length=255, blank=True, null=True)
    categoria = models.CharField(max_length=255, blank=True, null=True)
    precio = models.BigIntegerField()
    stock = models.IntegerField()
    estado = models.CharField(max_length=8)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    proveedor = models.ForeignKey(
        Proveedores, models.DO_NOTHING, blank=True, null=True
    )

    class Meta:
        managed = False
        db_table = 'productos'

    def __str__(self):
        return self.nombre

    @property
    def precio_formateado(self):
        return f"${self.precio:,.0f}".replace(",", ".")

    @property
    def tiene_stock(self):
        return self.stock > 0

    @property
    def stock_bajo(self):
        return 0 < self.stock <= 5

    @property
    def imagen_url(self):
        if self.imagen:
            return f'/media/{self.imagen}'
        return None

    @property
    def tiene_imagen(self):
        return bool(self.imagen)


class Ventas(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        'Users', models.DO_NOTHING, blank=True, null=True
    )
    subtotal = models.BigIntegerField(default=0)
    descuento_total = models.BigIntegerField(default=0)
    total = models.BigIntegerField(default=0)
    estado = models.CharField(max_length=10, default='completada')
    metodo_pago = models.CharField(max_length=255, default='efectivo')
    notas = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'ventas'

    def __str__(self):
        return f"Venta #{self.id}"


class DetalleVentas(models.Model):
    id = models.BigAutoField(primary_key=True)
    venta = models.ForeignKey(Ventas, models.CASCADE)
    producto = models.ForeignKey(
        Productos, models.DO_NOTHING, blank=True, null=True
    )
    producto_nombre = models.CharField(max_length=255)
    cantidad = models.IntegerField()
    precio_unitario = models.BigIntegerField()
    descuento_porcentaje = models.IntegerField(default=0)
    subtotal = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'detalle_ventas'


class LogActividades(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        'Users', models.DO_NOTHING, blank=True, null=True
    )
    accion = models.CharField(max_length=255)
    modulo = models.CharField(max_length=255)
    detalle = models.TextField()
    ip_address = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'log_actividades'


class Users(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.CharField(unique=True, max_length=255)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    password = models.CharField(max_length=255)
    remember_token = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    role = models.ForeignKey('Roles', models.DO_NOTHING, blank=True, null=True)
    estado = models.CharField(max_length=8)
    last_login_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'users'

    def __str__(self):
        return self.name


class Roles(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(unique=True, max_length=255)
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    permisos = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'roles'
