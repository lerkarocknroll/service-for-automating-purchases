import logging
from distutils.util import strtobool
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from requests import get
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json
from yaml import load as load_yaml, Loader

from backend.models import (
    Shop, Category, Product, ProductInfo, Parameter,
    ProductParameter, Order, OrderItem, Contact, ConfirmEmailToken
)
from backend.serializers import (
    UserSerializer, CategorySerializer, ShopSerializer,
    ProductInfoSerializer, OrderItemSerializer, OrderSerializer,
    ContactSerializer
)
from backend.signals import new_user_registered, new_order
from backend.tasks import send_email_task, do_import_task

logger = logging.getLogger(__name__)


class RegisterAccount(APIView):
    """
    Класс для регистрации покупателей
    """

    def post(self, request, *args, **kwargs):
        """
        Регистрация нового пользователя
        """
        required_fields = {'first_name', 'last_name', 'email', 'password', 'company', 'position'}
        if not required_fields.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            validate_password(request.data['password'])
        except Exception as password_error:
            error_array = [str(item) for item in password_error]
            return JsonResponse({'Status': False, 'Errors': {'password': error_array}})

        user_serializer = UserSerializer(data=request.data)
        if not user_serializer.is_valid():
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        user = user_serializer.save()
        user.set_password(request.data['password'])
        user.save()

        # Отправляем сигнал о регистрации нового пользователя
        new_user_registered.send(sender=self.__class__, user_id=user.id)
        return JsonResponse({'Status': True})


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    def post(self, request, *args, **kwargs):
        """
        Подтверждение email пользователя
        """
        if not {'email', 'token'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        token = ConfirmEmailToken.objects.filter(
            user__email=request.data['email'],
            key=request.data['token']
        ).first()

        if not token:
            return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        token.user.is_active = True
        token.user.save()
        token.delete()
        return JsonResponse({'Status': True})


class AccountDetails(APIView):
    """
    Класс для управления профилем пользователя
    """

    def get(self, request: Request, *args, **kwargs):
        """
        Получение данных профиля
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Обновление данных профиля
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if 'password' in request.data:
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = [str(item) for item in password_error]
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            request.user.set_password(request.data['password'])

        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if not user_serializer.is_valid():
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        user_serializer.save()
        return JsonResponse({'Status': True})


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """

    def post(self, request, *args, **kwargs):
        """
        Авторизация пользователя
        """
        if not {'email', 'password'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        user = authenticate(request, username=request.data['email'], password=request.data['password'])

        if user is None or not user.is_active:
            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})

        token, _ = Token.objects.get_or_create(user=user)
        return JsonResponse({'Status': True, 'Token': token.key})


class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


