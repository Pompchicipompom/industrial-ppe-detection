# CLEAN_REPO_REPORT.md

Отчёт о сборке чистого публичного репозитория для GitHub.
Документ оставлен в каталоге временно — после первичной проверки его
можно удалить перед `git push`.

## 1. Что скопировано

| Откуда | Куда |
| --- | --- |
| `ppe_monitoring/{config,detector,event_consolidator,event_logic,geometry,metrics_constants,motion,person_confirmation,person_head_confirmation,pipeline,profiler,rtsp_health,tracker,types,video_id,visualization,__init__}.py` | `ppe_monitoring/` |
| `tools/eval_events.py` | `tools/eval_events.py` |

Все остальные файлы написаны заново и не имеют связи с исходной
рабочей копией (см. раздел 2).

## 2. Что написано заново для чистой версии

- `README.md` — итоговый, на русском, без маркетинга;
- `main.py` — компактная CLI без отладочной/исторической логики
  оригинального main.py;
- `configs/production_hardhat.yaml`, `configs/production_vest.yaml`,
  `configs/example_video.yaml`;
- `examples/example_config_hardhat.yaml`,
  `examples/example_config_vest.yaml`,
  `examples/README.md`;
- `tools/consolidate_events.py` — отдельная CLI пост-обработки;
- `docs/architecture.md`, `docs/event_logic.md`, `docs/evaluation.md`,
  `docs/results_summary.md`, `docs/model_files.md`,
  `docs/repository_structure.md`;
- `models/README.md`;
- `requirements.txt`, `.gitignore`, `.gitattributes`.

## 3. Что исключено

Не переносились:

- `docs/vkr_update/` (исторические эксперименты и черновики);
- `tools/event_level_eval/`, `tools/runtime_benchmark/`,
  `tools/business_metrics/`, `tools/run_experiments.py`,
  `tools/run_ablation.py`, `tools/preflight_e2.py`,
  `tools/inspect_model_classes.py`,
  `tools/export_acceleration_artifacts.py`,
  `tools/manual_eval/`, `tools/proposed_v2_sh17/`,
  `tools/proposed_vs_sh17/`, `tools/clip2safety_baseline/`,
  `tools/clipbased_baseline/`, `tools/demo_videos/`,
  `tools/benchmark_model_runtime.py`,
  `tools/prepare_unified_ppe_dataset.py`,
  `tools/final_artifact_accumulation/`,
  `tools/final_robustness_audit/`,
  `tools/gpu_extra_artifacts/`,
  `tools/run_e2_latency_repeats.py`;
- ablation и grid-snippet конфиги
  (`configs/ablation_*`, `configs/_grid_snippet_*`,
  `configs/baseline.yaml`, `configs/proposed_*`,
  `configs/debug_visual_demo.yaml`);
- любые `*.pt`, `*.onnx`, `*.engine`, `*.bin`, `*.xml`;
- `input_files/`, `output_files/`, `runs/` исходного проекта;
- `.git/`, `.venv*`, `__pycache__/`, `kernel.errors.txt`,
  `CLEANUP_REPORT.md`, исторический `README.md`,
  `report_summary.py`;
- архивы, видеофайлы, dataset-каталоги.

## 4. Почему baseline-код не включён

Baseline-методы (SH17, YOLO-World, CLIP/VLM) использовались только в
исследовательской части ВКР для сравнения. Финальный модуль ими не
зависит, и их код не нужен для запуска `main.py`. Сравнительные
результаты приведены в основном тексте ВКР. Включение
исследовательских скриптов в публичный репозиторий привело бы к
дублированию веток разработки и затруднило бы навигацию.

## 5. Какие веса нужны и почему они не включены

| Имя файла | Назначение |
| --- | --- |
| `hardhat_detection_yolo11_200_epochs_best_02032025.pt` | основной hardhat-детектор |
| `helmet_vest_repo_best.pt` | vest-детектор с классом `NO-Safety Vest` |
| `hardhat_binary_best.pt` *(опционально)* | бинарная hardhat-модель |

Веса не входят в репозиторий по двум причинам:

