# Architecture Decision Records

ADR — фиксируем архитектурные решения с контекстом и обоснованием.
Формат: [MADR](https://adr.github.io/madr/)

| ID | Название | Статус |
|----|----------|--------|
| [001](001-appium-options-vs-desired-capabilities.md) | AppiumOptions вместо desired_capabilities | Accepted |
| [002](002-config-driven-vs-hardcoded-screens.md) | Config-driven вместо только hardcoded Screen Objects | Accepted |
| [003](003-structured-logging-warning-vs-debug.md) | WARNING vs DEBUG в структурированном логировании | Accepted |
| [004](004-core-vs-test-dependencies-split.md) | Разделение core/test зависимостей | Accepted |
| [005](005-reference-sut-deprecated.md) | Референсный SUT архивирован — риск и план миграции | Accepted (риск принят, задокументирован) |
| [006](006-wire-protocol-tests-vs-real-device.md) | Wire-protocol тесты вместо real-device в CI | Accepted (временная мера) |
| [007](007-device-pool-worker-assignment.md) | DevicePool — детерминированное распределение по worker_id | Accepted |
| [008](008-smart-retry-classification.md) | Smart retry — инфраструктура vs реальные баги | Accepted |
| [009](009-device-profile-loader-config-driven-capabilities.md) | DeviceProfileLoader — config-driven device capabilities | Accepted |
