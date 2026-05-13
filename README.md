# Видеоаналитика СИЗ: контроль каски на потоке

Инженерный **video-first** пайплайн для промышленного видеонаблюдения: детекция человека / головы / каски, трекинг, временная логика событий и экспорт **`no_hardhat`** (и опционально **`no_vest`**) в `events.csv` / `events.jsonl` с профилированием производительности.

---

## Скачать веса и демо-видео

В репозитории **нет** больших файлов (веса `.pt`, ролики `.mp4`). Чтобы запустить проект «с нуля», скачайте подготовленный пакет:

**[→ Скачать с Google Drive](https://drive.google.com/drive/folders/1YmBQYMUwpaXqmMdpY5acyaaalxJCVmNv)**

После скачивания распакуйте содержимое в корень клона согласно разделу «Быстрый старт» ниже (или откройте `google_drive_bundle/README.md` в этом репозитории — там та же логика).

---

## Возможности

| Область | Что сделано |
| --- | --- |
| Источник | Файл, камера, RTSP |
| Детекция | `person`, `head`, `hardhat`, опционально `vest` |
| Нагрузка | Сэмплинг по FPS, motion gating |
| Контекст | ROI (в т.ч. авто) |
| Трекинг | Стабильные `track_id`, ассоциация голова–каска |
| События | Временная логика, cooldown от спама |
| Наблюдаемость | FPS, задержки, `runtime_profile.json` |
| Эксперименты | Абляции, event-level оценка (`tools/`) |

---

## Архитектура (кратко)

**Источник → препроцесс → сэмплинг / motion gate → YOLO + трекинг → ROI-проходы голова/каска → временная логика → события и метрики + аннотированное видео.**

Подробнее: [`docs/architecture.md`](docs/architecture.md).

---

## Структура репозитория

| Путь | Назначение |
| --- | --- |
| `main.py` | CLI |
| `ppe_monitoring/` | Пайплайн, конфиг, детектор, трекер, motion, события, визуализация |
| `configs/` | `baseline`, `proposed`, абляции |
| `tools/` | `run_ablation.py`, `eval_events.py`, вспомогательные скрипты |
| `docs/` | Архитектура, протоколы оценки, конфигурация |
| `examples/` | Пример конфига, манифеста, GT |
| `models/` | Сюда кладутся веса (см. `models/README.md`) |
| `google_drive_bundle/` | **Локальная** сборка для выгрузки на Drive (см. README внутри; бинарники не в Git) |

---

## Требования

- **Python 3.11** (рекомендуется; см. CI).
- Виртуальное окружение.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-pipeline.txt
```

---

## Быстрый старт после скачивания с Drive

1. Склонируйте репозиторий.
2. Из архива с Drive скопируйте:
   - `*.pt` из папки `models/` архива → в **`models/`** проекта;
   - `yolov8s.pt` из корня архива → в **корень** проекта;
   - `videos/hardhat_input_video.mp4` → в **`input_files/`** (или укажите свой путь).
3. Запуск (короткий демо-прогон):

```bash
python main.py --config config.example.yaml --source input_files/hardhat_input_video.mp4 --no-preview --max-frames 200
```

Справка по аргументам:

```bash
python main.py --help
```

---

## Оценка событий (event-level)

После прогонов с `output_files/experiments/...`:

```bash
python tools/eval_events.py --run-group <имя_группы> --experiments-root output_files/experiments --gt-dir data/gt_events --tolerance-frames 0
```

Метрики и форматы: [`docs/evaluation.md`](docs/evaluation.md), [`docs/e2_evaluation_protocol.md`](docs/e2_evaluation_protocol.md).

---

## Сбор пакета для Drive у себя на диске

В репозитории есть папка **`google_drive_bundle/`**: в неё можно скопировать веса и короткий ролик для ручной загрузки на Google Drive. Подробности — в [`google_drive_bundle/README.md`](google_drive_bundle/README.md).  
Содержимое пакета (кроме `README.md`) **не коммитится** в Git.

---

## CI

При каждом push в `master` / `main` запускаются установка зависимостей, smoke-import и `unittest`. Статус смотрите на вкладке **Actions** репозитория.

---

## Ограничения

- Качество зависит от камеры, освещения и размера каски в кадре.
- События **`no_hardhat`** — вспомогательный сигнал; для операционных решений нужна человеческая проверка.
- Проект позиционируется как **инженерный прототип**, а не сертифицированная система безопасности.

---

## Лицензия

Проект распространяется под **Apache License 2.0** — см. файл [`LICENSE`](LICENSE).

---

## Контакты и ссылки

- Репозиторий: этот проект на GitHub.
- Артефакты для запуска: **[Google Drive](https://drive.google.com/drive/folders/ВСТАВЬТЕ_ID_ПАПКИ)** (замените ссылку на свою папку или файл).

После публикации ссылки обновите этот абзац и при необходимости `google_drive_bundle/README.md`.