- размер `.pt`-файлов (от единиц до десятков МБ) не подходит для
  обычного git-репозитория без Git LFS;
- условия распространения исходных весов (включая SH17) требуют
  отдельной передачи.

Архив с весами передаётся отдельно (например, через файловое хранилище
или релиз-ассет). Инструкция: `docs/model_files.md`,
`models/README.md`.

## 6. Как запустить проект

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# поместить веса в models/ и видео в input/demo.mp4

python main.py --config configs/production_hardhat.yaml \
    --source input/demo.mp4 --output runs/demo_hardhat
python main.py --config configs/production_vest.yaml \
    --source input/demo.mp4 --output runs/demo_vest
```

## 7. Какие проверки выполнены

| Проверка | Команда | Результат |
| --- | --- | --- |
| Tree | `Get-ChildItem -Recurse -File` | 41 файл, 0.247 МБ |
| Large files > 10 MB | `Where-Object Length -gt 10485760` | пусто |
| Веса (`*.pt/.onnx/.engine/.bin/.xml/.tflite/.pb`) | `Where-Object Extension -in …` | пусто |
| Видео (`*.mp4/.avi/.mov/.mkv/.webm`) | `Where-Object Extension -in …` | пусто |
| Файлы `.env` | `Where-Object Name -like *.env` | пусто |
| Слова `chatgpt/cursor/prompt/llm/gpt/claude/turboscribe` | `Select-String -CaseSensitive:$false …` | пусто |
| `python -m compileall .` | компиляция всех модулей | без ошибок |
| `python main.py --help` | вывод справки | OK, без необходимости весов |
| `python tools/consolidate_events.py --help` | вывод справки | OK |
| Импорт `EventConsolidatorV3` + smoke-консолидация | `python -c "…"` | 2 → 1 событие, OK |

### Результаты сводно

```
1) Large files > 10MB
(пусто)

2) Weights
(пусто)

3) Videos
(пусто)

4) .env
(пусто)

5) LLM/prompt traces
(пусто)

6) python -m compileall — без ошибок
7) python main.py --help — OK
   Импорт EventConsolidatorV3 — OK (2 raw -> 1 emitted)
```

## 8. Что нужно решить вручную перед `git push`

1. **Получить веса**. Без них `main.py` запустится до загрузки модели и
   завершится ошибкой Ultralytics. Команда `--help` от этого не
   зависит.
2. **Лицензия**. На текущем этапе LICENSE не добавлен. Перед
   публикацией принять решение о лицензии и добавить файл (или
   оставить «без лицензии», что означает «все права защищены»).
3. **Demo-видео для проверки**. Положить демонстрационное видео в
   `input/demo.mp4` (или указать собственный путь через `--source`).
4. **Удалить временный CLEAN_REPO_REPORT.md** (этот файл) перед
   первым публичным `git push`, если не хочется его публиковать.
5. **Инициализировать git и установить remote**:
   ```bash
   cd public_repo_clean
   git init
   git add .
   git commit -m "Initial public release"
   git branch -M main
   git remote add origin git@github.com:<user>/<repo>.git
   git push -u origin main
   ```
   До первого `git add .` ещё раз убедиться, что в `models/`, `input/`,
   `output/`, `runs/` нет «забытых» бинарников. `.gitignore` уже
   исключает `*.pt`, `*.mp4` и пр., но локально каталоги могут быть
   заполнены.

## 9. Совместимость и осторожности

- В `ppe_monitoring/visualization.py` используется PIL для рисования
  кириллических подписей. Системный шрифт ищется по стандартным путям
  (`/usr/share/fonts/...`, `C:/Windows/Fonts/...`). На сервере без
  GUI/шрифтов рендер всё ещё работает за счёт fallback'а на дефолтный
  шрифт PIL.
- `ultralytics` при отсутствии `yolov8s.pt` для person fallback'а
  пытается автоматически его скачать. Если репозиторий должен
  работать offline, заранее положите `yolov8s.pt` в корень.
- Текущие production-конфиги выставляют `use_half: false` для
  максимальной совместимости CPU/GPU. На сильной GPU можно выставить
  `use_half: true` вручную, ожидая ускорения.
