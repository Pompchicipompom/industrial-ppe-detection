# Пакет для скачивания (Google Drive / архив)

Здесь лежит **локальная копия** файлов, которые не хранятся в GitHub, но нужны, чтобы любой человек мог **клонировать репозиторий и сразу запустить** демо.

## Содержимое (после копирования скриптом)

| Файл | Назначение |
| --- | --- |
| `models/hardhat_detection_yolo11_200_epochs_best_02032025.pt` | основной детектор (person / head / hardhat) |
| `yolov8s.pt` | fallback-детектор людей (COCO), если включён в конфиге |
| `models/hardhat_binary_best.pt` | опциональная бинарная модель каски (если используете binary backend) |
| `videos/hardhat_input_video.mp4` | короткий демо-ролик (~0,6 МБ) |

Папка `google_drive_bundle/` **игнорируется Git** (кроме этого README), чтобы случайно не закоммитить веса и видео.

## Как подготовить архив для Google Drive

1. Убедитесь, что файлы скопированы в эту папку (см. структуру ниже).
2. Заархивируйте **всю** папку `google_drive_bundle` (или только подпапки `models/`, `videos/`, корневой `yolov8s.pt`).
3. Загрузите архив на Google Drive и выставьте доступ «по ссылке» (или отдельные ссылки на файлы).
4. Вставьте ссылку в корневой `README.md` репозитория (раздел «Скачать веса и демо»).

## Куда распаковать после скачивания

Из корня репозитория:

- файлы из `google_drive_bundle/models/` → в **`models/`** репозитория;
- `yolov8s.pt` → в **корень** репозитория (как в `config.example.yaml`);
- `google_drive_bundle/videos/hardhat_input_video.mp4` → например в **`input_files/`** или укажите путь в `--source`.

## Быстрая проверка

```bash
pip install -r requirements-pipeline.txt
python main.py --config config.example.yaml --source input_files/hardhat_input_video.mp4 --no-preview --max-frames 200
```

Если путей нет или не хватает веса — см. сообщения об ошибке в консоли и `models/README.md` в репозитории.
