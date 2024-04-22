# -*- coding: utf-8 -*-
import os

SECRET_KEY = "dummy"

TEST_RUNNER = "tests.runner.PytestTestRunner"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "django.contrib.sites",
    "tests.testapp",
    "schedule",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DATABASE_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get("DATABASE_NAME", ":memory:"),
        "USER": os.environ.get("DATABASE_USER"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD"),
        "HOST": os.environ.get("DATABASE_HOST"),
        "PORT": os.environ.get("DATABASE_PORT"),
    }
}

SITE_ID = 1

MEDIA_ROOT = "/tmp/schedule_test_media/"

MEDIA_PATH = "/media/"

ROOT_URLCONF = "tests.testapp.urls"

DEBUG = True

TEMPLATE_DEBUG = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "debug": TEMPLATE_DEBUG,
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATIC_URL = "/static/"

SHELL_PLUS_SUBCLASSES_IMPORT_MODULES_BLACKLIST = [
    "tests.testapp.scripts.invalid_import_script",
    "setup",
]

SHELL_PLUS_PRE_IMPORTS = [
    "import sys, os",
]
SHELL_PLUS_POST_IMPORTS = [
    "import traceback",
    "import pprint",
    "import os as test_os",
]

SILENCED_SYSTEM_CHECKS = ["models.W027", "models.W042"]
