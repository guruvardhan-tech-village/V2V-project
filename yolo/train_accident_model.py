#!/usr/bin/env python3
"""
Train YOLOv8 classification model for binary accident detection
"""

import argparse
from pathlib import Path
from ultralytics import YOLO


def train_model(
    data_path: str = "videodataset_binary",
    model_name: str = "yolov8n-cls.pt",
    epochs: int = 50,
    imgsz: int = 224,
    batch: int = 32,
    device: str = "cpu",
    project: str = "runs/classify",
    name: str = "accident_detection_model",
    patience: int = 20,
):
    """
    Train YOLOv8 classification model for accident detection.
    
    Args:
        data_path: Path to dataset directory (should contain train/val subdirectories)
        model_name: Pretrained model name or path
        epochs: Number of training epochs
        imgsz: Input image size
        batch: Batch size
        device: Device to use ('cpu', 'cuda', or GPU index)
        project: Project directory
        name: Experiment name
        patience: Early stopping patience
    """
    # Check if dataset exists
    data_path_obj = Path(data_path)
    if not data_path_obj.exists():
        print(f"❌ Error: Dataset directory not found: {data_path}")
        print("Please run prepare_binary_dataset.py first to create the binary dataset")
        return None
    
    # Check for data.yaml
    data_yaml = data_path_obj / "data.yaml"
    if not data_yaml.exists():
        print(f"⚠️ Warning: data.yaml not found in {data_path}")
        print("Creating data.yaml...")
        # Create data.yaml
        yaml_content = f"""path: {data_path_obj.absolute()}
train: train
val: val

nc: 2
names:
  0: Accident
  1: Non Accident
"""
        with open(data_yaml, "w") as f:
            f.write(yaml_content)
        print(f"✅ Created data.yaml at {data_yaml}")
    
    # Load model
    print(f"Loading model: {model_name}")
    model = YOLO(model_name)
    
    # Train model
    print(f"\n🚀 Starting training...")
    print(f"   Dataset: {data_path}")
    print(f"   Epochs: {epochs}")
    print(f"   Image size: {imgsz}")
    print(f"   Batch size: {batch}")
    print(f"   Device: {device}")
    print(f"   Patience: {patience}")
    
    results = model.train(
        data=data_path,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=name,
        patience=patience,
        exist_ok=True,
        verbose=True,
    )
    
    # Validate model
    print(f"\n📊 Validating model...")
    val_results = model.val()
    
    # Print results
    print(f"\n✅ Training complete!")
    print(f"   Model saved to: {project}/{name}/weights/best.pt")
    
    if hasattr(val_results, "top1"):
        print(f"   Top-1 Accuracy: {val_results.top1:.2f}%")
    if hasattr(val_results, "top5"):
        print(f"   Top-5 Accuracy: {val_results.top5:.2f}%")
    
    return results, val_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Train YOLOv8 classification model for accident detection"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="videodataset_binary",
        help="Path to dataset directory"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n-cls.pt",
        help="Pretrained model (yolov8n-cls.pt, yolov8s-cls.pt, etc.)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=50,
        help="Number of training epochs"
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=224,
        help="Input image size"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=32,
        help="Batch size"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device ('cpu', 'cuda', or GPU index like '0')"
    )
    parser.add_argument(
        "--project",
        type=str,
        default="runs/classify",
        help="Project directory"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="accident_detection_model",
        help="Experiment name"
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=20,
        help="Early stopping patience"
    )
    
    args = parser.parse_args()
    
    train_model(
        data_path=args.data,
        model_name=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        project=args.project,
        name=args.name,
        patience=args.patience,
    )


