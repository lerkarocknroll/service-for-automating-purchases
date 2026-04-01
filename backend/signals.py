import logging
from typing import Type

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, User
from backend.tasks import send_email_task

logger = logging.getLogger(__name__)

new_user_registered = Signal()
new_order = Signal()


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """
    Отправляем письмо с токеном для сброса пароля (асинхронно)
    """
    send_email_task.delay(
        f"Password Reset Token for {reset_password_token.user}",
        reset_password_token.key,
        reset_password_token.user.email
    )


@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """
    Отправляем письмо с подтверждением регистрации (асинхронно)
    """
    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)
        send_email_task.delay(
            f"Подтверждение регистрации для {instance.email}",
            f"Ваш токен подтверждения: {token.key}",
            instance.email
        )


@receiver(new_user_registered)
def new_user_registered_handler(sender, user_id, **kwargs):
    """
    Обработчик сигнала регистрации нового пользователя
    """
    try:
        user = User.objects.get(id=user_id)
        logger.info(f"New user registered: {user.email}")
        # Здесь можно добавить дополнительную логику при регистрации
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")


@receiver(new_order)
def new_order_signal(user_id, **kwargs):
    """
    Отправляем письмо при оформлении заказа (асинхронно)
    """
    try:
        user = User.objects.get(id=user_id)
        send_email_task.delay(
            "Обновление статуса заказа",
            "Ваш заказ успешно оформлен и передан в обработку",
            user.email
        )
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found for order notification")