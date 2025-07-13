# TSM-NIDS: TSMixer Network IDS

This directory contains implementations of TSM-NIDS (TSMixer Network Intrusion Detection System), a time series neural network approach for IoT network security analysis, including attack classification, attack identification, and IoT digital twin applications.

## 📁 Directory Structure

```
TSMixer/
├── AttackClassification/     # Multi-class attack classification using TON-IoT dataset
├── AttackIdentification/     # Binary attack detection using TON-IoT dataset
├── IoTDigitalTwin/          # Classification using captured real-world IoT data
└── readme.md               # This file
```

## 🎯 Overview

This project implements TSM-NIDS (TSMixer Network Intrusion Detection System), leveraging TSMixer neural networks for three main use cases:

1. **Attack Classification**: Multi-class classification to identify specific types of IoT attacks
2. **Attack Identification**: Binary classification to detect whether network traffic is malicious
3. **IoT Digital Twin**: Real-world IoT data analysis using captured dataset

## 📊 Datasets

### TON-IoT Dataset (AttackClassification & AttackIdentification)
- **Source**: Publicly available TON-IoT dataset
- **Description**: Comprehensive IoT network traffic dataset with labeled attack types
- **Usage**: Training and evaluation of TSM-NIDS models for security analysis
- **Classes**: Multiple attack types including DoS, DDoS, backdoor, injection, etc.

### Captured IoT Data (IoTDigitalTwin)
- **Source**: Real-world IoT devices in controlled environment
- **Description**: Network traffic captured from actual IoT devices
- **Usage**: Digital twin implementation and real-world validation
- **Format**: Time series data with network flow features

## 🏗️ Model Architecture

