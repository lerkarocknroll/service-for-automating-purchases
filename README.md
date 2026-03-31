# Backend-приложение для автоматизации закупок в розничной сети

## Оглавление
1. [Описание проекта](#описание-проекта)
2. [Технологический стек](#технологический-стек)
3. [Функциональные возможности](#функциональные-возможности)
4. [Структура проекта](#структура-проекта)
5. [Модели данных](#модели-данных)
6. [API Endpoints](#api-endpoints)
7. [Установка и запуск](#установка-и-запуск)
8. [Работа с Docker](#работа-с-docker)
9. [Тестирование](#тестирование)
10. [Примеры запросов](#примеры-запросов)
11. [Postman коллекция](#postman-коллекция)

---

## Описание проекта

REST API сервис для автоматизации закупок в розничной сети. Система позволяет:

- **Покупателям** просматривать каталог товаров от разных поставщиков, формировать корзину, оформлять заказы и отслеживать их статус
- **Поставщикам** загружать и обновлять прайс-листы в формате YAML, управлять статусом приёма заказов, просматривать оформленные заказы
- **Администраторам** управлять всеми данными через Django Admin

Все взаимодействие осуществляется через REST API. Асинхронная обработка задач (email-рассылки, импорт товаров) реализована с помощью Celery и Redis.

---

## Технологический стек

| Технология | Версия | Назначение |
|------------|--------|------------|
| Python | 3.11 | Язык программирования |
| Django | 5.0 | Web-фреймворк |
| Django REST Framework | 3.14 | Создание REST API |
| Celery | 5.3 | Асинхронная обработка задач |
| Redis | 7.0 | Брокер сообщений для Celery |
| PostgreSQL | 15 | База данных (основная) |
| SQLite | - | База данных (для разработки) |
| Docker | - | Контейнеризация |
| Gunicorn | - | WSGI сервер |

---

## Функциональные возможности

### Для покупателя
- Регистрация и авторизация
- Подтверждение email
- Просмотр каталога товаров с фильтрацией по магазинам и категориям
- Управление контактами (адреса доставки)
- Работа с корзиной (добавление, удаление, изменение количества)
- Оформление заказов
- Просмотр истории заказов
- Получение email-уведомлений о статусе заказа

### Для поставщика
- Загрузка/обновление прайс-листов через YAML-файл
- Включение/отключение приёма заказов
- Просмотр заказов с товарами своего магазина
- Асинхронный импорт товаров

### Для администратора
- Управление пользователями и их ролями
- Управление магазинами, категориями, товарами
- Управление заказами и их статусами
- Просмотр всех данных через Django Admin

---

## Структура проекта

```
netology_pd_diplom/
│
├── backend/                           # Основное приложение
│   ├── migrations/                    # Миграции базы данных
│   ├── __init__.py
│   ├── admin.py                       # Настройка админ-панели
│   ├── apps.py                        # Конфигурация приложения
│   ├── models.py                      # Модели данных
│   ├── serializers.py                 # Сериализаторы для API
│   ├── signals.py                     # Сигналы (email уведомления)
│   ├── tasks.py                       # Celery задачи
│   ├── tests.py                       # Тесты
│   ├── urls.py                        # Маршруты API
│   └── views.py                       # API представления
│
├── netology_pd_diplom/                # Конфигурация проекта
│   ├── __init__.py                    # Инициализация Celery
│   ├── celery.py                      # Настройка Celery
│   ├── settings.py                    # Настройки Django
│   ├── urls.py                        # Корневые маршруты
│   └── wsgi.py                        # WSGI конфигурация
│
├── data/                              # Тестовые данные
│   └── shop1.yaml                     # Пример прайс-листа
│
├── .env.example                       # Шаблон переменных окружения
├── .gitignore                         # Игнорируемые файлы
├── docker-compose.yml                 # Docker оркестрация
├── Dockerfile                         # Docker образ
├── manage.py                          # Утилита управления Django
├── README.md                          # Документация
└── requirements.txt                   # Зависимости Python
```

---

## Модели данных

### Пользователи (User)
- Расширенная модель пользователя Django
- Поля: email, first_name, last_name, company, position, type (shop/buyer)
- Аутентификация по email

### Магазин (Shop)
- `name` - название магазина
- `url` - ссылка на прайс-лист
- `user` - владелец магазина
- `state` - статус приёма заказов

### Категория (Category)
- `name` - название категории
- `shops` - магазины, предоставляющие товары этой категории

### Продукт (Product)
- `name` - название товара
- `category` - категория товара

### Информация о продукте (ProductInfo)
- `product` - ссылка на продукт
- `shop` - магазин-поставщик
- `model` - модель товара
- `external_id` - ID в системе поставщика
- `quantity` - количество на складе
- `price` - цена
- `price_rrc` - рекомендованная розничная цена

### Параметры (Parameter, ProductParameter)
- Гибкая система характеристик товаров (ключ-значение)

### Контакты (Contact)
- Адрес доставки: city, street, house, structure, building, apartment, phone

### Заказ (Order)
- `user` - покупатель
- `dt` - дата и время
- `state` - статус (basket, new, confirmed, assembled, sent, delivered, canceled)
- `contact` - адрес доставки

### Позиция заказа (OrderItem)
- `order` - заказ
- `product_info` - информация о товаре
- `quantity` - количество

---

## API Endpoints

### Аутентификация и пользователи
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/user/register` | Регистрация пользователя |
| POST | `/api/v1/user/confirm` | Подтверждение email |
| POST | `/api/v1/user/login` | Авторизация |
| GET | `/api/v1/user/details` | Получение профиля |
| POST | `/api/v1/user/details` | Обновление профиля |

### Каталог
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/categories` | Список категорий |
| GET | `/api/v1/shops` | Список магазинов |
| GET | `/api/v1/products` | Каталог товаров |

### Корзина и заказы
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/basket` | Просмотр корзины |
| POST | `/api/v1/basket` | Добавление товаров |
| PUT | `/api/v1/basket` | Обновление количества |
| DELETE | `/api/v1/basket` | Удаление товаров |
| GET | `/api/v1/orders` | Список заказов |
| POST | `/api/v1/orders` | Оформление заказа |

### Контакты
| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/contacts` | Список контактов |
| POST | `/api/v1/contacts` | Создание контакта |
| PUT | `/api/v1/contacts` | Обновление контакта |
| DELETE | `/api/v1/contacts` | Удаление контакта |

### Для поставщиков
| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/partner/update` | Импорт прайс-листа |
| GET | `/api/v1/partner/state` | Статус магазина |
| POST | `/api/v1/partner/state` | Изменение статуса |
| GET | `/api/v1/partner/orders` | Заказы поставщика |

---

## Установка и запуск

### Требования
- Python 3.11+
- PostgreSQL 15+ (опционально)
- Redis 7.0+
- Git

### Настройка переменных окружения

1. Скопируйте файл `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```

2. Отредактируйте `.env`, указав свои данные:
   - Пароль PostgreSQL
   - Настройки email
   - Секретный ключ Django

> **Важно:** Файл `.env` добавлен в `.gitignore` и не попадёт в репозиторий.

### Локальный запуск

1. **Клонирование репозитория**
   ```bash
   git clone <repository-url>
   cd netology_pd_diplom
   ```

2. **Создание виртуального окружения**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Установка зависимостей**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Настройка базы данных**

   Для SQLite (разработка) — настройки уже в `settings.py`:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.sqlite3',
           'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
       }
   }
   ```

   Для PostgreSQL — укажите параметры в файле `.env`:
   ```
   POSTGRES_DB=diplom_db
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   ```

5. **Применение миграций**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

6. **Запуск Redis**
   ```bash
   redis-server
   ```

7. **Запуск Celery worker** (в отдельном терминале)
   ```bash
   celery -A netology_pd_diplom worker --loglevel=info
   ```

8. **Запуск Django сервера**
   ```bash
   python manage.py runserver
   ```

9. **Проверка работы**
   - Админка: http://127.0.0.1:8000/admin/
   - API: http://127.0.0.1:8000/api/v1/

---

## Работа с Docker

### Предварительные требования
- Docker Desktop 20.10+
- Docker Compose 2.0+

### Запуск через Docker Compose

1. **Сборка и запуск контейнеров**
   ```bash
   docker-compose up --build
   ```

2. **Проверка работы**
   ```bash
   docker-compose ps
   ```

3. **Остановка контейнеров**
   ```bash
   docker-compose down
   ```

### Состав Docker-контейнеров
| Сервис | Порт | Назначение |
|--------|------|------------|
| web | 8000 | Django приложение (Gunicorn) |
| db | 5432 | PostgreSQL |
| redis | 6379 | Redis брокер |
| celery_worker | - | Celery worker |

---

## Тестирование

### Запуск тестов
```bash
python manage.py test backend.tests
```

### Тестовый сценарий
1. Регистрация покупателя
2. Авторизация и получение токена
3. Просмотр каталога товаров
4. Добавление товаров в корзину
5. Создание контакта
6. Оформление заказа
7. Проверка списка заказов

---

## Примеры запросов

### Регистрация пользователя
```bash
curl -X POST http://127.0.0.1:8000/api/v1/user/register \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Иван",
    "last_name": "Петров",
    "email": "user@example.com",
    "password": "securepass123",
    "company": "",
    "position": ""
  }'
```

### Авторизация
```bash
curl -X POST http://127.0.0.1:8000/api/v1/user/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123"
  }'
```

### Получение списка товаров
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/products?shop_id=1&category_id=1"
```

### Добавление товара в корзину
```bash
curl -X POST http://127.0.0.1:8000/api/v1/basket \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": "[{\"product_info\": 1, \"quantity\": 2}]"
  }'
```

### Импорт прайс-листа (для магазина)
```bash
curl -X POST http://127.0.0.1:8000/api/v1/partner/update \
  -H "Authorization: Token SHOP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://127.0.0.1:8001/shop1.yaml"
  }'
```

---

## Postman коллекция

В репозитории находится файл `backend/Diplom_API_Collection.json` — готовая коллекция для Postman.

### Импорт коллекции
1. Откройте Postman
2. Нажмите **Import**
3. Выберите файл `Diplom_API_Collection.json`
4. В переменной `base_url` укажите `http://127.0.0.1:8000/api/v1`
5. Выполняйте запросы в порядке:
   - `01. Register User` → регистрация
   - `02. Login User` → авторизация (токен сохранится автоматически)
   - `03. Get Products` → просмотр товаров
   - `06. Add to Basket` → добавление в корзину
   - `08. Create Contact` → создание контакта
   - `10. Create Order` → оформление заказа
   - `11. Get Orders` → просмотр заказов

---

## Переменные окружения

Создайте файл `.env` в корне проекта на основе `.env.example`:

```env
# Django
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True

# Database
POSTGRES_DB=diplom_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.mail.ru
EMAIL_HOST_USER=your_email@mail.ru
EMAIL_HOST_PASSWORD=your_password_here
EMAIL_PORT=465
EMAIL_USE_SSL=True
```