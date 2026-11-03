# Агентство по ремонту квартир

Учебный проект по курсу «Веб-разработка» (Django 5).

## Запуск (Windows)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

Сайт: http://127.0.0.1:8000/ , админка: http://127.0.0.1:8000/admin/
