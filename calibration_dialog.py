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
        
        # 預覽區域
        self.preview_widget = CalibrationPreview(self)
        layout.addWidget(self.preview_widget)
        
        # 控制項
        controls_layout = QVBoxLayout()
        
        # 角度控制
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
        
        # 大小控制
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
        
        # 按鈕
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
        
        # 繪製轉盤背景（靜態，簡化版）
        total_weight = sum(item['weight'] for item in self.dialog.items)
        if total_weight > 0:
            start_angle = 0 # 修正時固定為 0
            for item in self.dialog.items:
                span_angle = (item['weight'] / total_weight) * 360
                
                painter.setBrush(QBrush(item['color']))
                painter.setPen(Qt.NoPen)
                painter.drawPie(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                                int(start_angle * 16), int(span_angle * 16))
                
                # 繪製文字（簡化版）
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
        
        # 繪製基準線（12 點鐘方向 / 0 度紅線）
        # 在我們的邏輯中，0 度通常指向東方（Qt 預設）。
        # 我們希望以「上方」為基準。上方是逆時針 90 度或順時針 270 度。
        # Qt 的 0 度是東方。上方是逆時針 90 度。
        # 這裡我們直接向上畫一條垂直線。
        
        painter.setPen(QPen(Qt.red, 3, Qt.DashLine))
        painter.drawLine(center, QPointF(center.x(), center.y() - radius - 10))
        
        painter.setPen(QPen(Qt.red, 1))
        painter.drawText(QRectF(center.x() - 50, center.y() - radius - 30, 100, 20), Qt.AlignCenter, "基準線 (0°)")

        # 繪製圖片指針
        if self.dialog.pixmap:
            painter.save()
            painter.translate(center)
            
            # 旋轉：
            # 我們想顯示當「轉盤旋轉角度」為 0 時圖片的樣子。
            # 在 `wheel_window.py` 中：
            # final_rotate = -self._rotation_angle - self.pointer_angle_offset
            # 快速模式：轉盤旋轉 -angle。
            # 如果 self._rotation_angle 為 0（靜態轉盤），旋轉即為 -offset。
            
            # 統一的視覺旋轉邏輯，與 WheelWindow 匹配
            # WheelWindow 使用：rotate(-effective) + rotate(90)
            # effective = 90 + offset (當角度為 0 時)
            # rotate(-(90+offset)) + rotate(90) = rotate(-90 - offset + 90) = rotate(-offset)
            painter.rotate(-self.dialog.angle_offset)
            
            target_h = radius * 1.0 * self.dialog.scale
            target_w = target_h * (self.dialog.pixmap.width() / self.dialog.pixmap.height())
            
            painter.drawPixmap(QRectF(-target_w/2, -target_h/2, target_w, target_h), 
                               self.dialog.pixmap, self.dialog.pixmap.rect())
            
            painter.restore()
