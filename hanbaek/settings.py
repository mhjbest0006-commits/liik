"""
Django settings for hanbaek project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------ 보안 설정 ------------------
# 운영 배포 시에는 반드시 환경변수로 별도 관리하세요.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-CHANGE-THIS-KEY-BEFORE-DEPLOYING'
)

# 로컬 개발 중에는 True, 외부에 공개(운영)할 때는 반드시 False로 바꾸세요.
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# 로컬 테스트 + ngrok 등 터널링 서비스를 함께 쓰려면 "*" 유지,
# 실제 운영 배포 시에는 실제 도메인만 넣어서 좁히는 것을 권장합니다.
ALLOWED_HOSTS = ['*']

# ngrok 등 https 터널을 쓸 때 CSRF 체크가 막히지 않도록 허용 (필요 시 도메인 추가)
CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
]

# ------------------ 애플리케이션 ------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework.authtoken',
    'django_extensions',  # runserver_plus 및 HTTPS 개발 서버용

    'web',
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

ROOT_URLCONF = 'hanbaek.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'web.context_processors.role_context',  
            ],
        },
    },
]

WSGI_APPLICATION = 'hanbaek.wsgi.application'

# ------------------ 데이터베이스 ------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ------------------ 비밀번호 검증 ------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ------------------ DRF 설정 ------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
}

# ------------------ 국제화 ------------------
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True

# ------------------ 정적 파일 ------------------
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 로그인 관련 리디렉션
LOGIN_URL = '/login/'

MEAL_SERVICE_TIME_PER_PERSON = float(os.environ.get('MEAL_SERVICE_TIME_PER_PERSON', '3'))

# ------------------ [관리자 계정 / 학생 계정 분리] ------------------
ADMIN_SIGNUP_CODE = os.environ.get('ADMIN_SIGNUP_CODE', 'ADMIN')