The TSM-NIDS system implements a time series neural network based on the mixer architecture described in the [TSMixer paper](https://arxiv.org/pdf/2303.06053.pdf). This implementation is adapted from the [pytorch-tsmixer](https://github.com/ditschuk/pytorch-tsmixer) repository for IoT security classification tasks.

### Key Components:
- **Sequence Length**: Variable based on time window
- **Feature Dimension**: Network flow features (packet size, duration, etc.)
- **Hidden Dimensions**: Configurable (default: 64)
- **Number of Blocks**: 15 layers for deep feature learning
- **Attention Mechanisms**: Optional channel and temporal attention
- **Dropout**: 0.1 for regularization

### TSM-NIDS Architecture:
The system leverages mixer layers for processing time series data, offering a robust approach for network intrusion detection tasks. Unlike the original forecasting implementation, TSM-NIDS is specifically adapted for:
- **Multi-class Classification**: Attack type identification
- **Binary Classification**: Attack detection
- **Real-time Processing**: IoT network traffic analysis

## 📂 AttackClassification

**Purpose**: Multi-class classification of IoT attack types using TON-IoT dataset

### Scalers Tested
- **MinMaxScaler**: Normalizes features to [0,1] range
- **RobustScaler**: Uses median and IQR for outlier-resistant scaling
- **StandardScaler**: Z-score normalization (mean=0, std=1)

### Feature Engineering Approaches
1. **Base (1base)**: Original features without modification
2. **Mutual Information (2mi)**: Features selected based on MI scores
3. **Correlation (3corr)**: Features selected based on correlation analysis
4. **SMOTE (4smote)**: Synthetic minority oversampling technique
5. **PCA (5pca)**: Principal component analysis for dimensionality reduction
6. **Combined (mi_corr_smote_pca)**: Multiple techniques combined

### Key Files
- `tsmixermulti-tonpreprocess.ipynb`: Data preprocessing pipeline
- `tsmixermulti-tonprocess_*.ipynb`: Model training with different approaches
- `FeaturesCorrelationMatrix.png`: Feature correlation visualization
- `FeaturesMutualInformationScores.png`: MI scores visualization

## 📂 AttackIdentification

**Purpose**: Binary classification for attack detection using TON-IoT dataset

### Model Implementation
- **Base Model**: `tsmixerbasemodel.py` - Core TSMixer implementation
- **Binary Classification**: Distinguish between normal and malicious traffic
- **Evaluation Metrics**: Accuracy, precision, recall, F1-score

### Experimental Setup
Same scaler and feature engineering approaches as AttackClassification:
- Multiple scaling techniques
- Feature selection methods
- Data augmentation with SMOTE
- Dimensionality reduction with PCA

### Key Files
- `tsmixerbasemodel.py`: Base model architecture and training functions
- `tsmixerbinary-tonprocess_*.ipynb`: Binary classification experiments
- Confusion matrices and performance visualizations

## 📂 IoTDigitalTwin

**Purpose**: Real-world IoT data analysis using captured dataset

### Data Source
- **Captured Dataset**: Real IoT device network traffic
- **Environment**: Controlled IoT testbed
- **Devices**: Various IoT sensors and actuators
- **Features**: Network flow characteristics, timing patterns

### Classification Tasks
1. **Binary Classification**: Normal vs. anomalous behavior
2. **Multi-Class Classification**: Different device types or behavior patterns

### Key Files
- `tsmixermulti-preprocess.ipynb`: Preprocessing for captured data
- Separate folders for binary and multi-class approaches

## 🚀 Getting Started

### Prerequisites
```bash
# Core dependencies
pip install torch torchvision
pip install pandas numpy scikit-learn
pip install matplotlib seaborn
pip install jupyter notebook
pip install imbalanced-learn  # for SMOTE

# Optional: Install the reference TSMixer implementation
pip install pytorch-tsmixer
```

### Reference Implementation
This project is based on the PyTorch TSMixer implementation by [ditschuk](https://github.com/ditschuk/pytorch-tsmixer), which provides a clean and efficient implementation of the TSMixer architecture described in the [original paper](https://arxiv.org/pdf/2303.06053.pdf).

**Key Adaptations for IoT Security:**
- Modified for classification instead of forecasting
- Added support for multiple scalers and feature engineering
- Integrated with IoT-specific preprocessing pipelines
- Enhanced for real-time attack detection

### Running Experiments

1. **Data Preprocessing**:
   ```bash
   # For TON-IoT dataset preprocessing
   jupyter notebook AttackClassification/Full_IoT_Network/tsmixermulti-tonpreprocess.ipynb
   
   # For captured IoT data preprocessing
   jupyter notebook IoTDigitalTwin/tsmixermulti-preprocess.ipynb
   ```

2. **Model Training**:
   ```bash
   # For attack classification (multi-class)
   jupyter notebook AttackClassification/Full_IoT_Network/tsmixermulti-tonprocess_base_s.ipynb
   
   # For attack identification (binary)
   jupyter notebook AttackIdentification/Full_IoT_Network/tsmixerbinary-tonprocess_base_s.ipynb
   
   # For IoT digital twin analysis
   jupyter notebook IoTDigitalTwin/Binary\ Classification/[notebook_name].ipynb
   ```

3. **Evaluation**:
   - Confusion matrices and performance metrics are generated automatically
   - Results saved as PNG files for visualization
   - Model checkpoints saved for inference

### Quick Start Example
```python
# Based on pytorch-tsmixer structure
from tsmixer import TSMixer
import torch

# Load your preprocessed IoT data
# X_train: (batch_size, sequence_length, num_features)
# y_train: (batch_size,) for classification

# Initialize model
model = TSMixer(
    seq_len=X_train.shape[1],
    feat_dim=X_train.shape[2], 
    num_classes=len(unique_labels),
    hidden_dim=64
)

# Training loop (simplified)
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
criterion = torch.nn.CrossEntropyLoss()

for epoch in range(num_epochs):
    outputs = model(X_train)
    loss = criterion(outputs, y_train)
    loss.backward()
    optimizer.step()
    optimizer.zero_grad()
```

## 📈 Model Performance

### Feature Selection Impact
- **Mutual Information**: Selects most informative features
- **Correlation Analysis**: Removes redundant features
- **Combined Approaches**: Best overall performance

### Scaling Comparison
- **StandardScaler**: Generally best for neural networks
- **RobustScaler**: Better for datasets with outliers
- **MinMaxScaler**: Good for bounded feature ranges

## 🔧 Configuration

### Model Hyperparameters
```python
# Adapted from pytorch-tsmixer for classification tasks
TSMixer(
    seq_len=sequence_length,      # Time window size
    feat_dim=feature_count,       # Number of input features
    num_classes=class_count,      # Number of output classes
    hidden_dim=64,               # Hidden layer size
    num_blocks=15,               # Number of mixer blocks
    dropout=0.1,                 # Dropout rate
    use_channel_attention=False, # Channel attention
    use_temporal_attention=False # Temporal attention
)
```

### Training Parameters
- **Learning Rate**: 0.001 (Adam optimizer)
- **Batch Size**: 32
- **Epochs**: 30 (with early stopping)
- **Patience**: 5 epochs
- **Scheduler**: ReduceLROnPlateau

### Example Usage (Based on pytorch-tsmixer)
```python
import torch
import torch.nn as nn
from tsmixer import TSMixer  # Your adapted version

# Initialize model for classification
model = TSMixer(
    seq_len=100,        # 100 time steps
    feat_dim=41,        # 41 network features
    num_classes=10,     # 10 attack types
    hidden_dim=64
)

# Training setup
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# Forward pass
inputs = torch.randn(32, 100, 41)  # batch_size, seq_len, features
outputs = model(inputs)            # batch_size, num_classes
```

## 📊 Results and Visualization

### Generated Outputs
- Confusion matrices (raw counts and percentages)
- Feature importance scores
- Correlation matrices
- Training history plots
- Performance metrics reports

### File Naming Convention
- `*_confusion_matrix_raw.png`: Raw count confusion matrix
- `*_confusion_matrix_percentage.png`: Percentage confusion matrix
- `Features*.png`: Feature analysis visualizations

## 🔍 Research Applications

### Security Analysis
- Real-time IoT attack detection
- Attack type classification
- Anomaly detection in IoT networks

### Digital Twin Implementation
- IoT device behavior modeling
- Predictive maintenance
- System state monitoring

### References

1. **Original TSMixer Paper**:
   ```bibtex
   @article{tsmixer2023,
     title={TSMixer: An All-MLP Architecture for Time Series Forecasting},
     author={Chen, Si-An and Lin, Chun-Liang and Chandra, Rajarishi and Others},
     journal={arXiv preprint arXiv:2303.06053},
     year={2023}
   }
   ```

2. **PyTorch Implementation Reference**:
   ```bibtex
   @software{pytorch_tsmixer,
     title={PyTorch TSMixer: A pip-installable PyTorch implementation of TSMixer},
     author={ditschuk},
     year={2023},
     url={https://github.com/ditschuk/pytorch-tsmixer}
   }
   ```

## 🙏 Acknowledgments

- **TSMixer Architecture**: Based on the original TSMixer paper by Chen et al. (2023)
- **PyTorch Implementation**: Adapted from [pytorch-tsmixer](https://github.com/ditschuk/pytorch-tsmixer) by ditschuk
- **TON-IoT Dataset**: Used for benchmarking and evaluation
- **IoT Security Research**: Contributions to IoT network security analysis

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📧 Contact

For questions or support, please open an issue on GitHub.