# CapybaraVPN — custom integration for Home Assistant

Интеграция использует тот же JSON API, что и личный кабинет `capybaravpn.app`.

## Авторизация

POST `/api/auth/login`

```json
{
  "email": "<email>",
  "password": "<password>"
}
```

Интеграция сохраняет session cookie только в памяти и при HTTP 401/403 автоматически выполняет повторный вход.

## Используемые endpoint'ы

- `/api/auth/me`
- `/api/auth/summary`
- `/api/keys`
- `/api/keys/{client_id}/details`
- `/api/keys/{client_id}/connection`
- `/api/keys/{client_id}/addons-preview?force_web=true`
- `/api/auth/me/payments?limit=50`

Ссылки на VPN-подписку (`key`, `remnawave_link`) в Home Assistant не публикуются.

## Сущности

Аккаунт:
- Баланс
- Последний платёж
- Дата последнего платежа

Для каждого VPN-ключа:
- Действует до
- Осталось дней
- Тариф
- Стоимость тарифа (`total_price_rub`; для текущей конфигурации 4 устройства API отдавал 546 RUB)
- Использовано трафика
- Лимит устройств
- Подключено устройств
- Протокол
- Подключение (binary sensor)
- Подписка заморожена (binary sensor)

Обновление: каждые 60 минут.

## Установка

1. Распаковать папку `custom_components/capybaravpn` в `/config/custom_components/capybaravpn`.
2. Перезапустить Home Assistant.
3. Открыть: **Настройки → Устройства и службы → Добавить интеграцию**.
4. Найти **CapybaraVPN**.
5. Ввести email и пароль.

## Важно

Это не публично документированный API CapybaraVPN, а внутренний API веб-кабинета.
