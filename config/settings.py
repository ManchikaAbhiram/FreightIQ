from pathlib import Path
import os
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-change-this-freightiq-key')
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost,[::1]').split(',')
INSTALLED_APPS = [
 'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions',
 'django.contrib.messages','django.contrib.staticfiles','audit',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'audit.middleware.ApprovalMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'], 'APP_DIRS':True,
 'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'}, {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-in'
TIME_ZONE='Asia/Kolkata'
USE_I18N=True
USE_TZ=True
STATIC_URL='static/'
MEDIA_URL='media/'
MEDIA_ROOT=BASE_DIR/'media'
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
LOGIN_URL='login'
LOGIN_REDIRECT_URL='dashboard'
LOGOUT_REDIRECT_URL='login'
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
CSRF_COOKIE_HTTPONLY=True
CSRF_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_SECURE=not DEBUG
CSRF_COOKIE_SECURE=not DEBUG
SECURE_SSL_REDIRECT=not DEBUG
SECURE_REFERRER_POLICY='same-origin'
SECURE_HSTS_SECONDS=31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF=True
X_FRAME_OPTIONS='DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE=20*1024*1024
