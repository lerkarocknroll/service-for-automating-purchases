from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .models import ConfirmEmailToken, User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter
from requests import get
from yaml import load, Loader
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

@shared_task
def send_email_task(subject, message, to_email):

# Асинхронная отправка email

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[to_email]
        )
        msg.send()
        return {'status': True, 'message': f'Email sent to {to_email}'}
    except Exception as e:
        return {'status': False, 'error': str(e)}

@shared_task
def do_import_task(shop_user_id, url):

   # Асинхронный импорт товаров для магазина
    try:
        # Валидация URL
        validate_url = URLValidator()
        validate_url(url)
    except ValidationError as e:
        return {'status': False, 'error': str(e)}

    # Загрузка файла
    try:
        response = get(url, timeout=30)
        if response.status_code != 200:
            return {'status': False, 'error': 'Failed to fetch file'}
    except Exception as e:
        return {'status': False, 'error': str(e)}

    # Парсинг YAML
    try:
        data = load(response.content, Loader=Loader)
        if not data:
            return {'status': False, 'error': 'Empty or invalid YAML'}
    except Exception as e:
        return {'status': False, 'error': f'YAML parsing error: {str(e)}'}

    # Создание или обновление магазина
    shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=shop_user_id)

    # Обновление категорий
    for category in data['categories']:
        category_obj, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
        category_obj.shops.add(shop.id)

    # Удаляем старые данные о товарах магазина
    ProductInfo.objects.filter(shop_id=shop.id).delete()

    # Импорт товаров
    imported_count = 0
    for item in data['goods']:
        product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
        product_info = ProductInfo.objects.create(
            product_id=product.id,
            external_id=item['id'],
            model=item['model'],
            price=item['price'],
            price_rrc=item['price_rrc'],
            quantity=item['quantity'],
            shop_id=shop.id
        )
        for name, value in item['parameters'].items():
            param, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.create(
                product_info_id=product_info.id,
                parameter_id=param.id,
                value=str(value)
            )
        imported_count += 1

    return {'status': True, 'message': f'Imported {imported_count} products for shop {shop.name}'}