from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from backend.models import Shop, Category, Product, ProductInfo, Order, Contact
import json

User = get_user_model()


class UserRegistrationTest(TestCase):
    #ТЕСТЫ РЕГИСТРАЦИИ И АВТОРИЗАЦИИ ПОЛЬЗОВАТЕЛЕЙ

    def setUp(self):
        self.client = APIClient()

    def test_register_user(self):
        # ТЕСТ РЕГИСТРАЦИИ НОВОГО ПОЛЬЗОВАТЕЛЯ
        data = {
            'first_name': 'Иван',
            'last_name': 'Петров',
            'email': 'test@test.ru',
            'password': 'testpass123',
            'company': '',
            'position': ''
        }
        response = self.client.post('/api/v1/user/register', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['Status'], True)

    def test_login_user(self):
        # ТЕСТ АВТОРИЗАЦИИ ПОЛЬЗОВАТЕЛЯ
        # Создаем пользователя
        user = User.objects.create_user(
            email='login@test.ru',
            password='login123',
            is_active=True
        )

        data = {
            'email': 'login@test.ru',
            'password': 'login123'
        }
        response = self.client.post('/api/v1/user/login', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Token', response.data)


class ShopTest(TestCase):
    # ТЕСТЫ МАГАЗИНОВ

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='shop@test.ru',
            password='shop123',
            type='shop',
            is_active=True
        )
        self.token = Token.objects.create(user=self.user)

    def test_get_shops(self):
        # ТЕСТ ПОЛУЧЕНИЯ СПИСКА МАГАЗИНОВ
        # Создаем магазин
        Shop.objects.create(name='Test Shop', user=self.user, state=True)

        response = self.client.get('/api/v1/shops')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)

    def test_partner_state_get(self):
        # ТЕСТ ПОЛУЧЕНИЯ СТАТУСА МАГАЗИНА
        Shop.objects.create(name='Test Shop', user=self.user, state=True)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get('/api/v1/partner/state')
        self.assertEqual(response.status_code, 200)


class CatalogTest(TestCase):
    # ТЕСТЫ КАТАЛОГА ТОВАРОВ

    def setUp(self):
        self.client = APIClient()

        # Создаем категорию
        self.category = Category.objects.create(name='Смартфоны')

        # Создаем магазин и пользователя
        self.user = User.objects.create_user(
            email='catalog_shop@test.ru',
            password='pass123',
            type='shop',
            is_active=True
        )
        self.shop = Shop.objects.create(name='Test Shop', user=self.user, state=True)

        # Создаем товар
        self.product = Product.objects.create(
            name='Test Phone',
            category=self.category
        )

        # Создаем информацию о товаре
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            external_id=123,
            model='test/model',
            quantity=10,
            price=10000,
            price_rrc=12000
        )

    def test_get_categories(self):
        # ТЕСТ ПОЛУЧЕНИЯ КАТЕГОРИЙ
        response = self.client.get('/api/v1/categories')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_products(self):
        # ТЕСТ ПОЛУЧЕНИЯ ТОВАРОВ
        response = self.client.get('/api/v1/products')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class BasketTest(TestCase):
    # ТЕСТЫ КОРЗИНЫ

    def setUp(self):
        self.client = APIClient()

        # Создаем пользователя
        self.user = User.objects.create_user(
            email='buyer@test.ru',
            password='buyer123',
            type='buyer',
            is_active=True
        )
        self.token = Token.objects.create(user=self.user)

        # Создаем категорию
        self.category = Category.objects.create(name='Смартфоны')

        # Создаем магазин
        self.shop_user = User.objects.create_user(
            email='test_shop@test.ru',
            password='pass123',
            type='shop',
            is_active=True
        )
        self.shop = Shop.objects.create(name='Test Shop', user=self.shop_user, state=True)

        # Создаем товар
        self.product = Product.objects.create(
            name='Test Phone',
            category=self.category
        )

        # Создаем информацию о товаре
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            external_id=123,
            model='test/model',
            quantity=10,
            price=10000,
            price_rrc=12000
        )

    def test_add_to_basket(self):
        # ТЕСТ ДОБАВЛЕНИЯ ТОВАРА В КОРЗИНУ
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        items = json.dumps([{"product_info": self.product_info.id, "quantity": 2}])
        data = {'items': items}

        response = self.client.post('/api/v1/basket', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['Status'], True)

    def test_get_basket(self):
        # ТЕСТ ПРОСМОТРА КОРЗИНЫ
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        # Сначала добавляем товар
        items = json.dumps([{"product_info": self.product_info.id, "quantity": 2}])
        self.client.post('/api/v1/basket', {'items': items}, format='json')

        # Получаем корзину
        response = self.client.get('/api/v1/basket')
        self.assertEqual(response.status_code, 200)


class ContactTest(TestCase):
    # ТЕСТЫ КОНТАКТОВ

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            email='contact@test.ru',
            password='contact123',
            type='buyer',
            is_active=True
        )
        self.token = Token.objects.create(user=self.user)

    def test_create_contact(self):
        # ТЕСТ СОЗДАНИЯ КОНТАКТА
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        data = {
            'city': 'Москва',
            'street': 'Тверская',
            'house': '1',
            'phone': '89991234567'
        }

        response = self.client.post('/api/v1/contacts', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['Status'], True)

    def test_get_contacts(self):
        # ТЕСТ ПОЛУЧЕНИЯ КОНТАКТА
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        # Создаем контакт
        Contact.objects.create(
            user=self.user,
            city='Москва',
            street='Тверская',
            house='1',
            phone='89991234567'
        )

        response = self.client.get('/api/v1/contacts')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class OrderTest(TestCase):
    # ТЕСТЫ ЗАКАЗОВ

    def setUp(self):
        self.client = APIClient()

        # Создаем пользователя
        self.user = User.objects.create_user(
            email='order@test.ru',
            password='order123',
            type='buyer',
            is_active=True
        )
        self.token = Token.objects.create(user=self.user)

        # Создаем категорию
        self.category = Category.objects.create(name='Смартфоны')

        # Создаем магазин
        self.shop_user = User.objects.create_user(
            email='order_shop@test.ru',
            password='pass123',
            type='shop',
            is_active=True
        )
        self.shop = Shop.objects.create(name='Test Shop', user=self.shop_user, state=True)

        # Создаем товар
        self.product = Product.objects.create(
            name='Test Phone',
            category=self.category
        )

        # Создаем информацию о товаре
        self.product_info = ProductInfo.objects.create(
            product=self.product,
            shop=self.shop,
            external_id=123,
            model='test/model',
            quantity=10,
            price=10000,
            price_rrc=12000
        )

        # Создаем контакт
        self.contact = Contact.objects.create(
            user=self.user,
            city='Москва',
            street='Тверская',
            house='1',
            phone='89991234567'
        )

        # Создаем корзину
        self.basket = Order.objects.create(
            user=self.user,
            state='basket'
        )

    def test_create_order(self):
        # ТЕСТ ОФОРМЛЕНИЯ ЗАКАЗА
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        # Добавляем товар в корзину
        items = json.dumps([{"product_info": self.product_info.id, "quantity": 2}])
        self.client.post('/api/v1/basket', {'items': items}, format='json')

        # Оформляем заказ
        data = {
            'id': self.basket.id,
            'contact': self.contact.id
        }
        response = self.client.post('/api/v1/orders', data, format='json')
        self.assertEqual(response.status_code, 200)

    def test_get_orders(self):
        # ТЕСТ ПОЛУЧЕНИЯ ЗАКАЗОВ
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        response = self.client.get('/api/v1/orders')
        self.assertEqual(response.status_code, 200)