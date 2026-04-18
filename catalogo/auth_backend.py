import bcrypt
from .models import Users

class XStockBackend:
    """
    Backend personalizado para autenticar usuarios contra la tabla 'users' de XStock
    utilizando Bcrypt (compatible con Laravel $2y$).
    """
    def authenticate(self, request, username=None, password=None):
        if not username or not password:
            return None
            
        try:
            user = Users.objects.get(email=username, estado='activo')
            
            # Laravel usa $2y$, Python bcrypt usa $2b$. Son compatibles si reemplazamos el prefijo.
            laravel_hash = user.password.replace('$2y$', '$2b$')
            
            if bcrypt.checkpw(password.encode('utf-8'), laravel_hash.encode('utf-8')):
                return user
        except (Users.DoesNotExist, ValueError):
            return None

    def get_user(self, user_id):
        try:
            return Users.objects.get(pk=user_id)
        except Users.DoesNotExist:
            return None
