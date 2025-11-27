# Files Required to Run `accident_detection_realtime.py`

## Essential Files

### 1. **Main Script**
- `accident_detection_realtime.py` - The main accident detection script

### 2. **Trained Model** (REQUIRED)
- `runs/classify/video_accident_model/weights/best.pt` - The trained YOLOv8 classification model
  - This is the default model path
  - You can specify a different model using `--model` argument
  - The model file contains the trained weights and class information

### 3. **Python Dependencies** (Install via pip)
Install using: `pip install -r requirements.txt`

Required packages:
- `ultralytics` (>=8.0.0) - YOLOv8 framework
- `opencv-python` (>=4.6.0) - Computer vision library
- `numpy` (>=1.23.0) - Numerical computing
- `torch` (>=1.8.0) - PyTorch deep learning framework
- `torchvision` (>=0.9.0) - PyTorch vision utilities

## Optional Files

### Video Input (Optional)
- Video file (`.mp4`, `.avi`, `.mov`, etc.) - If using video file instead of webcam
- Webcam - Built-in or USB webcam (default source)

### Output (Optional)
- Output directory - For saving processed videos (if using `--save` option)

## Directory Structure

```
yolo/
├── accident_detection_realtime.py    # Main script
├── requirements.txt                   # Python dependencies
├── runs/
│   └── classify/
│       └── video_accident_model/
│           └── weights/
│               └── best.pt           # Trained model (REQUIRED)
└── yoloenv/                          # Virtual environment (optional but recommended)
    └── Scripts/
        └── activate                  # Activate virtual environment
```

## Quick Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   Or if using virtual environment:
   ```bash
   .\yoloenv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Verify model exists:**
   ```bash
   # Check if model file exists
   Test-Path "runs\classify\video_accident_model\weights\best.pt"
   ```

3. **Run the script:**
   ```bash
   python accident_detection_realtime.py --display --source 0
   ```

## Model File Information

The model file (`best.pt`) contains:
- Trained neural network weights
- Class names (Accident, Non Accident)
- Model architecture information
- Training configuration

**Note:** The model file is essential. Without it, the script cannot run. If you don't have the model, you need to train it first using `train_classifier.py`.

## System Requirements

- **Python:** 3.8 or higher
- **Operating System:** Windows, Linux, or macOS
- **RAM:** Minimum 4GB (8GB recommended)
- **GPU:** Optional but recommended for faster processing (CUDA-compatible GPU)
- **Webcam:** Required for real-time detection (or video file)

## Troubleshooting

### Model Not Found
If you get an error "Model file not found":
1. Check if the model path is correct: `runs/classify/video_accident_model/weights/best.pt`
2. Specify custom path: `python accident_detection_realtime.py --model path/to/your/model.pt`
3. Train a model first: `python train_classifier.py`

### Missing Dependencies
If you get import errors:
```bash
pip install ultralytics opencv-python numpy torch torchvision
```

### Webcam Not Working
- Check if webcam is connected
- Try different camera index: `--source 1` or `--source 2`
- Use a video file instead: `--source path/to/video.mp4`

