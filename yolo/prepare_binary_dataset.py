#!/usr/bin/env python3
"""
Prepare binary classification dataset from videodataset
Combines all accident types into 'Accident' class and negative_samples into 'Non Accident' class
"""

import os
import shutil
from pathlib import Path


def prepare_binary_dataset(
    source_dir: str = "videodataset",
    output_dir: str = "videodataset_binary",
    train_split: str = "train",
    val_split: str = "val"
):
    """
    Reorganize multi-class dataset into binary classification (Accident vs Non-Accident).
    
    Args:
        source_dir: Source directory with multi-class structure
        output_dir: Output directory for binary dataset
        train_split: Training split directory name
        val_split: Validation split directory name
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    
    # Accident class folders (all except negative_samples)
    accident_folders = [
        "collision_with_motorcycle",
        "collision_with_stationary_object",
        "drifting_or_skidding",
        "fire_or_explosions",
        "head_on_collision",
        "objects_falling",
        "other_crash",
        "pedestrian_hit",
        "rear_collision",
        "rollover",
        "side_collision"
    ]
    
    non_accident_folders = ["negative_samples"]
    
    # Create output directory structure
    train_accident_dir = output_path / train_split / "Accident"
    train_non_accident_dir = output_path / train_split / "Non Accident"
    val_accident_dir = output_path / val_split / "Accident"
    val_non_accident_dir = output_path / val_split / "Non Accident"
    
    for dir_path in [train_accident_dir, train_non_accident_dir, val_accident_dir, val_non_accident_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Process training data
    print("Processing training data...")
    train_accident_count = 0
    train_non_accident_count = 0
    
    # Copy accident images
    for folder in accident_folders:
        source_folder = source_path / train_split / folder
        if source_folder.exists():
            images = list(source_folder.glob("*.jpg"))
            for img in images:
                # Create unique filename to avoid conflicts
                new_name = f"{folder}_{img.name}"
                shutil.copy2(img, train_accident_dir / new_name)
                train_accident_count += 1
            print(f"  Copied {len(images)} images from {folder}")
    
    # Copy non-accident images
    for folder in non_accident_folders:
        source_folder = source_path / train_split / folder
        if source_folder.exists():
            images = list(source_folder.glob("*.jpg"))
            for img in images:
                shutil.copy2(img, train_non_accident_dir / img.name)
                train_non_accident_count += 1
            print(f"  Copied {len(images)} images from {folder}")
    
    # Process validation data
    print("\nProcessing validation data...")
    val_accident_count = 0
    val_non_accident_count = 0
    
    # Copy accident images
    for folder in accident_folders:
        source_folder = source_path / val_split / folder
        if source_folder.exists():
            images = list(source_folder.glob("*.jpg"))
            for img in images:
                # Create unique filename to avoid conflicts
                new_name = f"{folder}_{img.name}"
                shutil.copy2(img, val_accident_dir / new_name)
                val_accident_count += 1
            print(f"  Copied {len(images)} images from {folder}")
    
    # Copy non-accident images
    for folder in non_accident_folders:
        source_folder = source_path / val_split / folder
        if source_folder.exists():
            images = list(source_folder.glob("*.jpg"))
            for img in images:
                shutil.copy2(img, val_non_accident_dir / img.name)
                val_non_accident_count += 1
            print(f"  Copied {len(images)} images from {folder}")
    
    # Create data.yaml file
    data_yaml = f"""path: {output_path.absolute()}
train: {train_split}
val: {val_split}

nc: 2
names:
  0: Accident
  1: Non Accident
"""
    
    yaml_path = output_path / "data.yaml"
    with open(yaml_path, "w") as f:
        f.write(data_yaml)
    
    print(f"\n✅ Binary dataset prepared successfully!")
    print(f"   Output directory: {output_path.absolute()}")
    print(f"   Training - Accident: {train_accident_count} images")
    print(f"   Training - Non-Accident: {train_non_accident_count} images")
    print(f"   Validation - Accident: {val_accident_count} images")
    print(f"   Validation - Non-Accident: {val_non_accident_count} images")
    print(f"   Total training images: {train_accident_count + train_non_accident_count}")
    print(f"   Total validation images: {val_accident_count + val_non_accident_count}")
    print(f"\n   Data YAML saved to: {yaml_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Prepare binary classification dataset from videodataset"
    )
    parser.add_argument(
        "--source",
        type=str,
        default="videodataset",
        help="Source directory with multi-class structure"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="videodataset_binary",
        help="Output directory for binary dataset"
    )
    parser.add_argument(
        "--train-split",
        type=str,
        default="train",
        help="Training split directory name"
    )
    parser.add_argument(
        "--val-split",
        type=str,
        default="val",
        help="Validation split directory name"
    )
    
    args = parser.parse_args()
    
    prepare_binary_dataset(
        source_dir=args.source,
        output_dir=args.output,
        train_split=args.train_split,
        val_split=args.val_split
    )


