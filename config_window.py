import random
import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QListWidget, QListWidgetItem, QColorDialog, QCheckBox, 
    QMessageBox, QDoubleSpinBox, QLabel, QGroupBox, QFormLayout,
    QInputDialog, QSlider, QFileDialog
)
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen, QCursor
from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QSize
from collections import Counter
from wheel_window import WheelWindow
from utils import resource_path

SETTINGS_FILE = resource_path("settings.json")

class ProbabilityBar(QWidget):
    """機率條元件，顯示各選項的權重比例"""
    weights_changed = Signal()

    def __init__(self, parent=None):
        super().__init__()
        self.items = []
        self.drag_index = -1
        self.setMinimumHeight(40)
        self.setMaximumHeight(60)
        self.setCursor(Qt.ArrowCursor)

    def paintEvent(self, event):
        """繪製機率條"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        total_weight = sum(item['weight'] for item in self.items)
        if total_weight <= 0:
            return

        current_x = 0.0
        width = rect.width()
        
        for i, item in enumerate(self.items):
            segment_width = (item['weight'] / total_weight) * width
            
            painter.setBrush(QBrush(item['color']))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(current_x, 0, segment_width, rect.height()))
            
            if i < len(self.items) - 1:
                painter.setPen(QPen(Qt.white, 2))
                painter.drawLine(current_x + segment_width, 0, current_x + segment_width, rect.height())
                
            current_x += segment_width

    def mousePressEvent(self, event):
        """滑鼠按下事件"""
        if event.button() == Qt.LeftButton:
            self.drag_index = self.get_separator_index(event.position().x())

    def mouseMoveEvent(self, event):
        """滑鼠移動事件"""
        rect = self.rect()
        width = rect.width()
        
        if self.get_separator_index(event.position().x()) != -1 or self.drag_index != -1:
            self.setCursor(Qt.SplitHCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if self.drag_index != -1 and self.items:
            total_weight = sum(item['weight'] for item in self.items)
            
            current_cum_weight = sum(self.items[k]['weight'] for k in range(self.drag_index + 1))
            current_x_pos = (current_cum_weight / total_weight) * width
            
            delta_x = event.position().x() - current_x_pos
            delta_weight = (delta_x / width) * total_weight
            
            current_item = self.items[self.drag_index]
            next_item = self.items[self.drag_index + 1]
            
            new_w1 = current_item['weight'] + delta_weight
            new_w2 = next_item['weight'] - delta_weight
            
            min_weight = total_weight * 0.005
            
            if new_w1 >= min_weight and new_w2 >= min_weight:
                current_item['weight'] = new_w1
                next_item['weight'] = new_w2
                self.weights_changed.emit()
                self.update()

    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件"""
        self.drag_index = -1
        self.setCursor(Qt.ArrowCursor)

    def get_separator_index(self, x):
        """取得分隔線索引"""
        if not self.items:
            return -1
        
        rect = self.rect()
        width = rect.width()
        total_weight = sum(item['weight'] for item in self.items)
        if total_weight <= 0:
            return -1
        
        current_x = 0
        threshold = 10
        
        for i in range(len(self.items) - 1):
            segment_width = (self.items[i]['weight'] / total_weight) * width
            current_x += segment_width
            
            if abs(x - current_x) <= threshold:
                return i
        return -1

class ItemWidget(QWidget):
    """選項列表項目元件"""
    toggled = Signal(bool)
    
    def __init__(self, name, weight, color, prob, enabled):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        
        self.color_lbl = QLabel()
        self.color_lbl.setFixedSize(20, 20)
        self.color_lbl.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #555;")
        layout.addWidget(self.color_lbl)
        
        text = f"{name} (W: {weight:.1f} | P: {prob:.1f}%)"
        self.info_lbl = QLabel(text)
        self.info_lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.info_lbl)
        
        layout.addStretch()
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(enabled)
        self.checkbox.toggled.connect(self.on_toggled)
        self.checkbox.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
        layout.addWidget(self.checkbox)
        
        self.setLayout(layout)
        
    def on_toggled(self, checked):
        """核取方塊切換事件"""
        self.toggled.emit(checked)

