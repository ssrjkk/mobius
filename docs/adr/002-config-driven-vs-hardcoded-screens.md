# ADR 002: Config-driven (AppConfig/YAML) в дополнение к hardcoded Screen Objects

**Статус:** Accepted
**Дата:** 2026-04-10
**Автор:** Ситников Сергей (ssrjkk)

## Контекст

Изначальная архитектура — чистый Screen Object Model: `LoginScreen`,
`HomeScreen` и т.д. с захардкоженными локаторами конкретного приложения
(Sauce Labs My Demo App RN). Чтобы протестировать ДРУГОЕ приложение,
нужно было писать новые Python классы с нуля.

## Проблема

Это противоречит цели "универсальный framework для любого мобильного
приложения". Screen Object Model — правильный паттерн для тестирования
ОДНОГО конкретного приложения, но не даёт быстрый путь "просто укажи
другое приложение и работай".

## Решение

Добавлен `mobius/utils/app_config.py`:
- `AppConfig.load("apps/my_app.yaml")` — декларативное описание
  приложения (capabilities + именованные локаторы)
- `ConfigDrivenScreen` — generic Screen Object, читающий локаторы из
  конфига по ключу, а не из Python-атрибутов класса

## Обоснование

Оба подхода сосуществуют, не конкурируют:
- **Screen Object Model** (`mobius/screens/`) — когда UI сложный,
  нужны сложные flow-методы (`login()`, `fill_shipping()`), и оправдана
  инвестиция в полноценный класс на экран.
- **Config-driven** (`AppConfig`/`ConfigDrivenScreen`) — для быстрого
  smoke-теста незнакомого приложения, для CI где список приложений
  меняется динамически, или когда экран простой (несколько
  tap/type_text без сложной логики).

## Последствия

- Локаторы в YAML не типизированы Python'ом — опечатка в `strategy`
  ловится только в рантайме через fallback на XPath в
  `LocatorSpec.as_tuple()` — компромисс осознанный, не баг.
- ~~`apps/sauce_labs_demo.yaml` — единственный пример конфига~~
  **Обновление 2026-04-19:** добавлен второй, структурно другой конфиг
  `apps/ios_reference_example.yaml` (iOS вместо Android, `ios_predicate`/
  `class_name` locator strategies вместо `accessibility_id`/`xpath`,
  `bundle_id` вместо `app_package`) — `tests/unit/
  TestConfigDrivenGeneralization` подтверждает что механизм реально
  обобщается на структурно другое приложение, не завязан на одну схему.

## Альтернативы рассмотрены

- Page Factory паттерн (аннотации над полями класса, как в Java
  Selenium PageFactory): избыточная сложность для Python, не даёт
  выигрыша над прямым `ConfigDrivenScreen.find(key)`.
- JSON вместо YAML: YAML читаемее для локаторов с длинными XPath
  строками, JSON оставлен как альтернативный формат
  (`AppConfig.load()` поддерживает оба).
