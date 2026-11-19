# Агентство по ремонту квартир (ЛР7)

## Запуск (Windows)

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

`seed_demo` можно запускать повторно: данные не дублируются. Он заполняет все таблицы (не меньше 10 записей в каждой).

Сайт: http://127.0.0.1:8000/ , админка: http://127.0.0.1:8000/admin/

## Тестовые пользователи (пароль у всех `demo12345`)

| Логин | Роль | Что видит на главной |
|---|---|---|
| (без входа) | гость | каталог и примеры запросов |
| `client1` ... `client5` | клиент | + свои заказы |
| `manager1`, `manager2` | менеджер | + все заказы |
| `admin` | суперпользователь | + бригады и финансы |

Если `admin` уже был создан через `createsuperuser`, у него остаётся ваш пароль: сид его не меняет.
Если суперпользователя нет, создайте его: `python manage.py createsuperuser`.
