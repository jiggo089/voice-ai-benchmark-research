# Voice AI Benchmark Research

Исследование голосовых пайплайнов на **LiveKit**: распознавание речи, языковые модели, синтез, паузы и перебивание. Сравниваются облачные конфигурации для русского языка и локальные Nemotron Lightning / Omni на NVIDIA GB10 для английского.

**Начните с [итогового отчёта](REPORT.md)** — в нём приведены общий обзор, срезы по языку, открытым весам и закрытым моделям, результаты по задержке и ограничения сравнения.

The report is in Russian. It compares voice-agent configurations rather than claiming a universal model leaderboard. [Anonymized synthetic benchmark data](data/runs.json) and a CSV summary tool are included. The historical private management API and web UI are intentionally not part of this repository.

## Состав

- `REPORT.md`, `charts/` — выводы, таблицы и воспроизводимые графики.
- `data/runs.json` — 59 обезличенных синтетических прогонов с конфигурациями и метриками, без аудио и личных разговоров.
- `code/benchmark_suite.py` — код сценариев и измерений LiveKit; `code/example_lightning_complex_en.py` — пример английского сценария.
- `code/*_stream.py`, `code/omni_agent.py`, `code/neuraldeep_tts.py` — исследовательские адаптеры аудио.
- `code/summarize.py` — автономная выгрузка данных в CSV; `code/charts.py` — генерация графиков из JSON.
- `docs/` — примеры команд локальных сервисов GB10, предназначенные для адаптации.

## Быстрая проверка данных

Требуется Python 3.9+; для этой части сеть и ключи не нужны:

```bash
python3 code/summarize.py > summary.csv
PYTHONPATH=code python3 -m unittest discover -s code -p test_summarize.py -v
```

Для графиков дополнительно установите `matplotlib`, затем `python3 code/charts.py`.

## Повторение голосовых сценариев

Код сценариев — **исследовательский клиент интеграции, а не готовый сервер**. Понадобятся работающий LiveKit, агент и управляющий API, совместимый с контрактом клиента. API должен поддерживать `POST /api/v1/benchmarks/voice` с конфигурацией и bearer-токеном, возвращать `id`, `server_url`, `participant_token`, а также поддерживать `POST /api/v1/benchmarks/voice/{id}/close`. Агент должен отправлять данные в топике LiveKit `benchmark` в формате событий из `benchmark_suite.py`.

Установите зависимости из `requirements.txt` в отдельное окружение, настройте провайдеров и `BENCHMARK_API_URL` из `.env.example`, создайте совместимый JSON конфигурации и подайте краткоживущий токен через stdin. Пример:

```bash
export BENCHMARK_API_URL=http://localhost:8000
# OPENAI_API_KEY требуется только для генерации новых синтетических записей.
python3 code/example_lightning_complex_en.py \
  --fixtures ./fixtures/english --config ./config.json --output ./results.json < ./short_lived_token
```

Пути и примеры команд в `docs/` требуют подготовленных моделей и ПО. Генерация аудио и вызовы внешних моделей могут тарифицироваться. Оригинальный управляющий API, конфигурация аккаунтов, веб-интерфейс, GPU-образ и модельные веса не опубликованы; поэтому воспроизведение результатов требует собственной интеграции. Не используйте исходные результаты как гарантию работы другого сервера.

## Безопасность и данные

В репозитории нет ключей, пользовательских диалогов или записей. Файл `.env.example` содержит только имена переменных. Не размещайте сервисы моделей в открытом интернете без аутентификации. Результаты содержат только синтетические сценарии и технические поля.

## Лицензия

Содержимое репозитория — [MIT](LICENSE). У моделей, данных провайдеров, SDK и сервисов действуют собственные лицензии и условия.
