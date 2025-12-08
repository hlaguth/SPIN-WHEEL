import math
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QSlider, QWidget, QFrame)
from PySide6.QtGui import QPainter, QBrush, QPen, QColor, QPixmap, QFont
from PySide6.QtCore import Qt, QRectF, QPointF

class ImageCalibrationDialog(QDialog):
    def __init__(self, parent=None, items=None, image_path="", angle_offset=0, scale=1.0):
        super().__init__(parent)
        self.setWindowTitle("圖片修正")
        self.resize(500, 650)
        
        self.items = items or []
        self.image_path = image_path
        self.angle_offset = angle_offset
        self.scale = scale
        self.pixmap = None
        if self.image_path:
            self.pixmap = QPixmap(self.image_path)
            
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Preview Area
        self.preview_widget = CalibrationPreview(self)
        layout.addWidget(self.preview_widget)
        
        # Controls
        controls_layout = QVBoxLayout()
        
        # Angle Control
        angle_layout = QHBoxLayout()
        angle_layout.addWidget(QLabel("角度:"))
        self.angle_slider = QSlider(Qt.Horizontal)
        self.angle_slider.setRange(0, 360)
        self.angle_slider.setValue(self.angle_offset)
        self.angle_slider.valueChanged.connect(self.on_angle_changed)
        angle_layout.addWidget(self.angle_slider)
        self.angle_val_label = QLabel(f"{self.angle_offset}°")
        self.angle_val_label.setFixedWidth(40)
        angle_layout.addWidget(self.angle_val_label)
        controls_layout.addLayout(angle_layout)
        
        # Scale Control
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("大小:"))
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(10, 200) # 0.1 to 2.0
        self.scale_slider.setValue(int(self.scale * 100))
        self.scale_slider.valueChanged.connect(self.on_scale_changed)
        scale_layout.addWidget(self.scale_slider)
        self.scale_val_label = QLabel(f"{self.scale:.2f}x")
        self.scale_val_label.setFixedWidth(40)
        scale_layout.addWidget(self.scale_val_label)
        controls_layout.addLayout(scale_layout)
        
        layout.addLayout(controls_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("確定")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def on_angle_changed(self, value):
        self.angle_offset = value
        self.angle_val_label.setText(f"{value}°")
        self.preview_widget.update()
        
    def on_scale_changed(self, value):
        self.scale = value / 100.0
        self.scale_val_label.setText(f"{self.scale:.2f}x")
        self.preview_widget.update()
        
    def get_result(self):
        return self.angle_offset, self.scale

class CalibrationPreview(QWidget):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.setMinimumHeight(400)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        w = min(rect.width(), rect.height()) - 40
        radius = w / 2
        center = rect.center()
        
        # Draw Wheel Background (Static, simplified)
        total_weight = sum(item['weight'] for item in self.dialog.items)
        if total_weight > 0:
            start_angle = 0 # Fixed at 0 for calibration
            for item in self.dialog.items:
                span_angle = (item['weight'] / total_weight) * 360
                
                painter.setBrush(QBrush(item['color']))
                painter.setPen(Qt.NoPen)
                painter.drawPie(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                                int(start_angle * 16), int(span_angle * 16))
                
                # Draw text (simplified)
                mid_angle = start_angle + span_angle / 2
                painter.save()
                painter.translate(center)
                painter.rotate(-mid_angle)
                if item['color'].lightness() < 128:
                    painter.setPen(Qt.white)
                else:
                    painter.setPen(Qt.black)
                painter.setFont(QFont("Microsoft JhengHei", 10, QFont.Bold))
                painter.drawText(QRectF(radius * 0.4, -10, radius * 0.5, 20), Qt.AlignLeft, item['name'])
                painter.restore()
                
                start_angle += span_angle
        
        # Draw Reference Line (Red Line at 12 o'clock / 0 degrees)
        # 0 degree in our logic is 3 o'clock in Qt?
        # No, in our logic 0 degree usually points East (Qt default).
        # We want "Top" to be the reference. Top is 90 degrees (CCW from East) or 270 degrees (CW)?
        # Qt 0 is East. Top is 90 CCW.
        # But wait, our wheel logic usually aligns 0 with... where?
        # Let's draw a vertical line UP.
        
        painter.setPen(QPen(Qt.red, 3, Qt.DashLine))
        painter.drawLine(center, QPointF(center.x(), center.y() - radius - 10))
        
        painter.setPen(QPen(Qt.red, 1))
        painter.drawText(QRectF(center.x() - 50, center.y() - radius - 30, 100, 20), Qt.AlignCenter, "基準線 (0°)")

        # Draw Image Pointer
        if self.dialog.pixmap:
            painter.save()
            painter.translate(center)
            
            # Rotation:
            # We want to show how the image looks when "wheel rotation" is 0.
            # In `wheel_window.py`:
            # final_rotate = -self._rotation_angle - self.pointer_angle_offset
            # faster mode: wheel rotates by -angle. 
            # If self._rotation_angle is 0 (static wheel), rotation is -offset.
            
            # Wait, if I align image to Top, then offset should be what makes it point Top.
            # If image points right (0 deg), and I want it to point Top (90 deg), I need rotation +90?
            # Or -90?
            # Let's just use the same logic as `wheel_window.py` but with rotation=0.
            # Actually, `wheel_window` logic:
            # `pointer_angle = (self._rotation_angle + self.pointer_angle_offset) % 360`
            # `painter.rotate(-self._rotation_angle - self.pointer_angle_offset)`
            
            # If I want to align to "Reference Line" (which typically represents the winner selection point).
            # Usually verification is: Does the pointer point to the winning sector?
            # The winning sector detection uses `effective_angle = (angle + self.pointer_angle_offset) % 360`.
            # So if angle=0 (wheel start), pointer points to `offset`.
            # If I want pointer to point to Top (let's say Top is 90 deg in standard math), then `offset` should be 90.
            
            # Visual Feedback:
            # Draw the image rotated by `offset`. 
            # Whatever `offset` is set, we draw it.
            # Users will rotate it until it physically aligns with the Red Line.
            # So we just rotate by `-offset` (because Qt rotates Clockwise for positive? No, wait).
            
            # In `wheel_window`: `painter.rotate(-rotation_angle - offset)`.
            # Here rotation_angle is 0. So `painter.rotate(-offset)`.
            
            # But wait, if `offset` increases (0 -> 90), `effective_angle` increases (CCW).
            # `painter.rotate(-offset)` rotates CCW (if offset is positive).
            # Wait, `painter.rotate(angle)`: "Rotates the coordinate system the given angle *clockwise*."
            # So `painter.rotate(-offset)` rotates CCW.
            # Correct.
            
            # Unified Visual Rotation matching WheelWindow
            # WheelWindow uses: rotate(-effective) + rotate(90)
            # effective = 90 + offset (at 0 angle)
            # rotate(-(90+offset)) + rotate(90) = rotate(-90 - offset + 90) = rotate(-offset)
            painter.rotate(-self.dialog.angle_offset)
            
            target_h = radius * 1.0 * self.dialog.scale
            target_w = target_h * (self.dialog.pixmap.width() / self.dialog.pixmap.height())
            
            painter.drawPixmap(QRectF(-target_w/2, -target_h/2, target_w, target_h), 
                               self.dialog.pixmap, self.dialog.pixmap.rect())
            
            painter.restore()
