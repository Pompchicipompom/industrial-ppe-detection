from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml


TARGET_CLASSES = ["hardhat", "head", "person", "vest"]
TARGET_CLASS_TO_ID = {name: idx for idx, name in enumerate(TARGET_CLASSES)}

# Common source aliases -> unified target class names.
CLASS_ALIASES = {
    "helmet": "hardhat",
    "hard_hat": "hardhat",
    "hardhat": "hardhat",
    "head": "head",
    "person": "person",
    "worker": "person",
    "vest": "vest",
    "safety_vest": "vest",
    "reflective_vest": "vest",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build unified YOLO dataset with classes: hardhat, head, person, vest."
    )
    parser.add_argument(
        "--hardhat-yaml",
        type=str,
        default="datasets/hardhat_rf/data.yaml",
        help="Path to existing hardhat dataset YAML.",
    )
    parser.add_argument(
        "--vest-yaml",
        type=str,
        required=True,
        help="Path to vest dataset YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="datasets/ppe_unified_vest",
        help="Output dataset root directory.",
    )
    return parser.parse_args()


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_split_dir(dataset_yaml: dict, yaml_path: Path, split_key: str) -> Path | None:
    split_value = dataset_yaml.get(split_key)
    if not split_value:
        return None
    if isinstance(split_value, list):
        raise ValueError(f"Split {split_key!r} as list is not supported in this script.")
    split_path = Path(str(split_value))
    if split_path.is_absolute():
        return split_path if split_path.exists() else None
    root = dataset_yaml.get("path")
    if root:
        root_path = Path(str(root))
        if not root_path.is_absolute():
            root_path = (yaml_path.parent / root_path).resolve()
        candidate = (root_path / split_path).resolve()
        if candidate.exists():
            return candidate
    candidate = (yaml_path.parent / split_path).resolve()
    if candidate.exists():
        return candidate
    # Roboflow exports sometimes contain ../train/images even when train/images lives next to YAML.
    # Try normalizing by stripping leading ".." segments.
    normalized_parts = [p for p in split_path.parts if p not in ("..", ".")]
    if normalized_parts:
        fallback = (yaml_path.parent / Path(*normalized_parts)).resolve()
        if fallback.exists():
            return fallback
    return None


def _source_class_map(dataset_yaml: dict) -> dict[int, str]:
    names = dataset_yaml.get("names")
    if isinstance(names, dict):
        return {int(k): str(v) for k, v in names.items()}
    if isinstance(names, list):
        return {idx: str(v) for idx, v in enumerate(names)}
    raise ValueError("Dataset YAML does not contain valid 'names' section.")


def _normalize_to_target(name: str) -> str | None:
    key = str(name).strip().lower().replace("-", "_")
    return CLASS_ALIASES.get(key)


def _paired_paths(images_dir: Path) -> list[tuple[Path, Path]]:
    labels_dir = images_dir.parent / "labels"
    if not labels_dir.exists():
        raise FileNotFoundError(f"Labels folder not found near images: {labels_dir}")
    pairs: list[tuple[Path, Path]] = []
    for img in sorted(images_dir.glob("*")):
        if not img.is_file():
            continue
        label = labels_dir / f"{img.stem}.txt"
        if label.exists():
            pairs.append((img, label))
    return pairs


def _rewrite_label(label_path: Path, source_names: dict[int, str]) -> list[str]:
    out_lines: list[str] = []
    for raw in label_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        cls_id = int(float(parts[0]))
        src_name = source_names.get(cls_id)
        if src_name is None:
            continue
        target_name = _normalize_to_target(src_name)
        if target_name is None:
            continue
        target_id = TARGET_CLASS_TO_ID[target_name]
        out_lines.append(" ".join([str(target_id), *parts[1:5]]))
    return out_lines


def _merge_dataset(
    tag: str,
    dataset_yaml_path: Path,
    split_key: str,
    out_images_dir: Path,
    out_labels_dir: Path,
) -> tuple[int, int]:
    dataset_yaml = _load_yaml(dataset_yaml_path)
    source_names = _source_class_map(dataset_yaml)
    split_dir = _resolve_split_dir(dataset_yaml, dataset_yaml_path, split_key)
    if split_dir is None or not split_dir.exists():
        return 0, 0
    pairs = _paired_paths(split_dir)
    copied = 0
    labeled = 0
    for idx, (img, label) in enumerate(pairs):
        mapped = _rewrite_label(label, source_names)
        if not mapped:
            continue
        out_name = f"{tag}_{img.stem}_{idx:07d}{img.suffix.lower()}"
        dst_img = out_images_dir / out_name
        dst_label = out_labels_dir / f"{Path(out_name).stem}.txt"
        shutil.copy2(img, dst_img)
        dst_label.write_text("\n".join(mapped) + "\n", encoding="utf-8")
        copied += 1
        labeled += 1
    return copied, labeled


def main() -> None:
    args = parse_args()
    hardhat_yaml = Path(args.hardhat_yaml).resolve()
    vest_yaml = Path(args.vest_yaml).resolve()
    if not hardhat_yaml.exists():
        raise FileNotFoundError(f"Hardhat YAML not found: {hardhat_yaml}")
    if not vest_yaml.exists():
        raise FileNotFoundError(f"Vest YAML not found: {vest_yaml}")

    out_root = Path(args.output_dir).resolve()
    for split in ("train", "val", "test"):
        (out_root / "images" / split).mkdir(parents=True, exist_ok=True)
        (out_root / "labels" / split).mkdir(parents=True, exist_ok=True)

    stats: dict[str, dict[str, int]] = {}
    for split in ("train", "val", "test"):
        hi, _ = _merge_dataset(
            tag="hardhat",
            dataset_yaml_path=hardhat_yaml,
            split_key=split if split != "val" else "val",
            out_images_dir=out_root / "images" / split,
            out_labels_dir=out_root / "labels" / split,
        )
        vi, _ = _merge_dataset(
            tag="vest",
            dataset_yaml_path=vest_yaml,
            split_key=split if split != "val" else "val",
            out_images_dir=out_root / "images" / split,
            out_labels_dir=out_root / "labels" / split,
        )
        stats[split] = {"hardhat_images": hi, "vest_images": vi, "total_images": hi + vi}

    data_yaml = out_root / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                f"path: {out_root.as_posix()}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "",
                f"nc: {len(TARGET_CLASSES)}",
                f"names: {TARGET_CLASSES}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"Unified dataset prepared at: {out_root}")
    print(f"data.yaml: {data_yaml}")
    print(f"Target classes: {TARGET_CLASSES}")
    for split, split_stats in stats.items():
        print(f"{split}: {split_stats}")


if __name__ == "__main__":
    main()
