# Quick Start Guide - Accident Detection Training & Detection

## 🚀 Complete Workflow

### Step 1: Prepare Binary Dataset
Convert the multi-class videodataset to binary classification:

```bash
python prepare_binary_dataset.py
```

This will create `videodataset_binary/` with:
- All accident types → `Accident/` folder
- Negative samples → `Non Accident/` folder

### Step 2: Train the Model
Train YOLOv8 classification model:

```bash
python train_accident_model.py --data videodataset_binary --epochs 50 --batch 32
```

**For GPU (recommended):**
```bash
python train_accident_model.py --data videodataset_binary --epochs 50 --batch 32 --device cuda
```

### Step 3: Run Real-time Detection
Use the trained model for detection:

```bash
python accident_detection_realtime.py --display --source 0
```

**With video file:**
```bash
python accident_detection_realtime.py --display --source path/to/video.mp4
```

## 📋 Complete Command Sequence

```bash
# 1. Prepare dataset
python prepare_binary_dataset.py

# 2. Train model (CPU)
python train_accident_model.py --data videodataset_binary --epochs 50

# 3. Train model (GPU - faster)
python train_accident_model.py --data videodataset_binary --epochs 50 --device cuda

# 4. Run detection with webcam
python accident_detection_realtime.py --display --source 0

# 5. Run detection with video file
python accident_detection_realtime.py --display --source video.mp4
```

## 📁 Expected File Structure

```
yolo/
├── videodataset/                          # Original dataset
├── videodataset_binary/                   # Binary dataset (created in Step 1)
│   ├── train/
│   │   ├── Accident/
│   │   └── Non Accident/
│   ├── val/
│   │   ├── Accident/
│   │   └── Non Accident/
│   └── data.yaml
├── runs/classify/accident_detection_model/  # Trained model (after Step 2)
│   └── weights/
│       └── best.pt
├── prepare_binary_dataset.py
├── train_accident_model.py
└── accident_detection_realtime.py
```

## ⚙️ Training Options

### Basic Training (CPU)
```bash
python train_accident_model.py --data videodataset_binary --epochs 50
```

### Advanced Training (GPU)
```bash
python train_accident_model.py \
    --data videodataset_binary \
    --model yolov8s-cls.pt \
    --epochs 100 \
    --batch 32 \
    --device cuda
```

### Model Sizes
- `yolov8n-cls.pt` - Nano (fastest, smallest)
- `yolov8s-cls.pt` - Small (balanced)
- `yolov8m-cls.pt` - Medium (better accuracy)
- `yolov8l-cls.pt` - Large (high accuracy)
- `yolov8x-cls.pt` - Extra Large (best accuracy)

## 🎯 Detection Options

### Basic Detection
```bash
python accident_detection_realtime.py --display --source 0
```

### Adjust Sensitivity
```bash
# Less false positives (stricter)
python accident_detection_realtime.py --display --source 0 --threshold 0.98 --min-margin 0.40

# More sensitive (detect more)
python accident_detection_realtime.py --display --source 0 --threshold 0.90 --min-margin 0.20
```

### Save Output Video
```bash
python accident_detection_realtime.py --source video.mp4 --save output.mp4 --display
```

## ⏱️ Expected Times

- **Dataset Preparation**: 2-5 minutes (depends on dataset size)
- **Training (CPU)**: 2-6 hours (depends on epochs and dataset size)
- **Training (GPU)**: 30 minutes - 2 hours (much faster)
- **Detection**: Real-time (depends on hardware)

## 🔧 Troubleshooting

### Out of Memory During Training
```bash
# Reduce batch size
python train_accident_model.py --data videodataset_binary --batch 16
```

### Slow Training
```bash
# Use GPU
python train_accident_model.py --data videodataset_binary --device cuda

# Use smaller model
python train_accident_model.py --data videodataset_binary --model yolov8n-cls.pt
```

### False Positives in Detection
```bash
# Increase threshold and margin
python accident_detection_realtime.py --display --source 0 --threshold 0.98 --min-margin 0.40
```

## ✅ Verification

After training, verify the model exists:
```bash
# Check if model file exists
Test-Path "runs\classify\accident_detection_model\weights\best.pt"
```

## 📚 More Information

- See `README_TRAINING.md` for detailed training guide
- See `TRAINING_GUIDE.md` for advanced training options
- See `REQUIREMENTS.md` for required files and dependencies


