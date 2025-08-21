import sys
import json
import psutil
import paho.mqtt.client as mqtt
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

# Buffers for sensor values
temperature_values = []
humidity_values = []

# MQTT setup
def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)  # parse JSON
        if "temperature" in data:
            temperature_values.append(float(data["temperature"]))
            if len(temperature_values) > 100:
                temperature_values.pop(0)
        if "humidity" in data:
            humidity_values.append(float(data["humidity"]))
            if len(humidity_values) > 100:
                humidity_values.pop(0)
    except Exception as e:
        print("Error parsing MQTT message:", e)

client = mqtt.Client()
client.username_pw_set("admin", "admin123")   # credentials
client.connect("192.168.20.2", 1883)          # digital broker
client.subscribe("sensors/digital/data")      # topic
client.on_message = on_message
client.loop_start()

class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Twin Dashboard")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # Sensor Graph
        self.plot = pg.PlotWidget(title="Temperature & Humidity")
        self.temp_curve = self.plot.plot(pen='r', name="Temperature")
        self.hum_curve = self.plot.plot(pen='b', name="Humidity")
        layout.addWidget(self.plot)

        # Device Status
        self.status_label = QLabel("Device Status: Initializing...")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        # Timer to update graph + status
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # update every 1s

    def update_dashboard(self):
        # Update sensor graph
        if temperature_values:
            self.temp_curve.setData(temperature_values)
        if humidity_values:
            self.hum_curve.setData(humidity_values)

        # Update system usage
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        self.status_label.setText(
            f"Router: UP | Broker: UP | Sensor: UP\nCPU: {cpu}% RAM: {ram}%"
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Dashboard()
    window.show()
    sys.exit(app.exec_())
