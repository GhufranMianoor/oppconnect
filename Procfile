web: gunicorn oppconnect.wsgi:application --workers 3 --timeout 120 --preload
release: python manage.py migrate --no-input && python manage.py collectstatic --no-input
