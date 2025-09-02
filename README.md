# IoT Digital Twin Security Testbed

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![GNS3](https://img.shields.io/badge/GNS3-Compatible-green.svg)](https://gns3.com)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-Compatible-orange.svg)](https://tensorflow.org)
[![Jupyter](https://img.shields.io/badge/Jupyter-Notebooks-orange.svg)](https://jupyter.org)
[![License](https://img.shields.io/badge/License-Educational-yellow.svg)](#license)

A comprehensive security testbed for IoT networks using GNS3 virtualization platform. This project provides a controlled environment for researching IoT vulnerabilities, testing security mechanisms, and understanding digital twin concepts in cybersecurity education.

## 🎯 Overview

This testbed simulates real-world IoT environments with digital twin capabilities, allowing security researchers and students to:

- **Study IoT Vulnerabilities**: Test common IoT device security flaws in a safe environment
- **Analyze Network Traffic**: Monitor MQTT and other IoT protocol communications
- **Security Assessment**: Perform penetration testing on virtualized IoT devices
- **AI-Powered Threat Detection**: Use TSM-NIDS for intelligent intrusion detection
- **Attack Classification**: Identify specific types of IoT attacks using machine learning
- **Digital Twin Analysis**: Analyze real-world IoT data for security insights
- **Educational Research**: Learn about IoT security without risk to production systems

## 🏗️ Architecture

The testbed consists of several key components:

```
├── Agent/                    # MQTT broker and IoT simulation tools
│   ├── publish.py           # MQTT message publishing utilities
│   └── retrieve.py          # Data retrieval utilities
├── AttackThreat/            # Security testing framework
│   ├── exploit.py           # Automated vulnerability scanning
│   ├── exploit_interactive.py # Interactive security testing
│   ├── credentials.txt      # Common IoT default credentials
│   ├── brute-force_cycle/   # Brute force attack modules
│   ├── ddos_cycle/          # DDoS attack simulation
│   └── requirements.txt     # Python dependencies
├── TSMixer/                 # TSM-NIDS: AI-powered intrusion detection
│   ├── AttackClassification/ # Multi-class attack type classification
│   ├── AttackIdentification/ # Binary attack detection
│   └── IoTDigitalTwin/      # Real-world IoT data analysis
├── Collected Data/          # Dataset storage and management
├── IoTDevice                # IoT Device Scenarios
│   ├── MQTTScenarios        # MQTT broker and data management
│   ├── MQTTCaptureData/     # MQTT data capture modules
│   └── RTSPCaptureData/     # RTSP stream capture modules
└── README.md               # This documentation
```

## 🚀 Quick Start

### Prerequisites

**Operating System**: Ubuntu 22.04.4 LTS (recommended)

**Required Dependencies**:
- KVM virtualization support
- GNS3 network simulator
- Python 3.8+ with python3-venv
- Docker
- Standard Linux utilities (make, wget, konsole)
- Jupyter Notebook (for TSM-NIDS analysis)
- TensorFlow/PyTorch (for machine learning models)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Siong23/iot-digital-twin.git
   cd iot-digital-twin
   ```

2. **Install Python dependencies**:
   ```bash
   cd AttackThreat
   pip install -r requirements.txt
   ```

3. **Set up TSM-NIDS environment** (for AI-powered intrusion detection):
   ```bash
   cd TSMixer
   # Install additional ML dependencies as needed for specific modules
   pip install tensorflow jupyter pandas numpy scikit-learn
   ```

4. **Set up GNS3 environment** with the required appliances (see [Dependencies](#-dependencies))

### Basic Usage

1. **Start the MQTT broker**:
   ```bash
   cd IoTDevice/MQTTScenarios
   python3 mqttbroker.py
   ```

2. **Run security assessments**:
   ```bash
   cd AttackThreat
   python3 exploit.py  # Automated scanning
   # or
   python3 exploit_interactive.py  # Interactive mode
   ```

3. **Use TSM-NIDS for intrusion detection**:
   ```bash
   cd TSMixer/AttackClassification
   jupyter notebook tsmixermulti-tonprocess_base_s.ipynb
   # or explore other TSM-NIDS modules
   ```

## 📋 Dependencies

### GNS3 Appliances
- [Cisco 7200 Router](https://www.gns3.com/marketplace/appliances/cisco-7200) - Network routing simulation
- [Kali Linux](https://gns3.com/marketplace/appliances/kali-linux-2) - Security testing platform
- [Fixed Open vSwitch](https://gitlab.com/Fumeaux/openvswitch) - Virtual switching
- Ubuntu Server - IoT device simulation
- Ubuntu Guest Additions - Enhanced VM functionality
- TightVNC - Remote access capabilities

### System Requirements
- **Virtualization**: KVM support enabled
- **RAM**: Minimum 8GB (16GB recommended for ML workloads)
- **Storage**: 50GB+ available space (additional space for datasets)
- **Network**: Internet connection for appliance downloads
- **GPU**: Optional but recommended for TSM-NIDS training (CUDA-compatible)

## 🔧 Configuration

### MQTT Broker Setup
Configure secure MQTT communication using client certificates. Follow the [detailed MQTT setup guide](https://medium.com/gravio-edge-iot-platform/how-to-set-up-a-mosquitto-mqtt-broker-securely-using-client-certificates-82b2aaaef9c8).

### Network Topology
Design your GNS3 topology to include:
- IoT devices (simulated using lightweight VMs)
- Network infrastructure (routers, switches)
- Security monitoring tools (Kali Linux)
- MQTT broker services

### TSM-NIDS Configuration
The TSMixer-based Network Intrusion Detection System provides:
- **Attack Classification**: Multi-class classification of IoT attack types
- **Attack Identification**: Binary detection of malicious network traffic
- **Digital Twin Analysis**: Real-world IoT data processing and analysis

Configure TSM-NIDS by:
1. Selecting appropriate preprocessing methods (MinMaxScaler, RobustScaler, StandardScaler)
2. Choosing feature selection techniques (correlation analysis, mutual information)
3. Applying data augmentation methods (SMOTE) if needed
4. Configuring model parameters in the respective Jupyter notebooks

## 📊 Datasets and Research

### Supported Datasets
- **TON-IoT Dataset**: Comprehensive IoT network traffic dataset for training and evaluation
- **Real-world IoT Data**: Captured data from actual IoT devices in controlled environments
- **Custom Dataset Collection**: Tools for capturing and analyzing your own IoT network data

### Research Applications
- **Intrusion Detection Systems**: Evaluate TSMixer effectiveness for IoT security
- **Attack Pattern Analysis**: Study temporal patterns in IoT attack sequences
- **Feature Engineering**: Explore optimal feature sets for IoT security classification
- **Model Comparison**: Compare different scaling and preprocessing approaches
- **Threat Intelligence**: Generate insights from real-world IoT attack data

## ⚠️ Security Notice

**⚠️ IMPORTANT**: This testbed is designed exclusively for educational and research purposes in controlled environments. Only use these tools on systems you own or have explicit permission to test. Unauthorized use of security testing tools is illegal and unethical.

## 🎓 Educational Use Cases

- **Cybersecurity Courses**: Hands-on IoT security training
- **Research Projects**: IoT vulnerability analysis and threat modeling
- **Security Workshops**: Practical penetration testing and defense
- **Digital Twin Concepts**: Understanding IoT system modeling and simulation
- **AI Security**: Machine learning applications in cybersecurity
- **Network Intrusion Detection**: Time series analysis for threat detection
- **Data Science**: Feature engineering and model evaluation for security datasets

## 📚 Documentation

For detailed setup instructions and advanced usage, refer to:
- [AttackThreat Framework Documentation](./AttackThreat/README.md)
- [TSM-NIDS Documentation](./TSMixer/readme.md)
- [MQTT Security Configuration Guide](https://medium.com/gravio-edge-iot-platform/how-to-set-up-a-mosquitto-mqtt-broker-securely-using-client-certificates-82b2aaaef9c8)
- [Project Documentation (Word)](https://view.officeapps.live.com/op/view.aspx?src=https%3A%2F%2Fraw.githubusercontent.com%2FSiong23%2Fiot-digital-twin%2Frefs%2Fheads%2Fmain%2FTwinningAgent%2FIoT%2520Digital%2520Twin%2520Documentation%2520.docx&wdOrigin=BROWSELINK) *(Work in Progress - View Only)*

### Key Features by Component

#### Agent Module
- MQTT broker management and secure communication
- IoT device simulation and data collection
- RTSP stream capture for video IoT devices
- Telemetry control and monitoring

#### AttackThreat Module
- Automated vulnerability scanning
- Interactive penetration testing
- Brute force attack simulation
- DDoS attack coordination
- Credential testing against IoT devices

#### TSM-NIDS Module
- Time series neural network intrusion detection
- Multi-class attack classification (DoS, DDoS, backdoor, injection, etc.)
- Binary attack identification
- Feature importance analysis and visualization
- Support for multiple preprocessing techniques
- Real-world IoT dataset analysis

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests for improvements.

## 📄 License

This project is intended for educational and research purposes. Please ensure compliance with your institution's policies and applicable laws when using this testbed.

## 📧 Contact

For questions or collaboration opportunities, please open an issue or contact the repository maintainer.

---

**Repository**: https://github.com/Siong23/iot-digital-twin
