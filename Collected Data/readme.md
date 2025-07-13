# IoT Network Digital Twin Dataset

## Overview

This dataset contains network traffic data captured from a digital twin testbed of an IoT network, designed to simulate realistic smart environment scenarios with both normal IoT behavior and various cyber attack patterns. The testbed emulates real-world IoT communication patterns and security threats, making it valuable for cybersecurity research and intrusion detection system development.

## Dataset Information

- **Name**: IoT Network Digital Twin – Normal and Attack Traffic
- **Kaggle Link**: [https://www.kaggle.com/datasets/iffathanafiah/iotdigitaltwin/data](https://www.kaggle.com/datasets/iffathanafiah/iotdigitaltwin/data)
- **Total Duration**: Approximately 6 hours
- **Normal Traffic**: 3 hours
- **Attack Traffic**: 3+ hours

## Testbed Architecture

The digital twin setup consists of:

### IoT Devices
- **Digital IP Camera**: Modeled after physical IP cameras, streaming video data
- **Digital Temperature-Humidity Sensor**: Simulating environmental monitoring devices

### Infrastructure
- **Digital IoT Broker Server**: Central communication hub for all IoT devices
- **Network Infrastructure**: Realistic network topology with typical IoT communication patterns

## Data Capture Methodology

### Tools Used
- **Packet Capture**: Wireshark
- **Feature Extraction**: Zeek (formerly Bro)
- **Protocol Analysis**: Network-level and application-level logging

### Protocols Captured
- MQTT (IoT messaging)
- RTSP (Real-Time Streaming Protocol)
- TCP/UDP (Transport layer)
- ICMP (Network layer)
- Other IoT-specific and attack-related protocols

## Traffic Categories

### Normal Traffic (3 hours)

Normal behavior was captured across three distinct time periods to reflect realistic diurnal activity patterns:

1. **Morning Period** (1 hour)
   - Typical morning IoT device activity
   - Sensor data collection and transmission
   - Camera streaming patterns

2. **Evening Period** (1 hour)
   - Increased device activity
   - Higher data transmission rates
   - Enhanced monitoring patterns

3. **Night Period** (1 hour)
   - Reduced activity patterns
   - Periodic sensor updates
   - Minimal camera streaming

### Attack Traffic (3+ hours)

Multiple attack scenarios were executed to create a comprehensive threat landscape:

#### 1. DDoS Attacks (1 hour total)
- **Tool**: hping3
- **Attack Types**: ICMP, TCP, UDP packet floods
- **Pattern**: Multiple short bursts (2-6 minutes each)
- **Total Duration**: ~62 minutes of active attack traffic

#### 2. Password Brute-Force Attacks (1 hour total)
- **Duration**: 30 minutes evening + 30 minutes night
- **Tools**: Custom Python scripts with predefined dictionaries
- **Targets**: Login services on exposed IoT devices
- **Methodology**: Dictionary-based credential attacks

#### 3. Scanning Attacks
- **Nessus Vulnerability Scan**: Complete vulnerability assessment
- **Nmap Scanning**: 3 iterations with various flags
  - `-sV` (Service Version scan)
  - `-O` (OSes scan)
  - `-T5` (Faster timing)

#### 4. MQTT-Based Attacks (3 runs)
- **Tool**: MQTTSA (MQTT Security Analysis)
- **Targets**: MQTT broker vulnerabilities
- **Attack Types**: 
  - Malformed payload injection
  - Malicious message publishing
  - Broker exploitation attempts
  - Subscriber weakness exploitation

#### 5. RTSP-Based Attacks (3 runs)
- **Tool**: Cameradar
- **Targets**: Camera RTSP streams
- **Attack Types**:
  - Unauthorized access attempts
  - Stream enumeration
  - Credential brute-forcing
  - RTSP protocol exploitation

## Use Cases

This dataset is designed for:

### Research Applications
- **Intrusion Detection Systems (IDS)** training and evaluation
- **Anomaly Detection Models** development
- **Network Behavior Analysis** research
- **IoT Security** assessment and improvement
- **Digital Twin Cybersecurity** research

### Machine Learning Applications
- Binary classification (normal vs. attack)
- Multi-class attack type classification
- Time-series anomaly detection
- Feature importance analysis for IoT security

### Educational Purposes
- Cybersecurity training and education
- IoT network security demonstrations
- Attack pattern analysis tutorials
- Digital twin security concepts

## Dataset Structure

The dataset includes:
- Extracted features (CSV format)
- Protocol-specific logs
- Timestamp information for temporal analysis
- Attack labels and classifications

## Key Features

- **Realistic IoT Environment**: Based on actual IoT device behaviors
- **Temporal Patterns**: Captures diurnal variations in IoT activity
- **Comprehensive Attack Coverage**: Multiple attack vectors and techniques
- **High-Quality Labels**: Precise attack timing and classification
- **Protocol Diversity**: Multiple IoT and network protocols represented

---

*This dataset represents a comprehensive collection of IoT network traffic for cybersecurity research, captured from a realistic digital twin environment designed to advance IoT security research and education.*