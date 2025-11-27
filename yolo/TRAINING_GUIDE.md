# Training Guide for Accident Detection Model

## Step 1: Prepare Binary Dataset

The `videodataset` contains multiple accident types. We need to convert it to binary classification (Accident vs Non-Accident).

```bash
python prepare_binary_dataset.py --source videodataset --output videodataset_binary
```

This will:
- Combine all accident types into one "Accident" class
- Keep negative_samples as "Non Accident" class
- Create train/val splits with Accident/Non Accident folders
- Generate data.yaml file

## Step 2: Train the Model

Train the YOLOv8 classification model:

```bash
python train_accident_model.py --data videodataset_binary --epochs 50 --batch 32 --device cpu
```

### Training Parameters

- `--data`: Path to binary dataset (default: `videodataset_binary`)
- `--model`: Pretrained model (default: `yolov8n-cls.pt`)
  - Options: `yolov8n-cls.pt` (nano, fastest), `yolov8s-cls.pt` (small), `yolov8m-cls.pt` (medium), etc.
- `--epochs`: Number of training epochs (default: 50)
- `--batch`: Batch size (default: 32)
- `--device`: Device to use (default: `cpu`)
  - Use `cuda` or `0` for GPU if available
- `--imgsz`: Input image size (default: 224)
- `--patience`: Early stopping patience (default: 20)

### Example Commands

**CPU Training:**
```bash
python train_accident_model.py --data videodataset_binary --epochs 50 --batch 16
```

**GPU Training:**
```bash
python train_accident_model.py --data videodataset_binary --epochs 50 --batch 32 --device cuda
```

**Larger Model:**
```bash
python train_accident_model.py --data videodataset_binary --model yolov8s-cls.pt --epochs 50
```

## Step 3: Run Real-time Detection

After training, use the trained model for detection:

```bash
python accident_detection_realtime.py --display --source 0
```

Or with a video file:
```bash
python accident_detection_realtime.py --display --source path/to/video.mp4
```

## Directory Structure After Training

```
runs/classify/accident_detection_model/
├── weights/
│   ├── best.pt          # Best model (use this for inference)
│   └── last.pt          # Last checkpoint
├── args.yaml            # Training arguments
├── results.png          # Training curves
└── ...
```

## Model Selection

- **yolov8n-cls.pt**: Fastest, smallest model (good for real-time)
- **yolov8s-cls.pt**: Balanced speed and accuracy
- **yolov8m-cls.pt**: Better accuracy, slower
- **yolov8l-cls.pt**: High accuracy, slower
- **yolov8x-cls.pt**: Best accuracy, slowest

## Tips

1. **GPU Training**: Use GPU if available for much faster training
2. **Batch Size**: Adjust based on available memory (larger batch = faster training)
3. **Early Stopping**: Model will stop training if no improvement for `patience` epochs
4. **Image Size**: 224 is standard, but you can try 320 or 640 for better accuracy (slower)

## Troubleshooting

### Out of Memory
- Reduce batch size: `--batch 16` or `--batch 8`
- Reduce image size: `--imgsz 160`

### Slow Training
- Use GPU: `--device cuda`
- Use smaller model: `yolov8n-cls.pt`
- Reduce image size: `--imgsz 160`

### Poor Accuracy
- Train for more epochs: `--epochs 100`
- Use larger model: `yolov8s-cls.pt` or `yolov8m-cls.pt`
- Increase image size: `--imgsz 320`


