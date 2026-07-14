import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-dev-secret")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

SITE_NAME = os.getenv("SITE_NAME", "The Up Media")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "http://127.0.0.1:8000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "social_django",
    "django_ckeditor_5",
    "accounts",
    "news",
    "blog",
    "services",
    "subscriptions",
    "distribution",
    "live_tv",
    "social_downloader",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "theupmedia.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
                "core.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "theupmedia.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": os.getenv("DATABASE_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DATABASE_NAME"),
        "USER": os.getenv("DATABASE_USER"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD"),
        "HOST": os.getenv("DATABASE_HOST"),
        "PORT": os.getenv("DATABASE_PORT"),
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = (
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.facebook.FacebookOAuth2",
    "django.contrib.auth.backends.ModelBackend",
)

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY") or os.getenv("GOOGLE_OAUTH2_KEY", "")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv("SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET") or os.getenv("GOOGLE_OAUTH2_SECRET", "")
SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = os.getenv(
    "SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI",
    f"{SITE_DOMAIN}/auth/complete/google-oauth2/",
)
SOCIAL_AUTH_FACEBOOK_KEY = os.getenv("FACEBOOK_KEY", "")
SOCIAL_AUTH_FACEBOOK_SECRET = os.getenv("FACEBOOK_SECRET", "")
SOCIAL_AUTH_URL_NAMESPACE = "social"
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ["email", "profile"]
SOCIAL_AUTH_LOGIN_REDIRECT_URL = "/accounts/profile/"
SOCIAL_AUTH_LOGIN_ERROR_URL = "/accounts/login/?error=1"
SOCIAL_AUTH_RAISE_EXCEPTIONS = False
SOCIAL_AUTH_PROTECTED_USER_FIELDS = [
    "username",
    "first_name",
    "last_name",
    "email",
    "bio",
    "phone_number",
    "alternate_phone",
    "date_of_birth",
    "gender",
    "role",
    "designation",
    "organization",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "country",
    "postal_code",
    "language",
    "timezone",
    "website",
    "facebook",
    "twitter",
    "instagram",
    "linkedin",
    "youtube",
    "avatar",
    "cover_image",
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:profile"
LOGOUT_REDIRECT_URL = "core:home"

SITE_ID = 1

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = os.getenv("MEDIA_URL", "https://theupmedia.in/media/")
MEDIA_ROOT = BASE_DIR / "media"

CKEDITOR_5_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
CKEDITOR_5_UPLOAD_FILE_TYPES = ["jpeg", "jpg", "png", "gif", "bmp", "webp"]
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": [
            "heading",
            "|",
            "bold",
            "italic",
            "link",
            "bulletedList",
            "numberedList",
            "blockQuote",
            "insertTable",
            "undo",
            "redo",
        ],
    },
    "article": {
        "toolbar": [
            "heading",
            "|",
            "bold",
            "italic",
            "underline",
            "strikethrough",
            "link",
            "|",
            "bulletedList",
            "numberedList",
            "todoList",
            "outdent",
            "indent",
            "|",
            "blockQuote",
            "insertTable",
            "imageUpload",
            "mediaEmbed",
            "codeBlock",
            "|",
            "sourceEditing",
            "removeFormat",
            "undo",
            "redo",
        ],
        "heading": {
            "options": [
                {"model": "paragraph", "title": "Paragraph", "class": "ck-heading_paragraph"},
                {"model": "heading2", "view": "h2", "title": "Heading 2", "class": "ck-heading_heading2"},
                {"model": "heading3", "view": "h3", "title": "Heading 3", "class": "ck-heading_heading3"},
                {"model": "heading4", "view": "h4", "title": "Heading 4", "class": "ck-heading_heading4"},
            ],
        },
        "image": {
            "toolbar": [
                "imageTextAlternative",
                "|",
                "imageStyle:alignLeft",
                "imageStyle:alignCenter",
                "imageStyle:alignRight",
                "imageStyle:side",
            ],
            "styles": ["full", "side", "alignLeft", "alignCenter", "alignRight"],
        },
        "table": {
            "contentToolbar": [
                "tableColumn",
                "tableRow",
                "mergeTableCells",
                "tableProperties",
                "tableCellProperties",
            ],
        },
        "link": {
            "addTargetToExternalLinks": True,
            "defaultProtocol": "https://",
        },
        "height": "520px",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@theupmedia.com")
MOBILE_UPLOAD_API_KEY = os.getenv("MOBILE_UPLOAD_API_KEY", "")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv("CELERY_TASK_TIME_LIMIT", "3600"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "3300"))

LIVE_TV_RENDER_USE_CELERY = os.getenv("LIVE_TV_RENDER_USE_CELERY", "True").lower() == "true"
LIVE_TV_RENDER_ENCODER = os.getenv("LIVE_TV_RENDER_ENCODER", "cpu").lower()
LIVE_TV_RENDER_NVENC_PRESET = os.getenv("LIVE_TV_RENDER_NVENC_PRESET", "p1")
LIVE_TV_RENDER_NVENC_CQ = os.getenv("LIVE_TV_RENDER_NVENC_CQ", "28")

SOCIAL_DOWNLOADER_MAX_DURATION_SECONDS = int(os.getenv("SOCIAL_DOWNLOADER_MAX_DURATION_SECONDS", "1800"))
SOCIAL_DOWNLOADER_MAX_FILE_SIZE = int(os.getenv("SOCIAL_DOWNLOADER_MAX_FILE_SIZE", str(500 * 1024 * 1024)))
SOCIAL_DOWNLOADER_MAX_CONCURRENT_JOBS = int(os.getenv("SOCIAL_DOWNLOADER_MAX_CONCURRENT_JOBS", "1"))
SOCIAL_DOWNLOADER_JOB_TIMEOUT = int(os.getenv("SOCIAL_DOWNLOADER_JOB_TIMEOUT", "1800"))
SOCIAL_DOWNLOADER_DAILY_USER_LIMIT = int(os.getenv("SOCIAL_DOWNLOADER_DAILY_USER_LIMIT", "20"))
SOCIAL_DOWNLOADER_RETENTION_DAYS = int(os.getenv("SOCIAL_DOWNLOADER_RETENTION_DAYS", "7"))

SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
