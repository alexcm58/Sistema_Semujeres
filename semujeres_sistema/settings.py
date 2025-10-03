from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Archivos subidos
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Archivos estáticos
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'core/static']

# Seguridad
SECRET_KEY = 'django-insecure-1^%w#+h#%-nwhewo64ivy$+#-+aerr%j1)yco4wzac2v60@3ie'
DEBUG = True
ALLOWED_HOSTS = []

# Aplicaciones
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'semujeres_sistema.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'semujeres_sistema.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'semujer_db',          # Nombre de tu base de datos en MariaDB
        'USER': 'semujer_user',        # Usuario que creaste
        'PASSWORD': 'Semujer123!',     # Contraseña del usuario
        'HOST': 'localhost',           # Si MariaDB está en el mismo servidor
        'PORT': '3306',                # Puerto por defecto de MySQL/MariaDB
        'OPTIONS': {
            'charset': 'utf8mb4',      # Soporte de acentos y emojis
        }
    }
}


# Contraseñas
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internacionalización
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True


# Usuario personalizado
AUTH_USER_MODEL = 'core.Usuario'

# Login
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Configuración de correo (SMTP con Gmail)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "asemujeres@gmail.com"
EMAIL_HOST_PASSWORD = "fvjp lwjy iyby jnrn"  # tu contraseña de aplicación   # <-- pon tu contraseña o app password aquí
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

