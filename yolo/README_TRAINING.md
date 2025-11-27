# Complete Training and Detection Workflow

## Overview

This guide shows how to train a YOLOv8 model using the `videodataset` and use it for real-time accident detection.

## Step-by-Step Instructions

### Step 1: Prepare Binary Dataset

The `videodataset` contains multiple accident types. Convert it to binary classification (Accident vs Non-Accident):

```bash
python prepare_binary_dataset.py
```

This creates `videodataset_binary` with:
- `train/Accident/` - All accident types combined
- `train/Non Accident/` - Negative samples
- `val/Accident/` - Validation accident images
- `val/Non Accident/` - Validation non-accident images
- `data.yaml` - Dataset configuration

### Step 2: Train the Model

Train YOLOv8 classification model:

```bash
python train_accident_model.py --data videodataset_binary --epochs 50 --batch 32
```

**For GPU (if available):**
```bash
python train_accident_model.py --data videodataset_binary --epochs 50 --batch 32 --device cuda
```

**Training will:**
- Load the binary dataset
- Train for specified epochs
- Save best model to `runs/classify/accident_detection_model/weights/best.pt`
- Show training progress and validation accuracy

### Step 3: Run Real-time Detection

After training, use the model for detection:

**Webcam:**
```bash
python accident_detection_realtime.py --display --source 0
```

**Video file:**
```bash
python accident_detection_realtime.py --display --source path/to/video.mp4
```

**Save output video:**
```bash
python accident_detection_realtime.py --source video.mp4 --save output.mp4 --display
```

## Quick Start (All Steps)

```bash
# 1. Prepare dataset
python prepare_binary_dataset.py

# 2. Train model
python train_accident_model.py --data videodataset_binary --epochs 50

# 3. Run detection
python accident_detection_realtime.py --display --source 0
```

## File Structure

```
yolo/
├── videodataset/                    # Original multi-class dataset
├── videodataset_binary/             # Binary dataset (created by prepare_binary_dataset.py)
│   ├── train/
│   │   ├── Accident/
│   │   └── Non Accident/
│   ├── val/
│   │   ├── Accident/
│   │   └── Non Accident/
│   └── data.yaml
├── runs/classify/accident_detection_model/  # Trained model (after training)
│   └── weights/
│       └── best.pt
├── prepare_binary_dataset.py        # Dataset preparation script
├── train_accident_model.py          # Training script
└── accident_detection_realtime.py   # Real-time detection script
```

## Training Parameters

### Basic Training
```bash
python train_accident_model.py --data videodataset_binary --epochs 50
```

### Advanced Training
```bash
python train_accident_model.py \
    --data videodataset_binary \
    --model yolov8s-cls.pt \
    --epochs 100 \
    --batch 32 \
    --imgsz 224 \
    --device cuda \
    --patience 20
```

### Parameters Explained
- `--data`: Path to dataset directory
- `--model`: Pretrained model (yolov8n-cls.pt, yolov8s-cls.pt, etc.)
- `--epochs`: Number of training epochs
- `--batch`: Batch size (adjust based on memory)
- `--imgsz`: Input image size (224, 320, 640)
- `--device`: Device (cpu, cuda, or GPU index)
- `--patience`: Early stopping patience

## Detection Parameters

### Basic Detection
```bash
python accident_detection_realtime.py --display --source 0
```

### Advanced Detection
```bash
python accident_detection_realtime.py \
    --model runs/classify/accident_detection_model/weights/best.pt \
    --source 0 \
    --threshold 0.95 \
    --min-margin 0.30 \
    --window-size 15 \
    --display
```

### Parameters Explained
- `--model`: Path to trained model
- `--source`: Video source (0 for webcam, or video file path)
- `--threshold`: Confidence threshold (0.0-1.0, higher = less false positives)
- `--min-margin`: Minimum margin between accident and non-accident probability
- `--window-size`: Moving average window size
- `--display`: Show video window
- `--save`: Save output video

## Model Performance

After training, check the model performance:
- Training curves: `runs/classify/accident_detection_model/results.png`
- Best model: `runs/classify/accident_detection_model/weights/best.pt`
- Validation accuracy: Shown in terminal after training

## Troubleshooting

### Dataset Preparation
- **Error: Directory not found**: Make sure `videodataset` exists
- **Error: No images**: Check that videodataset has train/val folders with images

### Training
- **Out of memory**: Reduce batch size (`--batch 16` or `--batch 8`)
- **Slow training**: Use GPU (`--device cuda`) or smaller model (`yolov8n-cls.pt`)
- **Poor accuracy**: Train longer (`--epochs 100`) or use larger model

### Detection
- **Model not found**: Check model path in `--model` argument
- **False positives**: Increase threshold (`--threshold 0.98`) or margin (`--min-margin 0.40`)
- **Missing real accidents**: Decrease threshold (`--threshold 0.90`) or margin (`--min-margin 0.20`)

## Next Steps

1. Train the model with your dataset
2. Tune detection parameters for your use case
3. Deploy for real-time monitoring
4. Monitor and adjust thresholds as needed

## Notes

- The binary dataset combines all accident types into one "Accident" class
- Training time depends on dataset size, model size, and hardware
- GPU training is significantly faster than CPU
- Model accuracy improves with more training data and epochs


