# Markaz Store

Django reseller store: browse products, set a profit margin, share on WhatsApp, and place cash-on-delivery orders.

## Run locally

Requires Python 3.12+ (Django 6.1).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # optional, for /admin/
python manage.py runserver
```

Open http://127.0.0.1:8000/ (store) and http://127.0.0.1:8000/admin/ (manage categories, products, orders).

Optional env vars: `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` (comma-separated) when serving on a non-localhost domain.

## Tests

```bash
python manage.py test
```
