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
    categoria = models.CharField(max_length=255, blank=True, null=True)
    precio = models.BigIntegerField()
    stock = models.IntegerField()
    estado = models.CharField(max_length=8)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    proveedor = models.ForeignKey(
        Proveedores, models.DO_NOTHING, blank=True, null=True
    )

    CATEGORIA_ICONOS = {
        'Manga': '📚',
        'Figura': '🎭',
        'Figuras': '🎭',
        'Ropa': '👕',
        'Accesorios': '🎒',
        'Decoración': '🖼️',
        'Papelería': '✏️',
    }

    CATEGORIA_COLORES = {
        'Manga': '#e74c8a',
        'Figura': '#8b5cf6',
        'Figuras': '#8b5cf6',
        'Ropa': '#3b82f6',
        'Accesorios': '#f59e0b',
        'Decoración': '#10b981',
        'Papelería': '#ef4444',
    }

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
    def categoria_icono(self):
        return self.CATEGORIA_ICONOS.get(self.categoria, '📦')

    @property
    def categoria_color(self):
        return self.CATEGORIA_COLORES.get(self.categoria, '#6366f1')
