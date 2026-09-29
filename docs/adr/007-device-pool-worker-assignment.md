# ADR 007: DevicePool — детерминированное распределение по xdist worker_id

**Статус:** Accepted
**Дата:** 2026-04-20
**Автор:** Ситников Сергей (ssrjkk)

## Контекст

При параллельном выполнении тестов через pytest-xdist каждый worker —
отдельный процесс. N worker'ов должны разделить M устройств/эмуляторов
так чтобы два worker'а не открыли Appium-сессию на одном устройстве
одновременно и не получили коллизию портов.

## Проблема

Стандартный подход — File-based lock или Redis-based distributed lock.
Оба требуют внешней синхронизации между процессами, усложняют setup и
ломаются в Docker/CI-средах где файловая система или Redis недоступны.

## Решение

**Детерминированное вычисление** без синхронизации: каждый worker сам
вычисляет свой индекс из собственного `worker_id` ('gw0' → 0, 'gw1' → 1),
затем берёт `devices[index]` — одно устройство ровно одному worker'у.

```python
def get_for_worker(self, worker_id: str | None) -> Device:
    if not self._devices:
        raise ValueError("DevicePool: no devices registered — call register() first")

    if worker_id is None or worker_id == "master":
        index = 0
    else:
        digits = "".join(c for c in worker_id if c.isdigit())
        index = int(digits) if digits else 0

    if index >= len(self._devices):
        raise ValueError(
            f"DevicePool: worker {worker_id!r} needs device #{index}, but only "
            f"{len(self._devices)} device(s) are registered. Register one device per "
            f"worker or run with -n {len(self._devices)}."
        )
    return self._devices[index]
```

Порты назначаются по индексу при регистрации (`system_port = BASE + index`)
— поэтому два worker'а с разными `worker_id` **математически гарантированно**
получают разные устройства и, следом, разные порты. Никакого IPC не нужно.

`register()` дополнительно отклоняет повторный `udid` (`ValueError: device
... is already registered`): две записи об одном эмуляторе — это не "два
устройства", а две параллельные Appium-сессии на одном устройстве, которые
дерутся за его UiAutomator2-сервер при формально уникальных портах.

## Пересмотр 2026-09-27: отказ от modulo round-robin

В первой редакции здесь был `devices[index % len(devices)]`, а в
"Обосновании" — утверждение что при N worker'ов > M устройств тесты
"выполняются последовательно на доступных устройствах, не падают".
Утверждение было неверным: остаток от деления выдаёт одинаковый индекс
разным worker'ам (gw0 и gw2 при двух устройствах → один и тот же `Device`
вместе с его `systemPort`/`chromedriverPort`/`mjpegServerPort`), то есть
ровно ту коллизию параллельных сессий, ради отсутствия которой пул и
создавался. Проявлялось это не ошибкой конфигурации, а необъяснимым
таймаутом в середине прогона.

Round-robin убран: worker'ов больше чем устройств — `ValueError` с
actionable-сообщением на первом же обращении к пулу (см. код выше), а не
молчаливое разделение устройства между процессами.

## Обоснование

- Детерминированность → воспроизводимость (при одинаковом пуле устройств
  всегда один и тот же worker получает одно и то же устройство).
- Отсутствие lock → нет deadlock, нет cleanup при crash worker'а.
- Fail-fast вместо round-robin: несовместимые N>M — это ошибка запуска
  (нужно столько эмуляторов, сколько worker'ов), а не режим работы.
  Коллизию двух процессов на одном устройстве невозможно отличить от
  "флакающего" теста, поэтому лучше упасть до первого тапа.

## Предположения

- pytest-xdist worker_id всегда имеет формат 'gw{N}' (gw0, gw1, ...).
  Это задокументированный формат xdist, не undocumented internals.
  Цифр в `worker_id` нет (или worker'а нет вовсе — `None`/'master') →
  индекс 0.
- DevicePool регистрируется до старта worker'ов (в conftest.py на уровне
  сессии). Если регистрация происходит внутри worker'а — каждый worker
  создаст свой пул и детерминированность нарушится.

## Облачная матрица: синтетический udid (`_pool_key()`)

Облако (Sauce Labs / BrowserStack) не выдаёт serial'ов устройств, но
`register()` требует уникальный `udid`. Без ключа матрица "Pixel 6 на 13.0"
+ "Pixel 6 на 14.0" — одна и та же модель под двумя версиями ОС — упала бы
на `ValueError: device ... is already registered` ещё до первого теста.
Поэтому провайдеры в `mobius/utils/cloud_providers.py` генерируют ключ
самим:

```python
def _pool_key(device: str, version: str) -> str:
    return f"{device}_{version}".replace(" ", "_").lower()
```

- `udid` из профиля облака приоритетнее генерируемого:
  `udid=p.get("udid") or _pool_key(...)` — реальный serial не перетирается.
- Версия входит в ключ именно поэтому: одного `device` недостаточно.
- `build_pool()` после регистрации прогоняет `assert_no_port_collisions()`.
- Порты, назначенные пулом, в облачные capabilities НЕ уходят —
  `capabilities_for()` у обоих провайдеров собирает только
  `appium:deviceName` и `sauce:options`/`bstack:options`, порты назначает
  облако. Локальный путь с портами — `DevicePool.to_capabilities_extra()`.

## Ограничения

- M устройств < N worker'ов → `ValueError` (см. секцию "Пересмотр" выше):
  регистрируй по устройству на worker или запускай с `-n M`. Разделение
  одного устройства между параллельными worker'ами пулом не
  поддерживается.
- Не поддерживает динамическое добавление устройств в runtime — пул
  фиксируется в начале сессии.
- Локальный пул ограничен числом эмуляторов на раннере; для матрицы
  шире — облачные провайдеры (секция `_pool_key()` выше).