class ProductInfoView(APIView):
    """
    Класс для поиска товаров
    """

    def get(self, request: Request, *args, **kwargs):
        """
        Получение информации о товарах с фильтрацией
        """
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            query &= Q(shop_id=shop_id)
        if category_id:
            query &= Q(product__category_id=category_id)

        queryset = ProductInfo.objects.filter(query).select_related(
            'shop', 'product__category'
        ).prefetch_related('product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


class BasketView(APIView):
    """
    Класс для управления корзиной пользователя
    """

    def get(self, request, *args, **kwargs):
        """
        Получение корзины
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        basket = Order.objects.filter(
            user_id=request.user.id, state='basket'
        ).prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Добавление товаров в корзину
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if not items_string:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            items_dict = load_json(items_string)
        except ValueError:
            return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})

        basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
        objects_created = 0

        for order_item in items_dict:
            order_item.update({'order': basket.id})
            serializer = OrderItemSerializer(data=order_item)
            if not serializer.is_valid():
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

            try:
                serializer.save()
                objects_created += 1
            except IntegrityError as error:
                return JsonResponse({'Status': False, 'Errors': str(error)})

        return JsonResponse({'Status': True, 'Создано объектов': objects_created})

    def delete(self, request, *args, **kwargs):
        """
        Удаление товаров из корзины
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if not items_string:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        items_list = items_string.split(',')
        basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
        query = Q()
        objects_deleted = False

        for order_item_id in items_list:
            if order_item_id.isdigit():
                query |= Q(order_id=basket.id, id=order_item_id)
                objects_deleted = True

        if not objects_deleted:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        deleted_count = OrderItem.objects.filter(query).delete()[0]
        return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

    def put(self, request, *args, **kwargs):
        """
        Обновление количества товаров в корзине
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if not items_string:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            items_dict = load_json(items_string)
        except ValueError:
            return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})

        basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
        objects_updated = 0

        for order_item in items_dict:
            if isinstance(order_item.get('id'), int) and isinstance(order_item.get('quantity'), int):
                objects_updated += OrderItem.objects.filter(
                    order_id=basket.id, id=order_item['id']
                ).update(quantity=order_item['quantity'])

        return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})


class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика
    """

    def post(self, request, *args, **kwargs):
        """
        Запуск асинхронного импорта прайс-листа
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if not url:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        validate_url = URLValidator()
        try:
            validate_url(url)
        except ValidationError as e:
            return JsonResponse({'Status': False, 'Error': str(e)})

        # Запускаем асинхронную задачу импорта
        do_import_task.delay(request.user.id, url)
        return JsonResponse({'Status': True, 'Message': 'Импорт запущен в фоновом режиме'})


class PartnerState(APIView):
    """
    Класс для управления статусом приёма заказов
    """

    def get(self, request, *args, **kwargs):
        """
        Получение статуса магазина
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Изменение статуса магазина
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        state = request.data.get('state')
        if not state:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            Shop.objects.filter(user_id=request.user.id).update(state=strtobool(state))
            return JsonResponse({'Status': True})
        except ValueError as error:
            return JsonResponse({'Status': False, 'Errors': str(error)})


class PartnerOrders(APIView):
    """
    Класс для получения заказов поставщиками
    """

    def get(self, request, *args, **kwargs):
        """
        Получение заказов поставщика
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        orders = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id
        ).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class ContactView(APIView):
    """
    Класс для управления контактами пользователя
    """

    def get(self, request, *args, **kwargs):
        """
        Получение списка контактов
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        contacts = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Создание нового контакта
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if not {'city', 'street', 'phone'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        request.data._mutable = True
        request.data.update({'user': request.user.id})
        serializer = ContactSerializer(data=request.data)

        if not serializer.is_valid():
            return JsonResponse({'Status': False, 'Errors': serializer.errors})

        serializer.save()
        return JsonResponse({'Status': True})

    def delete(self, request, *args, **kwargs):
        """
        Удаление контакта
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_string = request.data.get('items')
        if not items_string:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        items_list = items_string.split(',')
        query = Q()
        objects_deleted = False

        for contact_id in items_list:
            if contact_id.isdigit():
                query |= Q(user_id=request.user.id, id=contact_id)
                objects_deleted = True

        if not objects_deleted:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        deleted_count = Contact.objects.filter(query).delete()[0]
        return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})

    def put(self, request, *args, **kwargs):
        """
        Обновление контакта
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        contact_id = request.data.get('id')
        if not contact_id or not contact_id.isdigit():
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        contact = Contact.objects.filter(id=contact_id, user_id=request.user.id).first()
        if not contact:
            return JsonResponse({'Status': False, 'Errors': 'Контакт не найден'})

        serializer = ContactSerializer(contact, data=request.data, partial=True)
        if not serializer.is_valid():
            return JsonResponse({'Status': False, 'Errors': serializer.errors})

        serializer.save()
        return JsonResponse({'Status': True})


class OrderView(APIView):
    """
    Класс для получения и оформления заказов
    """

    def get(self, request, *args, **kwargs):
        """
        Получение списка заказов
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        orders = Order.objects.filter(
            user_id=request.user.id
        ).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter'
        ).select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        ).distinct()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """
        Оформление заказа из корзины
        """
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if not {'id', 'contact'}.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        order_id = request.data.get('id')
        if not order_id or not order_id.isdigit():
            return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

        try:
            is_updated = Order.objects.filter(
                user_id=request.user.id, id=order_id
            ).update(
                contact_id=request.data['contact'],
                state='new'
            )
        except IntegrityError as error:
            logger.error(f"Order creation error: {error}")
            return JsonResponse({'Status': False, 'Errors': 'Неправильно указаны аргументы'})

        if not is_updated:
            return JsonResponse({'Status': False, 'Errors': 'Заказ не найден'})

        new_order.send(sender=self.__class__, user_id=request.user.id)
        return JsonResponse({'Status': True})