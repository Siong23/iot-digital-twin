import sys
import psutil
import paho.mqtt.client as mqtt
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer
import pyqtgraph as pg

sensor_values = []

# MQTT setup
def on_message(client, userdata, msg):
    try:
        value = float(msg.payload.decode())
        sensor_values.append(value)
        if len(sensor_values) > 100:
            sensor_values.pop(0)
    except:
        pass

client = mqtt.Client()
client.connect("localhost", 1883)  # your digital broker
client.subscribe("digital/sensor/temp")
client.on_message = on_message
client.loop_start()

class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Twin Dashboard")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # Sensor Graph
        self.plot = pg.PlotWidget(title="Sensor Data")
        self.curve = self.plot.plot(pen='y')
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
        if sensor_values:
            self.curve.setData(sensor_values)

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