class ConfigWindow(QWidget):
    """設定視窗主類別"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("轉盤設定")
        self.resize(600, 700)
        self.setMinimumWidth(600)
        self.setStyleSheet("""
            QWidget {
                font-family: "Microsoft JhengHei", sans-serif;
                font-size: 14px;
            }
            QPushButton {
                background-color: #4CAF50; 
                color: white; 
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton#remove_btn {
                background-color: #f44336;
            }
            QPushButton#remove_btn:hover {
                background-color: #d32f2f;
            }
            QPushButton#move_btn {
                background-color: #FF9800;
            }
            QPushButton#move_btn:hover {
                background-color: #F57C00;
            }
            QPushButton#wheel_btn {
                background-color: #2196F3;
                font-size: 16px;
                padding: 12px;
            }
            QPushButton#test_btn {
                background-color: #9C27B0;
            }
            QPushButton#test_btn:hover {
                background-color: #7B1FA2;
            }
            QLineEdit, QDoubleSpinBox {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f9f9f9;
            }
            QListWidget::item {
                border-bottom: 1px solid #eee;
                padding: 0px; 
            }
        """)
        
        self.items = []
        self.wheel_window = None
        self.editing_index = -1
        
        self.history_data = []
        self.history_grouped = True
        self.panel_expanded = False
        self.history_panel_width = 300
        
        self.auto_spin_count = 0
        self.is_auto_spinning = False
        self.auto_spin_speed = 3.0
        
        self.result_text_color = QColor(255, 255, 255)
        self.border_enabled = True
        self.border_color = QColor(255, 255, 255)
        self.sound_enabled = False
        self.finish_sound_enabled = False
        self.result_opacity = 150
        self.pre_expand_width = 600
        
        self.init_ui()
        self.load_last_settings()
        
    def init_ui(self):
        """初始化使用者介面"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        input_group = QGroupBox("新增/編輯選項")
        input_layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("輸入選項名稱")
        input_layout.addRow("名稱:", self.name_input)
        
        weight_layout = QHBoxLayout()
        self.weight_input = QDoubleSpinBox()
        self.weight_input.setRange(0.1, 10000.0)
        self.weight_input.setDecimals(1)
        self.weight_input.setValue(1.0)
        self.weight_input.setSingleStep(0.5)
        weight_layout.addWidget(self.weight_input)
        
        self.color_btn = QPushButton("選擇顏色")
        self.color_btn.clicked.connect(self.choose_color)
        self.current_color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        self.update_color_btn()
        weight_layout.addWidget(self.color_btn)
        
        input_layout.addRow("權重 & 顏色:", weight_layout)
        
        self.add_btn = QPushButton("新增至列表")
        self.add_btn.clicked.connect(self.add_or_update_item)
        input_layout.addRow(self.add_btn)
        
        self.cancel_edit_btn = QPushButton("取消編輯")
        self.cancel_edit_btn.clicked.connect(self.cancel_edit)
        self.cancel_edit_btn.setVisible(False)
        self.cancel_edit_btn.setStyleSheet("background-color: #9E9E9E;")
        input_layout.addRow(self.cancel_edit_btn)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        style_group = QGroupBox("轉盤樣式設定")
        style_layout = QFormLayout()
        
        self.result_color_btn = QPushButton("結果文字顏色")
        self.result_color_btn.clicked.connect(self.choose_result_color)
        self.update_result_color_btn()
        
        result_layout = QHBoxLayout()
        result_layout.addWidget(self.result_color_btn)
        
        result_layout.addSpacing(10)
        result_layout.addWidget(QLabel("背景透明度:"))
        
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setFixedWidth(100)
        self.opacity_slider.setValue(60)
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        self.opacity_slider.sliderReleased.connect(self.save_settings)
        
        self.opacity_label = QLabel("60%")
        
        result_layout.addWidget(self.opacity_slider)
        result_layout.addWidget(self.opacity_label)
        result_layout.addStretch()
        
        style_layout.addRow("結果顯示:", result_layout)
        
        border_layout = QHBoxLayout()
        self.border_check = QCheckBox("顯示邊框")
        self.border_check.setChecked(True)
        self.border_check.stateChanged.connect(self.update_wheel_settings)
        border_layout.addWidget(self.border_check)
        
        self.separator_check = QCheckBox("顯示分隔線")
        self.separator_check.setChecked(True)
        self.separator_check.stateChanged.connect(self.update_wheel_settings)
        border_layout.addWidget(self.separator_check)
        
        self.border_color_btn = QPushButton("邊框顏色")
        self.border_color_btn.clicked.connect(self.choose_border_color)
        self.update_border_color_btn()
        border_layout.addWidget(self.border_color_btn)
        
        style_layout.addRow("轉盤邊框:", border_layout)
        
        sound_multi_layout = QHBoxLayout()
        
        self.sound_check = QCheckBox("啟用音效 (Tick)")
        self.sound_check.setChecked(False)
        self.sound_check.stateChanged.connect(self.update_wheel_settings)
        sound_multi_layout.addWidget(self.sound_check)

        self.finish_sound_check = QCheckBox("啟用結束音效 (Finish)")
        self.finish_sound_check.setChecked(False)
        self.finish_sound_check.stateChanged.connect(self.update_wheel_settings)
        sound_multi_layout.addWidget(self.finish_sound_check)
        
        sound_multi_layout.addStretch()
        
        self.multi_spin_setup_btn = QPushButton("設定連抽")
        self.multi_spin_setup_btn.clicked.connect(self.show_multi_spin_dialog)
        self.multi_spin_setup_btn.setEnabled(False)
        self.multi_spin_setup_btn.setStyleSheet("background-color: #9E9E9E;")
        sound_multi_layout.addWidget(self.multi_spin_setup_btn)
        
        style_layout.addRow("音效:", sound_multi_layout)
        
        style_group.setLayout(style_layout)
        main_layout.addWidget(style_group)
        
        list_group = QGroupBox("選項列表 (雙擊編輯)")
        list_layout = QVBoxLayout()
        
        self.item_list = QListWidget()
        self.item_list.setSelectionMode(QListWidget.SingleSelection)
        self.item_list.setDragDropMode(QListWidget.InternalMove)
        self.item_list.itemDoubleClicked.connect(self.load_item_for_edit)
        self.item_list.model().rowsMoved.connect(self.on_list_reordered)
        list_layout.addWidget(self.item_list)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(5)
        
        self.move_up_btn = QPushButton("▲")
        self.move_up_btn.setToolTip("上移")
        self.move_up_btn.setFixedWidth(40)
        self.move_up_btn.setObjectName("move_btn")
        self.move_up_btn.clicked.connect(self.move_item_up)
        btn_layout.addWidget(self.move_up_btn)
        
        self.move_down_btn = QPushButton("▼")
        self.move_down_btn.setToolTip("下移")
        self.move_down_btn.setFixedWidth(40)
        self.move_down_btn.setObjectName("move_btn")
        self.move_down_btn.clicked.connect(self.move_item_down)
        btn_layout.addWidget(self.move_down_btn)
        
        self.remove_btn = QPushButton("移除")
        self.remove_btn.setObjectName("remove_btn")
        self.remove_btn.clicked.connect(self.remove_item)
        btn_layout.addWidget(self.remove_btn)
        
        self.test_btn = QPushButton("手動")
        self.test_btn.setObjectName("test_btn")
        self.test_btn.clicked.connect(self.test_wheel)
        btn_layout.addWidget(self.test_btn)
        
        self.save_btn = QPushButton("儲存")
        self.save_btn.setObjectName("save_btn")
        self.save_btn.clicked.connect(self.save_items)
        btn_layout.addWidget(self.save_btn)
        
        self.load_btn = QPushButton("載入")
        self.load_btn.setObjectName("load_btn")
        self.load_btn.clicked.connect(self.load_items_dialog)
        btn_layout.addWidget(self.load_btn)
        
        list_layout.addLayout(btn_layout)
        
        list_group.setLayout(list_layout)
        main_layout.addWidget(list_group)
        
        self.open_wheel_btn = QPushButton("開啟轉盤")
        self.open_wheel_btn.setObjectName("wheel_btn")
        self.open_wheel_btn.clicked.connect(self.toggle_wheel)
        main_layout.addWidget(self.open_wheel_btn)
        
        left_widget = QWidget()
        left_widget.setLayout(main_layout)
        
        self.history_container = QWidget()
        self.history_container.setFixedWidth(0)
        self.history_container.setVisible(False)
        
        hist_layout = QVBoxLayout(self.history_container)
        hist_layout.setContentsMargins(10, 10, 10, 10)
        
        hist_title = QLabel("轉動紀錄")
        hist_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        hist_layout.addWidget(hist_title)
        
        self.history_memo = QLineEdit()
        self.history_memo.setPlaceholderText("備註 (清空時移除)")
        hist_layout.addWidget(self.history_memo)
        
        self.hist_view_btn = QPushButton("切換：合併顯示")
        self.hist_view_btn.clicked.connect(self.toggle_history_view)
        hist_layout.addWidget(self.hist_view_btn)
        
        self.history_list = QListWidget()
        hist_layout.addWidget(self.history_list)
        
        hist_clear_btn = QPushButton("清空紀錄")
        hist_clear_btn.setStyleSheet("background-color: #d32f2f;")
        hist_clear_btn.clicked.connect(self.clear_history)
        hist_layout.addWidget(hist_clear_btn)
        
        outer_layout = QHBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        outer_layout.addWidget(left_widget)
        
        btn_strip = QWidget()
        btn_strip.setFixedWidth(30)
        strip_layout = QVBoxLayout(btn_strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.addStretch()
        
        self.expand_btn = QPushButton("▶")
        self.expand_btn.setFixedSize(30, 60)
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background-color: #eee;
                border: 1px solid #ccc;
                border-top-left-radius: 10px;
                border-bottom-left-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ddd;
            }
        """)
        self.expand_btn.clicked.connect(self.toggle_history_panel)
        strip_layout.addWidget(self.expand_btn)
        strip_layout.addStretch()
        
        outer_layout.addWidget(btn_strip)
        outer_layout.addWidget(self.history_container)
        
        self.setLayout(outer_layout)

    def toggle_history_panel(self):
        """切換歷史紀錄面板"""
        if self.panel_expanded:
            self.panel_expanded = False
            self.history_container.setVisible(False)
            self.history_container.setFixedWidth(0)
            self.expand_btn.setText("▶")
            target_width = self.pre_expand_width
            if target_width < 600:
                target_width = 600
            
            self.layout().activate()
            self.resize(target_width, self.height())
        else:
            self.pre_expand_width = self.width()
            self.panel_expanded = True
            self.history_container.setVisible(True)
            self.history_container.setFixedWidth(self.history_panel_width)
            self.expand_btn.setText("◀")
            self.resize(self.width() + self.history_panel_width, self.height())
            self.update_history_list()
            
    def add_history_record(self, winner_name):
        """新增歷史紀錄"""
        self.history_data.append(winner_name)
        if self.panel_expanded:
            self.update_history_list()
            
        if self.is_auto_spinning and self.auto_spin_count > 0:
            self.auto_spin_count -= 1
            if self.auto_spin_count > 0:
                QTimer.singleShot(500, self.trigger_auto_spin)
            else:
                self.is_auto_spinning = False
                self.multi_spin_setup_btn.setText("設定連抽")
                self.multi_spin_setup_btn.setStyleSheet("background-color: #673AB7;")
                QMessageBox.information(self, "完成", "多連抽已完成！")

    def show_multi_spin_dialog(self):
        """顯示多連抽設定對話框"""
        if self.is_auto_spinning:
            self.is_auto_spinning = False
            self.multi_spin_setup_btn.setText("設定連抽")
            self.multi_spin_setup_btn.setStyleSheet("background-color: #673AB7;")
            return

        from PySide6.QtWidgets import QInputDialog
        
        speed, ok = QInputDialog.getDouble(self, "多連抽設定", "速度倍率 (原本的幾倍?):", 3.0, 1.0, 10.0, 1)
        if not ok:
            return
        
        count, ok = QInputDialog.getInt(self, "多連抽設定", "連抽次數:", 10, 1, 1000)
        if not ok:
            return
        
        if self.wheel_window is None:
            self.toggle_wheel()
        else:
            self.wheel_window.show()
            self.wheel_window.raise_()
        
        self.auto_spin_count = count
        self.auto_spin_speed = speed
        self.is_auto_spinning = True
        
        self.multi_spin_setup_btn.setText("停止連抽")
        self.multi_spin_setup_btn.setStyleSheet("background-color: #d32f2f;")
        
        self.trigger_auto_spin()
        
    def trigger_auto_spin(self):
        """觸發自動旋轉"""
        if self.wheel_window and self.is_auto_spinning:
            self.wheel_window.auto_spin(self.auto_spin_speed)
        
    def update_history_list(self):
        """更新歷史紀錄列表"""
        self.history_list.clear()
        if not self.history_data:
            return
        
        if self.history_grouped:
            self.hist_view_btn.setText("切換：個別顯示")
            counts = Counter(self.history_data)
            for name, count in counts.most_common():
                item = QListWidgetItem(f"{name} x{count}")
                item.setTextAlignment(Qt.AlignCenter)
                self.history_list.addItem(item)
        else:
            self.hist_view_btn.setText("切換：合併顯示")
            for name in reversed(self.history_data):
                item = QListWidgetItem(name)
                item.setTextAlignment(Qt.AlignCenter)
                self.history_list.addItem(item)

    def toggle_history_view(self):
        """切換歷史紀錄顯示模式"""
        self.history_grouped = not self.history_grouped
        self.update_history_list()
        
    def clear_history(self):
        """清空歷史紀錄"""
        self.history_data = []
        self.history_memo.clear()
        self.update_history_list()

    def choose_result_color(self):
        """選擇結果文字顏色"""
        color = QColorDialog.getColor(self.result_text_color)
        if color.isValid():
            self.result_text_color = color
            self.update_result_color_btn()
            self.update_wheel_settings()
            
    def update_result_color_btn(self):
        """更新結果顏色按鈕樣式"""
        text_color = "black" if self.result_text_color.lightness() > 128 else "white"
        self.result_color_btn.setStyleSheet(f"background-color: {self.result_text_color.name()}; color: {text_color};")
    
    def choose_border_color(self):
        """選擇邊框顏色"""
        color = QColorDialog.getColor(self.border_color)
        if color.isValid():
            self.border_color = color
            self.update_border_color_btn()
            self.update_wheel_settings()

    def update_border_color_btn(self):
        """更新邊框顏色按鈕樣式"""
        text_color = "black" if self.border_color.lightness() > 128 else "white"
        self.border_color_btn.setStyleSheet(f"background-color: {self.border_color.name()}; color: {text_color};")
        
    def choose_color(self):
        """選擇選項顏色"""
        color = QColorDialog.getColor(self.current_color)
        if color.isValid():
            self.current_color = color
            self.update_color_btn()
            
    def update_color_btn(self):
        """更新顏色按鈕樣式"""
        text_color = "white" if self.current_color.lightness() < 128 else "black"
        self.color_btn.setStyleSheet(f"background-color: {self.current_color.name()}; color: {text_color};")
        self.color_btn.setText(f"顏色 ({self.current_color.name()})")

    def add_or_update_item(self):
        """新增或更新選項"""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "錯誤", "請輸入選項名稱")
            return
            
        weight = self.weight_input.value()
        color = self.current_color
        
        enabled = True
        
        if self.editing_index >= 0:
            enabled = self.items[self.editing_index].get('enabled', True)
            self.items[self.editing_index] = {'name': name, 'weight': weight, 'color': color, 'enabled': enabled}
            self.cancel_edit()
        else:
            self.items.append({'name': name, 'weight': weight, 'color': color, 'enabled': enabled})
            self.name_input.clear()
            self.name_input.setFocus()
            self.current_color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            self.update_color_btn()
        
        self.update_list()
        self.update_wheel()
        self.save_settings()
        
    def load_item_for_edit(self, list_item):
        """載入選項以進行編輯"""
        row = self.item_list.row(list_item)
        item = self.items[row]
        self.name_input.setText(item['name'])
        self.weight_input.setValue(float(item['weight']))
        self.current_color = item['color']
        self.update_color_btn()
        
        self.editing_index = row
        self.add_btn.setText("更新選項")
        self.cancel_edit_btn.setVisible(True)
        
    def cancel_edit(self):
        """取消編輯"""
        self.editing_index = -1
        self.add_btn.setText("新增至列表")
        self.cancel_edit_btn.setVisible(False)
        self.name_input.clear()
        self.current_color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        self.update_color_btn()

    def remove_item(self):
        """移除選項"""
        row = self.item_list.currentRow()
        if row >= 0:
            self.items.pop(row)
            self.update_list()
            self.update_wheel()
            if row == self.editing_index:
                self.cancel_edit()
        else:
            QMessageBox.information(self, "提示", "請先選擇要移除的項目")

    def move_item_up(self):
        """上移選項"""
        row = self.item_list.currentRow()
        if row > 0:
            self.items[row], self.items[row-1] = self.items[row-1], self.items[row]
            self.update_list()
            self.item_list.setCurrentRow(row-1)
            self.update_wheel()
            
    def move_item_down(self):
        """下移選項"""
        row = self.item_list.currentRow()
        if row >= 0 and row < len(self.items) - 1:
            self.items[row], self.items[row+1] = self.items[row+1], self.items[row]
            self.update_list()
            self.item_list.setCurrentRow(row+1)
            self.update_wheel()
            
    def test_wheel(self):
        """開啟測試轉盤"""
        active_items = [i for i in self.items if i.get('enabled', True)]
        if not active_items:
            QMessageBox.warning(self, "警告", "請先新增並啟用至少一個選項")
            return
            
        self.test_window = WheelWindow(edit_mode=True)
        self.test_window.setWindowTitle("拖曳可以改變占比")
        
        self.test_window.update_settings(
            active_items, 
            self.border_enabled_check(), 
            self.border_color, 
            self.result_text_color,
            self.separator_check.isChecked()
        )
        self.test_window.weights_changed.connect(self.on_weights_changed_from_wheel)
        self.test_window.show()

    def on_weights_changed_from_wheel(self):
        """從轉盤更新權重時的回調"""
        self.update_list()
        self.save_settings()

    def update_list(self):
        """更新選項列表"""
        self.item_list.clear()
        
        active_items = [i for i in self.items if i.get('enabled', True)]
        total_weight = sum(i['weight'] for i in active_items)
        
        for i, item in enumerate(self.items):
            list_item = QListWidgetItem()
            self.item_list.addItem(list_item)
            
            prob = 0
            if item.get('enabled', True) and total_weight > 0:
                prob = (item['weight'] / total_weight) * 100
                
            widget = ItemWidget(item['name'], item['weight'], item['color'], prob, item.get('enabled', True))
            widget.toggled.connect(lambda checked, idx=i: self.on_item_toggled(idx, checked))
            
            list_item.setSizeHint(widget.sizeHint())
            list_item.setData(Qt.UserRole, item)
            self.item_list.setItemWidget(list_item, widget)

    def on_list_reordered(self, parent, start, end, destination, row):
        """列表重新排序時的回調"""
        new_items = []
        for i in range(self.item_list.count()):
            list_item = self.item_list.item(i)
            item_data = list_item.data(Qt.UserRole)
            if item_data:
                new_items.append(item_data)
        
        self.items = new_items
        self.update_list()
        self.update_wheel()
        self.save_settings()

    def on_item_toggled(self, index, checked):
        """選項啟用/停用切換"""
        if 0 <= index < len(self.items):
            self.items[index]['enabled'] = checked
            self.update_list()
            self.update_wheel()
            self.save_settings()

    def save_items(self):
        """儲存選項至檔案"""
        if not self.items:
            QMessageBox.information(self, "提示", "沒有項目可儲存")
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "儲存設定", "", "Json Files (*.json)")
        if file_name:
            self.do_save(file_name)

    def do_save(self, file_name):
        """執行儲存"""
        data = []
        for item in self.items:
            data.append({
                'name': item['name'],
                'weight': item['weight'],
                'color': item['color'].name(),
                'enabled': item.get('enabled', True)
            })
        try:
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            self.save_settings(last_file=file_name)
            QMessageBox.information(self, "成功", "設定已儲存")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗: {str(e)}")

    def load_items_dialog(self):
        """載入選項對話框"""
        file_name, _ = QFileDialog.getOpenFileName(self, "載入設定", "", "Json Files (*.json)")
        if file_name:
            self.do_load(file_name)

    def do_load(self, file_name):
        """執行載入"""
        try:
            with open(file_name, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.items = []
            for item_data in data:
                val = item_data['weight']
                weight_val = float(val)
                
                self.items.append({
                    'name': item_data['name'],
                    'weight': weight_val,
                    'color': QColor(item_data['color']),
                    'enabled': item_data.get('enabled', True)
                })
            
            self.update_list()
            self.update_wheel()
            self.save_settings(last_file=file_name)
            QMessageBox.information(self, "成功", "設定已載入")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"載入失敗: {str(e)}")

    def save_settings(self, last_file=None):
        """儲存設定"""
        settings = {
            "result_text_color": self.result_text_color.name(),
            "border_enabled": self.border_check.isChecked(),
            "border_color": self.border_color.name(),
            "separator_enabled": self.separator_check.isChecked(),
            "sound_enabled": self.sound_check.isChecked(),
            "finish_sound_enabled": self.finish_sound_check.isChecked(),
            "result_opacity": int(self.opacity_slider.value() * 2.55)
        }
        if last_file:
            settings["last_file"] = last_file
        elif os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    old_settings = json.load(f)
                    if "last_file" in old_settings:
                        settings["last_file"] = old_settings["last_file"]
            except:
                pass
                  
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except:
            pass

    def load_last_settings(self):
        """載入上次的設定"""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                if "result_text_color" in settings:
                    self.result_text_color = QColor(settings["result_text_color"])
                    self.update_result_color_btn()
                
                if "border_color" in settings:
                    self.border_color = QColor(settings["border_color"])
                    self.update_border_color_btn()
                    
                if "border_enabled" in settings:
                    self.border_check.setChecked(settings["border_enabled"])
                    
                if "separator_enabled" in settings:
                    self.separator_check.setChecked(settings["separator_enabled"])
                    
                if "sound_enabled" in settings:
                    self.sound_check.setChecked(settings["sound_enabled"])

                if "finish_sound_enabled" in settings:
                    self.finish_sound_check.setChecked(settings["finish_sound_enabled"])

                if "result_opacity" in settings:
                    self.result_opacity = settings["result_opacity"]
                    slider_val = int(self.result_opacity / 2.55)
                    self.opacity_slider.setValue(slider_val)
                    self.opacity_label.setText(f"{slider_val}%")
                    
                if "last_file" in settings and os.path.exists(settings["last_file"]):
                    with open(settings["last_file"], 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.items = []
                    for item_data in data:
                        self.items.append({
                            'name': item_data['name'],
                            'weight': float(item_data['weight']),
                            'color': QColor(item_data['color']),
                            'enabled': item_data.get('enabled', True)
                        })
                    self.update_list()
            except Exception as e:
                print(f"Error loading settings: {e}")

    def toggle_wheel(self):
        """切換轉盤視窗"""
        if self.wheel_window is None:
            active_items = [i for i in self.items if i.get('enabled', True)]
            if not active_items:
                QMessageBox.warning(self, "警告", "請先新增並啟用至少一個選項")
                return
            self.wheel_window = WheelWindow()
            self.update_wheel()
            self.wheel_window.show()
            self.wheel_window.spin_finished.connect(self.add_history_record)
            self.wheel_window.window_closed.connect(self.on_wheel_closed)
            self.open_wheel_btn.setText("關閉轉盤")
            
            self.multi_spin_setup_btn.setEnabled(True)
            self.multi_spin_setup_btn.setStyleSheet("background-color: #673AB7;")
        else:
            self.wheel_window.close()
            
    def on_wheel_closed(self):
        """轉盤視窗關閉時的回調"""
        self.wheel_window = None
        self.open_wheel_btn.setText("開啟轉盤")
        
        self.multi_spin_setup_btn.setEnabled(False)
        self.multi_spin_setup_btn.setStyleSheet("background-color: #9E9E9E;")
        
        if self.is_auto_spinning:
            self.is_auto_spinning = False
            self.multi_spin_setup_btn.setText("設定連抽")
            self.multi_spin_setup_btn.setStyleSheet("background-color: #673AB7;")

    def update_wheel(self):
        """更新轉盤設定"""
        if self.wheel_window:
            active_items = [i for i in self.items if i.get('enabled', True)]
            self.wheel_window.update_settings(
                active_items, 
                self.border_enabled_check(), 
                self.border_color, 
                self.result_text_color,
                self.separator_check.isChecked(),
                self.sound_check.isChecked(),
                self.finish_sound_check.isChecked(),
                int(self.opacity_slider.value() * 2.55)
            )
            
    def on_opacity_changed(self):
        """透明度滑桿改變時的回調"""
        val = self.opacity_slider.value()
        self.result_opacity = int(val * 2.55)
        self.opacity_label.setText(f"{val}%")
        
        if self.wheel_window:
            self.wheel_window.result_opacity = self.result_opacity
            self.wheel_window.preview_opacity()
            
    def update_wheel_settings(self):
        """更新轉盤設定並儲存"""
        self.save_settings()
        self.update_wheel()
        
    def resizeEvent(self, event):
        """視窗大小改變事件"""
        print(f"Config Window Size: {self.width()} x {self.height()}")
        super().resizeEvent(event)

    def border_enabled_check(self):
        """檢查邊框是否啟用"""
        return self.border_check.isChecked()
