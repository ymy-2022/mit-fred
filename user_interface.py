import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QGridLayout, QLabel, QPushButton, QLineEdit,
    QCheckBox, QSlider, QVBoxLayout, QHBoxLayout, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from database import Database
from fiber_camera import FiberCamera

class DiameterPlot(FigureCanvas):
    """Matplotlib plot for real-time diameter data."""
    def __init__(self, parent=None):
        self.fig = Figure(figsize=(5, 2.2))
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Diameter (mm)")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Diameter (mm)")
        self.line, = self.ax.plot([], [], lw=2, label="Diameter")
        self.setpoint_line, = self.ax.plot([], [], lw=2, color='r', label='Setpoint')
        self.ax.legend()
        self.x_data = []
        self.y_data = []
        self.setpoint_data = []

    def update_plot(self, x, y, setpoint):
        self.x_data.append(x)
        self.y_data.append(y)
        self.setpoint_data.append(setpoint)
        self.line.set_data(self.x_data, self.y_data)
        self.setpoint_line.set_data(self.x_data, self.setpoint_data)
        self.ax.relim()
        self.ax.autoscale_view()
        self.draw()

class UserInterface(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fiber Diameter System")
        self.setGeometry(100, 100, 1600, 900)
        self.setFixedSize(1600, 900)
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # ----------- 左上角按钮和输入框区 -----------
        self.calibrate_camera_btn = QPushButton("Calibrate Camera")
        self.calibration_wire_input = QLineEdit()
        self.calibration_wire_input.setPlaceholderText("Calibration wire D (mm)")
        self.calibration_wire_input.setFixedWidth(120)
        self.start_motor_btn = QPushButton("Start Motor")
        top_left_row = QHBoxLayout()
        top_left_row.addWidget(self.calibrate_camera_btn)
        top_left_row.addWidget(self.calibration_wire_input)
        top_left_row.addWidget(self.start_motor_btn)
        self.layout.addLayout(top_left_row, 0, 0, 1, 2)

        # ----------- Diameter Plot 和视频显示 -----------
        self.diameter_plot = DiameterPlot()
        self.layout.addWidget(self.diameter_plot, 1, 0, 1, 2)

        self.raw_image = QLabel("Original Video")
        self.raw_image.setFixedSize(480, 320)
        self.raw_image.setStyleSheet("background-color: #222; color: white;")
        self.raw_image.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.raw_image, 2, 0)

        self.processed_image = QLabel("Fully Processed Video")
        self.processed_image.setFixedSize(480, 320)
        self.processed_image.setStyleSheet("background-color: #222; color: white;")
        self.processed_image.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.processed_image, 3, 0)

        # ----------- 右侧参数区（全局定义控件） -----------
        right_panel = QVBoxLayout()
        # Erode
        self.erode_checkbox = QCheckBox("Erode")
        right_panel.addWidget(self.erode_checkbox)
        right_panel.addWidget(QLabel("腐蚀操作，去除细小噪点，使主线条更突出"))
        # Dilate
        self.dilate_checkbox = QCheckBox("Dilate")
        right_panel.addWidget(self.dilate_checkbox)
        right_panel.addWidget(QLabel("膨胀操作，增强主线条，连接断裂部分"))
        # Gaussian Blur
        self.blur_checkbox = QCheckBox("Gaussian Blur")
        right_panel.addWidget(self.blur_checkbox)
        right_panel.addWidget(QLabel("高斯模糊，平滑图像，减少噪声影响"))
        # Binary
        self.binary_checkbox = QCheckBox("Binary")
        right_panel.addWidget(self.binary_checkbox)
        right_panel.addWidget(QLabel("二值化，将图像转为黑白，突出目标区域"))

        right_panel.addSpacing(10)
        # Canny lower threshold
        self.canny_lower_slider = QSlider(Qt.Horizontal)
        self.canny_lower_slider.setRange(0, 150)
        self.canny_lower_slider.setSingleStep(5)
        self.canny_lower_slider.setTickInterval(5)
        self.canny_lower_slider.setValue(50)
        right_panel.addWidget(QLabel("Canny低阈值 (0-150, 步长5)"))
        right_panel.addWidget(self.canny_lower_slider)
        right_panel.addWidget(QLabel("调节边缘检测灵敏度，越低越敏感"))
        # Canny higher threshold
        self.canny_higher_slider = QSlider(Qt.Horizontal)
        self.canny_higher_slider.setRange(150, 300)
        self.canny_higher_slider.setSingleStep(5)
        self.canny_higher_slider.setTickInterval(5)
        self.canny_higher_slider.setValue(200)
        right_panel.addWidget(QLabel("Canny高阈值 (150-300, 步长5)"))
        right_panel.addWidget(self.canny_higher_slider)
        right_panel.addWidget(QLabel("调节边缘检测强度，越高越严格"))
        # Hough threshold
        self.hough_threshold_slider = QSlider(Qt.Horizontal)
        self.hough_threshold_slider.setRange(10, 100)
        self.hough_threshold_slider.setSingleStep(5)
        self.hough_threshold_slider.setTickInterval(5)
        self.hough_threshold_slider.setValue(30)
        right_panel.addWidget(QLabel("Hough阈值 (10-100, 步长5)"))
        right_panel.addWidget(self.hough_threshold_slider)
        right_panel.addWidget(QLabel("调节直线检测严格程度，越低越容易检测出线"))

        self.layout.addLayout(right_panel, 1, 2, 4, 1)

        # ----------- 目标直径输入（用于标定和目标曲线） -----------
        self.target_diameter = QDoubleSpinBox()
        self.target_diameter.setMinimum(0.3)
        self.target_diameter.setMaximum(1.5)
        self.target_diameter.setValue(1.0)
        self.target_diameter.setSingleStep(0.01)
        self.target_diameter.setDecimals(3)
        self.layout.addWidget(QLabel("Target Diameter (mm)"), 4, 0)
        self.layout.addWidget(self.target_diameter, 4, 1)

        # ----------- FiberCamera实例，控件引用传递 -----------
        self.fiber_camera = FiberCamera(self.target_diameter, self)
        self.calibrate_camera_btn.clicked.connect(self.calibrate_camera)
        self.start_motor_btn.clicked.connect(self.start_motor_sequence)

        # 定时刷新
        self.timer = QTimer()
        self.timer.timeout.connect(self.fiber_camera.camera_loop)
        self.timer.start(100)

    def calibrate_camera(self):
        try:
            real_diameter_mm = float(self.calibration_wire_input.text())
            self.fiber_camera.calibration_wire_diameter = real_diameter_mm
        except Exception:
            self.fiber_camera.calibration_wire_diameter = None
        self.fiber_camera.calibrate()

    def start_motor_sequence(self):
        """Start motor, extruder, fan, and heater at required settings."""
        self.dc_motor_pwm.setValue(30)
        self.extrusion_motor_speed.setValue(0.6)
        self.fan_duty_cycle.setValue(100)
        self.target_temperature.setValue(95)
        self.dc_motor_open_loop_enabled = True
        self.device_started = True
        self.show_message("Start Motor", "Motor started at 30% PWM, fan at 100%, heater at 95°C, extruder at normal speed.")

    def start_gui(self) -> None:
        timer = QTimer()
        timer.timeout.connect(self.fiber_camera.camera_loop)
        timer.start(200)
        self.window.show()
        self.app.exec_()

    def show_message(self, title: str, message: str) -> None:
        QMessageBox.information(self.app.activeWindow(), title, message)

    def update_temperature_slider_label(self, value) -> None:
        self.target_temperature_label.setText(f"Temperature: {value} C")

    def update_fan_slider_label(self, value) -> None:
        self.fan_duty_cycle_label.setText(f"Fan Duty Cycle: {value} %")

    class Plot(FigureCanvas):
        """Base class for plots"""
        def __init__(self, title: str, y_label: str) -> None:
            self.figure = Figure()
            self.axes = self.figure.add_subplot(111)
            super(UserInterface.Plot, self).__init__(self.figure)
            self.axes.set_title(title)
            self.axes.set_xlabel("Time (s)")
            self.axes.set_ylabel(y_label)
            self.progress_line, = self.axes.plot([], [], lw=2, label=title)
            self.setpoint_line, = self.axes.plot([], [], lw=2, color='r', label=f'Target {title}')
            self.axes.legend()
            self.x_data = []
            self.y_data = []
            self.setpoint_data = []

        def update_plot(self, x: float, y: float, setpoint: float) -> None:
            self.x_data.append(x)
            self.y_data.append(y)
            self.setpoint_data.append(setpoint)
            self.progress_line.set_label(f"{self.axes.get_title()}: {y:.2f}")
            self.axes.legend()
            self.progress_line.set_data(self.x_data, self.y_data)
            self.setpoint_line.set_data(self.x_data, self.setpoint_data)
            self.axes.relim()
            self.axes.autoscale_view()
            self.draw()
