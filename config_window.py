import random
import json
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QListWidget, QListWidgetItem, QColorDialog, QCheckBox, 
    QMessageBox, QDoubleSpinBox, QLabel, QGroupBox, QFormLayout,
    QInputDialog, QSlider, QFileDialog, QRadioButton, QButtonGroup,
    QSpinBox, QComboBox, QDialog
)
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen, QCursor
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QSize, QUrl
from collections import Counter
from wheel_window import WheelWindow
from utils import resource_path, external_path
from calibration_dialog import ImageCalibrationDialog
import csv
import shutil

SETTINGS_FILE = external_path("settings.json")


class SoundConflictDialog(QDialog):
    """音效衝突解決對話框"""
    def __init__(self, parent, file_keep, file_new):
        super().__init__(parent)
        self.setWindowTitle("音效衝突 - 選擇要保留的檔案")
        self.setWindowModality(Qt.WindowModal)
        self.resize(500, 200)
        self.selected_action = None # 'keep_old', 'replace_new', None(cancel)
        
        layout = QVBoxLayout(self)
        
        info_lbl = QLabel(f"偵測到同名但不同格式的音效檔！\n系統只能保留其中一個 (MP3優先於WAV)。\n請試聽並選擇要留下的檔案：")
        layout.addWidget(info_lbl)
        
        # Comparison Layout
        comp_layout = QHBoxLayout()
        
        # Left: Existing/Keep (The one that was already there or alternate format)
        # Actually logic is: File A (Old/Existing?) vs File B (New/Importing?)
        # Let's call them "既有檔案" vs "新匯入檔案"
        # Since we are detecting conflict, usually we have one on disk and one currently being imported (temp source).
        # Or if both are on disk (renaming case)?
        # Implementation: We passed in paths.
        
        self.file_keep = file_keep # The one that might be deleted if we choose new
        self.file_new = file_new   # The one providing replacement
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self.player.errorOccurred.connect(lambda error, msg=self.player.errorString(): print(f"Preview Error: {error} - {msg}"))
        
        # --- File A (Existing/Conflict) ---
        group_a = QGroupBox(f"保留: {os.path.basename(file_keep)}")
        layout_a = QVBoxLayout(group_a)
        btn_play_a = QPushButton("▶ 試聽")
        btn_play_a.clicked.connect(lambda: self.play_sound(file_keep))
        btn_select_a = QPushButton("保留此檔")
        btn_select_a.clicked.connect(self.choose_keep)
        layout_a.addWidget(btn_play_a)
        layout_a.addWidget(btn_select_a)
        comp_layout.addWidget(group_a)
        
        # --- File B (New/Importing) ---
        group_b = QGroupBox(f"使用新檔: {os.path.basename(file_new)}")
        layout_b = QVBoxLayout(group_b)
        btn_play_b = QPushButton("▶ 試聽")
        btn_play_b.clicked.connect(lambda: self.play_sound(file_new))
        btn_select_b = QPushButton("使用新檔")
        btn_select_b.clicked.connect(self.choose_new)
        layout_b.addWidget(btn_play_b)
        layout_b.addWidget(btn_select_b)
        comp_layout.addWidget(group_b)
        
        layout.addLayout(comp_layout)
        
        btn_cancel = QPushButton("取消匯入")
        btn_cancel.clicked.connect(self.reject)
        layout.addWidget(btn_cancel)

    def play_sound(self, path):
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        
    def choose_keep(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.selected_action = 'keep_old' # Keep the conflicting one (reject new)
        self.accept()
        
    def choose_new(self):
        self.player.stop()
        self.player.setSource(QUrl())
        self.selected_action = 'replace_new' # Use the new one (delete conflicting)
        self.accept()
        
    def closeEvent(self, event):
        self.player.stop()
        self.player.setSource(QUrl())
        super().closeEvent(event)


class CollapsibleBox(QWidget):
    """可收合的區塊元件"""
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.title = title
        self.toggle_btn = QPushButton(f"▼ {title}")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                text-align: left; 
                background-color: #333; 
                color: white;
                border: 1px solid #555;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)
        self.toggle_btn.toggled.connect(self.on_toggled)

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_area.setLayout(self.content_layout)
        
        lay = QVBoxLayout()
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_btn)
        lay.addWidget(self.content_area)
        self.setLayout(lay)
        
    def on_toggled(self, checked):
        self.content_area.setVisible(checked)
        arrow = "▼" if checked else "▶"
        self.toggle_btn.setText(f"{arrow} {self.title}")

    def setContentLayout(self, layout):
        self.content_layout.addLayout(layout)

class ItemWidget(QWidget):
    """選項列表項目元件"""
    toggled = Signal(bool)
    sound_toggled = Signal(bool)
    import_clicked = Signal()
    
    def __init__(self, name, weight, color, prob, enabled, sound_enabled, sound_file=""):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(enabled)
        self.checkbox.toggled.connect(self.on_toggled)
        self.checkbox.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; }")
        layout.addWidget(self.checkbox)
        
        self.color_lbl = QLabel()
        self.color_lbl.setFixedSize(20, 20)
        self.color_lbl.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #555;")
        layout.addWidget(self.color_lbl)
        
        text = f"{name} (W: {weight:.1f} | P: {prob:.1f}%)"
        self.info_lbl = QLabel(text)
        self.info_lbl.setStyleSheet("font-size: 10pt; font-weight: bold;")
        layout.addWidget(self.info_lbl)
        
        layout.addStretch()
        
        # 音效設定
        self.sound_check = QCheckBox("音效")
        self.sound_check.setChecked(sound_enabled)
        self.sound_check.toggled.connect(self.on_sound_toggled)
        layout.addWidget(self.sound_check)
        
        self.import_btn = QPushButton("匯入音效")
        
        if sound_file:
            self.import_btn.setText(f"♪ {sound_file}")
            self.import_btn.setToolTip(f"目前音效: {sound_file}")
            self.import_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-size: 12px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.import_btn.setFixedWidth(120) # Widen for text
        else:
            self.import_btn.setFixedSize(70, 25)
            self.import_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    font-size: 12px;
                    padding: 0px;
                }
                QPushButton:hover {
                    background-color: #1976D2;
                }
            """)
            
        self.import_btn.clicked.connect(self.import_clicked.emit)
        layout.addWidget(self.import_btn)
        
        self.setLayout(layout)
        
    def on_toggled(self, checked):
        """核取方塊切換事件"""
        self.toggled.emit(checked)

    def on_sound_toggled(self, checked):
        """音效切換事件"""
        self.sound_toggled.emit(checked)

class ConfigWindow(QWidget):
    """設定視窗主類別"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("轉盤設定")
        self.resize(550, 700)
        self.setMinimumWidth(550)
        self.setStyleSheet("""
            QWidget {
                font-family: "Microsoft JhengHei", sans-serif;
                font-size: 12pt;
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
        self.test_window = None
        self.current_file_path = None # Track current file
        
        self.history_sessions = [{"data": [], "memo": ""}]
        self.curr_session_idx = 0
        self.history_grouped = True
        self.panel_expanded = False
        self.history_panel_width = 300
        
        self.auto_spin_count = 0
        self.is_auto_spinning = False
        self.auto_spin_speed = 3.0
        
        self.result_text_color = QColor(255, 255, 255)
        self.result_bg_color = QColor(0, 0, 0)
        self.border_enabled = True
        self.border_color = QColor(255, 255, 255)
        self.sound_enabled = False
        self.finish_sound_enabled = False
        self.result_opacity = 150
        self.result_opacity = 150
        self.always_on_top = True # Legacy boolean, keeping just in case
        self.window_mode = 'top' # 'top', 'tool', 'normal'
        self.pre_expand_width = 400
        
        self.wheel_mode = "classic" # "classic" 或 "image"
        self.wheel_mode = "classic" # "classic" 或 "image"
        self.pointer_image_path = resource_path(os.path.join("PIC", "ARR.png"))
        self.pointer_angle_offset = 135
        self.pointer_scale = 0.4
        self.spin_speed_multiplier = 1.0 # 速度倍率 (1.0 = 正常)
        self.allowed_speeds = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.5, 10.0]
        self.classic_pointer_angle = 0
        self.center_text = "GO"
        self.show_pointer_line = True
        self.editing_index = -1
        
        self.init_ui()
        self.load_last_settings()
        
    def init_ui(self):
        """初始化使用者介面"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(20, 5, 10, 5)
        self.setMinimumSize(400, 400)
        
        self.input_group = CollapsibleBox("新增/編輯選項")
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
        
        self.input_group.setContentLayout(input_layout)
        main_layout.addWidget(self.input_group)

        # 樣式設定群組 (使用自訂 CollapsibleBox)
        self.style_group = CollapsibleBox("轉盤樣式設定")
        style_layout = QFormLayout()
        
        # 轉盤模式
        mode_layout = QHBoxLayout()
        self.mode_classic_radio = QRadioButton("經典")
        self.mode_image_radio = QRadioButton("圖片指針")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_classic_radio)
        self.mode_group.addButton(self.mode_image_radio)
        self.mode_classic_radio.setChecked(True) 
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        mode_layout.addWidget(self.mode_classic_radio)
        mode_layout.addWidget(self.mode_image_radio)
        
        mode_layout.addSpacing(20)
        mode_layout.addWidget(QLabel("置頂方式:"))
        
        # Window Mode Combo (Move here)
        self.window_mode_combo = QComboBox()
        self.window_mode_combo.addItems(["置頂", "普通"])
        self.window_mode_combo.currentIndexChanged.connect(self.on_window_mode_changed)
        mode_layout.addWidget(self.window_mode_combo)
        
        mode_layout.addStretch()
        style_layout.addRow("轉盤模式:", mode_layout)
        
        # 圖片模式設定區塊
        self.image_mode_container = QWidget()
        image_mode_layout = QHBoxLayout(self.image_mode_container)
        image_mode_layout.setContentsMargins(0, 0, 0, 0)
        image_mode_layout.setSpacing(5)
        
        image_mode_layout.addWidget(QLabel("指針圖片:"))
        
        self.image_path_label = QLabel("未選擇圖片")
        image_mode_layout.addWidget(self.image_path_label)
        
        self.image_select_btn = QPushButton("選擇圖片")
        self.image_select_btn.clicked.connect(self.select_pointer_image)
        image_mode_layout.addWidget(self.image_select_btn)
        
        self.calibrate_btn = QPushButton("圖片修正")
        self.calibrate_btn.clicked.connect(self.open_calibration_dialog)
        self.calibrate_btn.setEnabled(False)
        image_mode_layout.addWidget(self.calibrate_btn)
        
        self.pointer_line_btn = QPushButton("輔助線: 開")
        self.pointer_line_btn.setCheckable(True)
        self.pointer_line_btn.setChecked(True)
        self.pointer_line_btn.clicked.connect(self.toggle_pointer_line)
        self.pointer_line_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        image_mode_layout.addWidget(self.pointer_line_btn)
        
        image_mode_layout.addStretch()
        
        style_layout.addRow(self.image_mode_container)
        self.image_mode_container.setVisible(False)
        
        # 經典模式設定區塊
        self.image_mode_container.setVisible(False)

        # 經典模式設定區塊
        self.classic_mode_container = QWidget()
        classic_mode_layout = QHBoxLayout(self.classic_mode_container)
        classic_mode_layout.setContentsMargins(0, 0, 0, 0)
        
        classic_mode_layout.addWidget(QLabel("指針位置:"))
        self.pointer_angle_combo = QComboBox()
        # 0=右(E), 45=右下(SE), 90=下(S), 135=左下(SW), 180=左(W), 225=左上(NW), 270=上(N), 315=右上(NE)
        self.pointer_angle_combo.addItems(["0° (右)", "45° (右下)", "90° (下)", "135° (左下)", "180° (左)", "225° (左上)", "270° (上)", "315° (右上)"])
        self.pointer_angle_combo.currentIndexChanged.connect(self.on_classic_settings_changed)
        classic_mode_layout.addWidget(self.pointer_angle_combo)
        
        classic_mode_layout.addSpacing(15)
        
        classic_mode_layout.addWidget(QLabel("中間文字:"))
        self.center_text_input = QLineEdit("GO")
        self.center_text_input.setFixedWidth(60)
        self.center_text_input.textChanged.connect(self.on_classic_settings_changed)
        classic_mode_layout.addWidget(self.center_text_input)
        classic_mode_layout.addStretch()
        
        style_layout.addRow(self.classic_mode_container)
        
        # 線條設定 (邊框與分隔線)
        line_layout = QHBoxLayout()
        # 邊框
        self.border_check = QCheckBox("啟用邊框")
        self.border_check.stateChanged.connect(self.update_wheel_settings)
        line_layout.addWidget(self.border_check)
        
        line_layout.addSpacing(15)
        
        # 分隔線 (移至邊框顏色左側)
        self.separator_check = QCheckBox("啟用分隔線 (同邊框色)")
        self.separator_check.setChecked(True)
        self.separator_check.stateChanged.connect(self.update_wheel_settings)
        line_layout.addWidget(self.separator_check)

        line_layout.addSpacing(15)

        self.border_color_btn = QPushButton()
        self.border_color_btn.setFixedSize(50, 20)
        self.border_color_btn.clicked.connect(self.choose_border_color)
        self.border_color_btn.setStyleSheet(f"background-color: {self.border_color.name()}")
        line_layout.addWidget(self.border_color_btn)
        
        line_layout.addStretch()
        
        style_layout.addRow("線條設定:", line_layout)
        
        # 結果設定 (顏色與透明度)
        result_layout = QHBoxLayout()
        
        self.result_color_btn = QPushButton("文字顏色")
        self.result_color_btn.clicked.connect(self.choose_result_color)
        # self.result_color_btn.setMinimumWidth(100) 
        self.update_result_color_btn()
        result_layout.addWidget(self.result_color_btn, 1) # stretch factor 1
        
        self.result_bg_color_btn = QPushButton("背景顏色")
        self.result_bg_color_btn.clicked.connect(self.choose_result_bg_color)
        # self.result_bg_color_btn.setMinimumWidth(100)
        self.update_result_bg_color_btn()
        result_layout.addWidget(self.result_bg_color_btn, 1) # stretch factor 1
        
        # 透明度設定 (整合進同一行)
        #result_layout.addSpacing(1)
        result_layout.addWidget(QLabel("不透明度:"))
        
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(60)
        self.opacity_slider.setFixedWidth(120) # 稍微縮小滑桿寬度
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        self.opacity_slider.sliderReleased.connect(self.save_settings)
        result_layout.addWidget(self.opacity_slider)
        
        self.opacity_label = QLabel("60%")
        self.opacity_label.setFixedWidth(45)
        result_layout.addWidget(self.opacity_label)
        
        style_layout.addRow(result_layout)

        # 音效設定
        self.sound_container = QWidget()
        sound_multi_layout = QHBoxLayout(self.sound_container)
        sound_multi_layout.setContentsMargins(0, 0, 0, 0)
        
        self.sound_check = QCheckBox("旋轉音效")
        self.sound_check.setChecked(False)
        self.sound_check.stateChanged.connect(self.update_wheel_settings)
        sound_multi_layout.addWidget(self.sound_check)

        self.continuous_sound_check = QCheckBox("持續音效")
        self.continuous_sound_check.setChecked(False)
        self.continuous_sound_check.stateChanged.connect(self.update_wheel_settings)
        sound_multi_layout.addWidget(self.continuous_sound_check)

        self.finish_sound_check = QCheckBox("結束音效 ")
        self.finish_sound_check.setChecked(False)
        self.finish_sound_check.stateChanged.connect(self.update_wheel_settings)
        sound_multi_layout.addWidget(self.finish_sound_check)
        
        # 匯入音效按鈕
        self.import_sound_btn = QPushButton("匯入音效")
        self.import_sound_btn.clicked.connect(self.import_custom_sound)
        self.import_sound_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        sound_multi_layout.addWidget(self.import_sound_btn)
        
        sound_multi_layout.addStretch()
        
        style_layout.addRow(self.sound_container)

        # 旋轉速度
        speed_layout = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(0, len(self.allowed_speeds) - 1)
        # Find closest index for current speed
        current_idx = 2 # Default to 1.0 (index 2)
        try:
             current_idx = self.allowed_speeds.index(self.spin_speed_multiplier)
        except ValueError:
             # If not exact match, find closest
             current_idx = min(range(len(self.allowed_speeds)), key=lambda i: abs(self.allowed_speeds[i]-self.spin_speed_multiplier))
        self.speed_slider.setValue(current_idx)
        self.speed_slider.setFixedWidth(150)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        self.speed_slider.sliderReleased.connect(self.save_settings)
        speed_layout.addWidget(self.speed_slider)
        self.speed_label = QLabel("1.0x")
        self.speed_label.setFixedWidth(40)
        speed_layout.addWidget(self.speed_label)
        
        speed_layout.addSpacing(15)
        
        speed_layout.addStretch()
        
        self.multi_spin_setup_btn = QPushButton("設定連抽")
        self.multi_spin_setup_btn.clicked.connect(self.show_multi_spin_dialog)
        self.multi_spin_setup_btn.setEnabled(False)
        self.multi_spin_setup_btn.setStyleSheet("background-color: #9E9E9E;")
        speed_layout.addWidget(self.multi_spin_setup_btn)
        
        speed_layout.addSpacing(10)
        
        # Window Mode Combo moved up
        
        style_layout.addRow("旋轉速度:", speed_layout)

        self.style_group.setContentLayout(style_layout)
        main_layout.addWidget(self.style_group)
        
        # --- 列表群組 ---
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
        
        hist_title_layout = QHBoxLayout()
        self.hist_title_lbl = QLabel(f"轉動紀錄 ({self.curr_session_idx + 1})")
        self.hist_title_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        hist_title_layout.addWidget(self.hist_title_lbl)
        
        hist_title_layout.addStretch()
        
        self.hist_clear_btn = QPushButton("清空此頁")
        self.hist_clear_btn.setStyleSheet("padding: 2px; background-color: #d32f2f; font-size: 10pt;")
        self.hist_clear_btn.setFixedSize(60, 25)
        self.hist_clear_btn.clicked.connect(self.clear_history)
        hist_title_layout.addWidget(self.hist_clear_btn)
        
        self.prev_session_btn = QPushButton("＜")
        self.prev_session_btn.setFixedSize(30, 25)
        self.prev_session_btn.setStyleSheet("padding: 0; background-color: #4CAF50;") # 覆蓋全域 padding
        self.prev_session_btn.clicked.connect(self.prev_session)
        self.prev_session_btn.setEnabled(False)
        hist_title_layout.addWidget(self.prev_session_btn)
        
        self.next_session_btn = QPushButton("＞")
        self.next_session_btn.setFixedSize(30, 25)
        self.next_session_btn.setStyleSheet("padding: 0; background-color: #4CAF50;") # 覆蓋全域 padding
        self.next_session_btn.clicked.connect(self.next_session)
        hist_title_layout.addWidget(self.next_session_btn)
        
        hist_layout.addLayout(hist_title_layout)
        
        self.history_memo = QLineEdit()
        self.history_memo.setPlaceholderText("備註 (跟隨此紀錄)")
        self.history_memo.textChanged.connect(self.save_current_memo)
        hist_layout.addWidget(self.history_memo)
        
        self.hist_view_btn = QPushButton("切換：合併顯示")
        self.hist_view_btn.clicked.connect(self.toggle_history_view)
        hist_layout.addWidget(self.hist_view_btn)
        
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QListWidget.NoSelection) # 禁止選取
        hist_layout.addWidget(self.history_list)
        
        # Bottom controls for history
        hist_bottom_layout = QHBoxLayout()
        
        self.clear_all_btn = QPushButton("清除全部")
        self.clear_all_btn.setStyleSheet("background-color: #b71c1c;")
        self.clear_all_btn.clicked.connect(self.clear_all_history)
        hist_bottom_layout.addWidget(self.clear_all_btn)
        
        self.export_csv_btn = QPushButton("匯出 CSV")
        self.export_csv_btn.setStyleSheet("background-color: #009688;")
        self.export_csv_btn.clicked.connect(self.export_history_csv)
        hist_bottom_layout.addWidget(self.export_csv_btn)
        
        hist_layout.addLayout(hist_bottom_layout)
        
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
                background-color: black;
                color: white;
                border: 1px solid #333;
                border-top-left-radius: 10px;
                border-bottom-left-radius: 10px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #333;
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
            if target_width < 550:
                target_width = 550
            
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
        
        self.save_settings()
            
    def add_history_record(self, winner_name):
        """新增歷史紀錄"""
        self.history_sessions[self.curr_session_idx]['data'].append(winner_name)
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
            
        # 確保對話框在最上層
        msg = QMessageBox(self)
        msg.setWindowTitle("準備連抽")
        msg.setText("開始連抽前，是否清空目前的歷史紀錄？")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.No)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        reply = msg.exec()
                                   
        if reply == QMessageBox.Cancel:
            return
        if reply == QMessageBox.Yes:
            self.clear_history()

        # 速度輸入
        input_dialog_speed = QInputDialog(self)
        input_dialog_speed.setWindowTitle("多連抽設定")
        input_dialog_speed.setLabelText("速度倍率 (原本的幾倍?):")
        input_dialog_speed.setDoubleDecimals(1)
        input_dialog_speed.setDoubleRange(1.0, 10.0)
        input_dialog_speed.setDoubleValue(3.0)
        input_dialog_speed.setWindowFlags(input_dialog_speed.windowFlags() | Qt.WindowStaysOnTopHint)
        
        if input_dialog_speed.exec() == QInputDialog.Accepted:
            speed = input_dialog_speed.doubleValue()
        else:
            return

        # 次數輸入
        input_dialog_count = QInputDialog(self)
        input_dialog_count.setWindowTitle("多連抽設定")
        input_dialog_count.setLabelText("連抽次數:")
        input_dialog_count.setIntRange(1, 1000)
        input_dialog_count.setIntValue(10)
        input_dialog_count.setWindowFlags(input_dialog_count.windowFlags() | Qt.WindowStaysOnTopHint)

        if input_dialog_count.exec() == QInputDialog.Accepted:
            count = input_dialog_count.intValue()
        else:
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
        
        current_data = self.history_sessions[self.curr_session_idx]['data']
        current_memo = self.history_sessions[self.curr_session_idx]['memo']
        
        # update memo without triggering signal loop if possible, or just set it
        self.history_memo.blockSignals(True)
        self.history_memo.setText(current_memo)
        self.history_memo.blockSignals(False)
        
        self.hist_title_lbl.setText(f"轉動紀錄 ({self.curr_session_idx + 1})")
        self.prev_session_btn.setEnabled(self.curr_session_idx > 0)
        
        if not current_data:
            return
        
        if self.history_grouped:
            self.hist_view_btn.setText("切換：個別顯示")
            counts = Counter(current_data)
            for name, count in counts.most_common():
                item = QListWidgetItem(f"{name} x{count}")
                item.setTextAlignment(Qt.AlignCenter)
                self.history_list.addItem(item)
        else:
            self.hist_view_btn.setText("切換：合併顯示")
            for name in reversed(current_data):
                item = QListWidgetItem(name)
                item.setTextAlignment(Qt.AlignCenter)
                self.history_list.addItem(item)

    def toggle_history_view(self):
        """切換歷史紀錄顯示模式"""
        self.history_grouped = not self.history_grouped
        self.update_history_list()
        
    def clear_history(self):
        """清空歷史紀錄"""
        self.history_sessions[self.curr_session_idx]['data'] = []
        # user might want to keep the memo, or clear it? 
        # "備註 (清空時移除)" -> implies clear.
        # But now "跟隨此紀錄". Let's clear data but keep memo? 
        # User prompt said "remark is associated with a specific one".
        # Usually clearing history clears data. Let's clear data only for now unless user asked to clear memo.
        # Actually previous code cleared memo: self.history_memo.clear()
        # Let's keep that behavior for the current session.
        self.history_sessions[self.curr_session_idx]['memo'] = ""
        self.history_memo.clear()
        self.update_history_list()

    def prev_session(self):
        if self.curr_session_idx > 0:
            self.curr_session_idx -= 1
            self.update_history_list()
            self.save_settings()

    def next_session(self):
        # Check if current session is last
        if self.curr_session_idx == len(self.history_sessions) - 1:
            # Create new session
            self.history_sessions.append({"data": [], "memo": ""})
            
        self.curr_session_idx += 1
        self.update_history_list()
        self.save_settings()
        
    def save_current_memo(self):
        self.history_sessions[self.curr_session_idx]['memo'] = self.history_memo.text()
        pass

    def clear_all_history(self):
        """清除所有歷史紀錄"""
        # 使用 WindowModal 避免凍結轉盤視窗
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("確認")
        msg_box.setText("確定要清除所有紀錄嗎？")
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setWindowModality(Qt.WindowModal)
        
        if msg_box.exec() == QMessageBox.Yes:
            self.history_sessions = [{"data": [], "memo": ""}]
            self.curr_session_idx = 0
            self.update_history_list()
            self.save_settings()

    def export_history_csv(self):
        """匯出所有歷史紀錄為 CSV"""
        # 使用 WindowModal 檔案對話框
        dialog = QFileDialog(self, "匯出 CSV", "", "CSV Files (*.csv)")
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setWindowModality(Qt.WindowModal)
        
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                file_name = files[0]
                try:
                    with open(file_name, 'w', newline='', encoding='utf-8-sig') as csvfile:
                        writer = csv.writer(csvfile)
                        
                        # 準備資料
                        # Row 1: Session IDs
                        ids = [f"紀錄 {i+1}" for i in range(len(self.history_sessions))]
                        writer.writerow(ids)
                        
                        # Row 2: Memos
                        memos = [s.get('memo', '') for s in self.history_sessions]
                        writer.writerow(memos)
                        
                        # Row 3+: Data (Transpose)
                        # Find max length
                        max_len = 0
                        for s in self.history_sessions:
                            data = s.get('data', [])
                            if len(data) > max_len:
                                max_len = len(data)
                                
                        for i in range(max_len):
                            row_data = []
                            for s in self.history_sessions:
                                data = s.get('data', [])
                                # Chronological: Old -> New
                                rev_data = list(data)
                                if i < len(rev_data):
                                    row_data.append(rev_data[i])
                                else:
                                    row_data.append("")
                            writer.writerow(row_data)
                                    
                    # 成功提示也需要 WindowModal
                    msg = QMessageBox(self)
                    msg.setWindowTitle("成功")
                    msg.setText("匯出完成！")
                    msg.setIcon(QMessageBox.Information)
                    msg.setWindowModality(Qt.WindowModal)
                    msg.exec()
                    
                except Exception as e:
                    msg = QMessageBox(self)
                    msg.setWindowTitle("錯誤")
                    msg.setText(f"匯出失敗: {str(e)}")
                    msg.setIcon(QMessageBox.Critical)
                    msg.setWindowModality(Qt.WindowModal)
                    msg.exec()

    def choose_result_color(self):
        """選擇結果文字顏色"""
        color = QColorDialog.getColor(self.result_text_color)
        if color.isValid():
            self.result_text_color = color
            self.update_result_color_btn()
            self.update_result_bg_color_btn() # Update preview checking
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
            msg = QMessageBox(self)
            msg.setWindowTitle("錯誤")
            msg.setText("請輸入選項名稱")
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowModality(Qt.WindowModal)
            msg.exec()
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
        self.auto_save_items() # Call auto_save_items here
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
        
        # Auto expand input group
        if hasattr(self, 'input_group'):
            self.input_group.toggle_btn.setChecked(True)

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
            self.auto_save_items() # Call auto_save_items here
            if row == self.editing_index:
                self.cancel_edit()
        else:
            msg = QMessageBox(self)
            msg.setWindowTitle("提示")
            msg.setText("請先選擇要移除的項目")
            msg.setIcon(QMessageBox.Information)
            msg.setWindowModality(Qt.WindowModal)
            msg.exec()

    def move_item_up(self):
        """上移選項"""
        row = self.item_list.currentRow()
        if row > 0:
            self.items[row], self.items[row-1] = self.items[row-1], self.items[row]
            self.update_list()
            self.item_list.setCurrentRow(row-1)
            self.update_wheel()
            self.auto_save_items() # Call auto_save_items here
            
    def move_item_down(self):
        """下移選項"""
        row = self.item_list.currentRow()
        if row >= 0 and row < len(self.items) - 1:
            self.items[row], self.items[row+1] = self.items[row+1], self.items[row]
            self.update_list()
            self.item_list.setCurrentRow(row+1)
            self.update_wheel()
            self.auto_save_items() # Call auto_save_items here
            
    def test_wheel(self):
        """開啟測試轉盤"""
        active_items = [i for i in self.items if i.get('enabled', True)]
        if not active_items:
            msg = QMessageBox(self)
            msg.setWindowTitle("警告")
            msg.setText("請先新增並啟用至少一個選項")
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowModality(Qt.WindowModal)
            msg.exec()
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
        self.auto_save_items() # Call auto_save_items here
        self.save_settings()
        self.update_wheel()

    def update_list(self):
        """更新選項列表"""
        # 保存捲動位置
        scroll_bar = self.item_list.verticalScrollBar()
        current_scroll = scroll_bar.value()
        
        self.item_list.clear()
        
        active_items = [i for i in self.items if i.get('enabled', True)]
        total_weight = sum(i['weight'] for i in active_items)
        
        for i, item in enumerate(self.items):
            list_item = QListWidgetItem()
            self.item_list.addItem(list_item)
            
            prob = 0
            if item.get('enabled', True) and total_weight > 0:
                prob = (item['weight'] / total_weight) * 100
                
            widget = ItemWidget(item['name'], item['weight'], item['color'], prob, item.get('enabled', True), item.get('sound_enable', False), item.get('sound_file', ""))
            widget.toggled.connect(lambda checked, idx=i: self.on_item_toggled(idx, checked))
            widget.sound_toggled.connect(lambda checked, idx=i: self.on_item_sound_toggled(idx, checked))
            widget.import_clicked.connect(lambda idx=i: self.on_item_import_clicked(idx))
            
            list_item.setSizeHint(widget.sizeHint())
            list_item.setData(Qt.UserRole, item)
            self.item_list.setItemWidget(list_item, widget)
            
        # 恢復捲動位置
        scroll_bar.setValue(current_scroll)

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
        self.auto_save_items() # Call auto_save_items here
        self.save_settings()

    def on_item_toggled(self, index, checked):
        """選項啟用/停用切換"""
        if 0 <= index < len(self.items):
            self.items[index]['enabled'] = checked
            self.update_list()
            self.update_wheel()
            self.auto_save_items()
            self.save_settings()

    def on_item_sound_toggled(self, index, checked):
        """選項音效啟用/停用切換"""
        if 0 <= index < len(self.items):
            self.items[index]['sound_enable'] = checked
            self.auto_save_items()
            self.save_settings()

    def on_item_import_clicked(self, index):
        """選項專屬音效匯入"""
        if not (0 <= index < len(self.items)):
            return
            
        item = self.items[index]
        name = item['name']
        
        dialog = QFileDialog(self, f"匯入音效 ({name})", "", "Audio Files (*.mp3 *.wav)")
        dialog.setWindowModality(Qt.WindowModal)
        
        if dialog.exec():
            files = dialog.selectedFiles()
            if not files:
                return
            src_path = files[0]
            
            # Check size (10MB)
            if os.path.getsize(src_path) > 10 * 1024 * 1024:
                msg = QMessageBox(self)
                msg.setText("檔案大小不能超過 10MB")
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowModality(Qt.WindowModal)
                msg.exec()
                return
                
            try:
                sound_dir = external_path("SOUND")
                if not os.path.exists(sound_dir):
                    os.makedirs(sound_dir)
                    
                target_filename = os.path.basename(src_path)
                target_path = os.path.join(sound_dir, target_filename)
                
                # Release locks if WheelWindow exists
                if self.wheel_window:
                    self.wheel_window.release_audio_locks()

                # Execute Copy (Standard copy will overwrite if exists)
                if os.path.exists(target_path):
                     # If it's the exact same file (same path), do nothing
                     if os.path.abspath(target_path) == os.path.abspath(src_path):
                         pass
                     else:
                         try:
                             os.remove(target_path)
                         except:
                             pass
                         shutil.copy2(src_path, target_path)
                else:
                     shutil.copy2(src_path, target_path)
                
                # Update item data
                self.items[index]['sound_enable'] = True
                self.items[index]['sound_file'] = target_filename
                
                # Reload wheel sounds
                if self.wheel_window:
                    self.wheel_window.load_sounds()
                self.auto_save_items()
                self.save_settings()
                
                msg = QMessageBox(self)
                msg.setText(f"已匯入選項音效: {target_filename}")
                msg.setIcon(QMessageBox.Information)
                msg.setWindowModality(Qt.WindowModal)
                msg.exec()
                
            except Exception as e:
                msg = QMessageBox(self)
                msg.setText(f"匯入失敗: {str(e)}")
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowModality(Qt.WindowModal)
                msg.exec()

    def update_result_color_btn(self):
        self.result_color_btn.setStyleSheet(f"background-color: #e3e3e3; color: {self.result_text_color.name()}; font-weight: bold;")

    def choose_result_bg_color(self):
        color = QColorDialog.getColor(self.result_bg_color, self, "選擇結果背景顏色")
        if color.isValid():
            self.result_bg_color = color
            self.update_result_bg_color_btn()
            self.save_settings()

    def update_result_bg_color_btn(self):
        self.result_bg_color_btn.setStyleSheet(f"background-color: {self.result_bg_color.name()}; color: {self.result_text_color.name()}; font-weight: bold;")

    def save_items(self):
        """儲存選項至檔案"""
        if not self.items:
            msg = QMessageBox(self)
            msg.setWindowTitle("提示")
            msg.setText("沒有項目可儲存")
            msg.setIcon(QMessageBox.Information)
            msg.setWindowModality(Qt.WindowModal)
            msg.exec()
            return

        # 使用 WindowModal 檔案對話框
        dialog = QFileDialog(self, "儲存設定", "", "Json Files (*.json)")
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setWindowModality(Qt.WindowModal)
        
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                self.do_save(files[0])

    def do_save(self, file_name):
        """執行儲存"""
        self.current_file_path = file_name
        self.auto_save_items()
        self.save_settings(last_file=file_name)
        QMessageBox.information(self, "成功", "設定已儲存")

    def auto_save_items(self):
        """自動儲存選項至當前檔案"""
        target_file = self.current_file_path
        if not target_file:
            target_file = external_path("autosave.json")
            
        data = []
        for item in self.items:
            data.append({
                'name': item['name'],
                'weight': item['weight'],
                'color': item['color'].name(),
                'enabled': item.get('enabled', True),
                'sound_enable': item.get('sound_enable', False),
                'sound_file': item.get('sound_file', "")
            })
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass # Silent fail for auto-save

    def load_items_dialog(self):
        """載入選項對話框"""
        # 使用 WindowModal 檔案對話框
        dialog = QFileDialog(self, "載入設定", "", "Json Files (*.json)")
        dialog.setWindowModality(Qt.WindowModal)
        
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                self.do_load(files[0])

    def do_load(self, file_name):
        """執行載入 (僅讀取內容，不綁定檔案路徑)"""
        try:
            # self.current_file_path = file_name # 移除這行，避免自動儲存覆蓋原始檔案
            with open(file_name, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.items = []
            for item_data in data:
                val = item_data['weight']
                weight_val = float(val)
                
                # 驗證音效路徑是否存在
                sound_file = item_data.get('sound_file', "")
                sound_enable = item_data.get('sound_enable', False)
                if sound_file and not os.path.exists(sound_file):
                    sound_file = ""  # 路徑不存在，重置為預設
                    sound_enable = False
                
                self.items.append({
                    'name': item_data['name'],
                    'weight': weight_val,
                    'color': QColor(item_data['color']),
                    'enabled': item_data.get('enabled', True),
                    'sound_enable': sound_enable,
                    'sound_file': sound_file
                })
            
            self.update_list()
            self.update_wheel()
            
            # 不更新 last_file，因為這只是匯入資料，不是開啟專案
            # self.save_settings(last_file=file_name) 
            self.save_settings() # 僅儲存 UI 設定
            
            # 觸發一次自動儲存到預設的 autosave.json (或保持未儲存狀態直到使用者手動存檔)
            # 這裡我們選擇讓它存到 autosave.json，確保資料不會遺失
            self.current_file_path = None 
            self.auto_save_items() # 這會失敗或存到 autosave? 
            # 修正: auto_save_items 依賴 current_file_path。
            # 如果是 None，auto_save 會 return。
            # 所以這裡我們應該明確告訴使用者：已匯入，但尚未儲存到特定檔案。
            
            QMessageBox.information(self, "成功", "設定已載入 (變更不會寫回原檔案)")
        except Exception as e:
            msg = QMessageBox(self)
            msg.setWindowTitle("錯誤")
            msg.setText(f"載入失敗: {str(e)}")
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowModality(Qt.WindowModal)
            msg.exec()

    def save_settings(self, last_file=None):
        """儲存設定"""
        if last_file is None:
            last_file = self.current_file_path

        settings = {
            "result_text_color": self.result_text_color.name(),
            "result_bg_color": self.result_bg_color.name(),
            "border_enabled": self.border_check.isChecked(),
            "border_color": self.border_color.name(),
            "separator_enabled": self.separator_check.isChecked(),
            "sound_enabled": self.sound_check.isChecked(),
            "continuous_sound_enabled": self.continuous_sound_check.isChecked(),
            "finish_sound_enabled": self.finish_sound_check.isChecked(),
            "result_opacity": int(self.opacity_slider.value() * 2.55),
            "always_on_top": self.always_on_top,
            "window_mode": self.window_mode,
            
            "wheel_mode": self.wheel_mode,
            "pointer_image_path": self.pointer_image_path,
            "pointer_angle_offset": self.pointer_angle_offset,
            "pointer_scale": self.pointer_scale,
            "spin_speed_multiplier": self.spin_speed_multiplier,
            "classic_pointer_angle": self.classic_pointer_angle,
            "center_text": self.center_text,
            "show_pointer_line": self.show_pointer_line,
            "panel_expanded": self.panel_expanded,
            "input_panel_expanded": self.input_group.toggle_btn.isChecked() if hasattr(self, 'input_group') else True,
            "style_panel_expanded": self.style_group.toggle_btn.isChecked() if hasattr(self, 'style_group') else True,
            "history_sessions": self.history_sessions,
            "curr_session_idx": self.curr_session_idx
        }
        
        if last_file:
            settings["last_file"] = last_file

        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except:
            pass

    def load_last_settings(self):
        """載入上次的設定"""
        print(f"DEBUG: Loading settings... File: {__file__}")
        items_loaded = False
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                if "result_text_color" in settings:
                    self.result_text_color = QColor(settings["result_text_color"])
                    self.update_result_color_btn()

                if "result_bg_color" in settings:
                    self.result_bg_color = QColor(settings["result_bg_color"])
                    self.update_result_bg_color_btn()
                
                if "border_color" in settings:
                    self.border_color = QColor(settings["border_color"])
                    self.update_border_color_btn()
                    
                if "border_enabled" in settings:
                    self.border_check.setChecked(settings["border_enabled"])
                    
                if "separator_enabled" in settings:
                    self.separator_check.setChecked(settings["separator_enabled"])
                    
                if "sound_enabled" in settings:
                    self.sound_check.setChecked(settings["sound_enabled"])

                if "continuous_sound_enabled" in settings:
                    self.continuous_sound_check.setChecked(settings["continuous_sound_enabled"])

                if "finish_sound_enabled" in settings:
                    self.finish_sound_check.setChecked(settings["finish_sound_enabled"])

                if "result_opacity" in settings:
                    self.result_opacity = settings["result_opacity"]
                    slider_val = int(self.result_opacity / 2.55)
                    self.opacity_slider.setValue(slider_val)
                    self.opacity_label.setText(f"{slider_val}%")

                if "always_on_top" in settings:
                    self.always_on_top = settings["always_on_top"]
                    # If legacy setting is true, default to 'top', otherwise 'normal' if mode not found
                    if self.always_on_top:
                         self.window_mode = 'top'
                    else:
                         self.window_mode = 'normal'
                         
                if "window_mode" in settings:
                    self.window_mode = settings["window_mode"]
                
                # Update combo box
                mode_map = {'top': 0, 'normal': 1}
                # Handle legacy 'tool' value -> map to 'normal'
                if self.window_mode == 'tool':
                    self.window_mode = 'normal'
                
                if self.window_mode in mode_map:
                    self.window_mode_combo.setCurrentIndex(mode_map[self.window_mode])
                
                # Restore panel expansion state
                if "panel_expanded" in settings:
                    should_expand = settings["panel_expanded"]
                    if should_expand != self.panel_expanded:
                        self.toggle_history_panel()

                if "input_panel_expanded" in settings and hasattr(self, 'input_group'):
                    self.input_group.toggle_btn.setChecked(settings["input_panel_expanded"])

                if "style_panel_expanded" in settings and hasattr(self, 'style_group'):
                    self.style_group.toggle_btn.setChecked(settings["style_panel_expanded"])

                if "history_sessions" in settings:
                    self.history_sessions = settings["history_sessions"]
                if "curr_session_idx" in settings:
                    self.curr_session_idx = settings["curr_session_idx"]
                    # Boundary check
                    if self.curr_session_idx >= len(self.history_sessions):
                        self.curr_session_idx = 0

                # 載入新設定
                # 載入新設定
                self.wheel_mode = settings.get('wheel_mode', 'classic')
                self.pointer_image_path = settings.get('pointer_image_path', "")
                
                # Check if image exists, if not fallback to default
                if not self.pointer_image_path or not os.path.exists(self.pointer_image_path):
                     default_path = resource_path(os.path.join("PIC", "ee.png"))
                     if os.path.exists(default_path):
                         self.pointer_image_path = default_path
                         self.pointer_angle_offset = 335 # Default for ee.png
                     else:
                         self.pointer_image_path = ""
                         self.pointer_angle_offset = settings.get('pointer_angle_offset', 0)
                else:
                    self.pointer_angle_offset = settings.get('pointer_angle_offset', 0)

                self.pointer_scale = settings.get('pointer_scale', 1.0)
                self.spin_speed_multiplier = settings.get('spin_speed_multiplier', 1.0)
                
                self.classic_pointer_angle = settings.get('classic_pointer_angle', 0)
                self.center_text = settings.get('center_text', "GO")
                self.show_pointer_line = settings.get('show_pointer_line', True)

                # Update UI Mode State
                if self.wheel_mode == 'classic':
                    self.mode_classic_radio.setChecked(True)
                    self.image_mode_container.setVisible(False)
                    self.classic_mode_container.setVisible(True)
                else:
                    self.mode_image_radio.setChecked(True)
                    self.image_mode_container.setVisible(True)
                    self.classic_mode_container.setVisible(False)

                if self.pointer_image_path:
                    self.image_path_label.setText(os.path.basename(self.pointer_image_path))
                else:
                    self.image_path_label.setText("未選擇圖片")
                
                self.update_pointer_line_btn_state()
                
                # 恢復 UI 狀態
                angle_index = self.classic_pointer_angle // 45
                if 0 <= angle_index < 8:
                    self.pointer_angle_combo.setCurrentIndex(angle_index)
                self.center_text_input.setText(self.center_text)
                
                # 更新速度滑桿
                try:
                    # Find closest index
                    current_idx = min(range(len(self.allowed_speeds)), key=lambda i: abs(self.allowed_speeds[i]-self.spin_speed_multiplier))
                    self.speed_slider.setValue(current_idx)
                    self.spin_speed_multiplier = self.allowed_speeds[current_idx] # Snap to allowed value
                except:
                    self.speed_slider.setValue(2) # Default to 1.0
                    self.spin_speed_multiplier = 1.0
                
                self.speed_label.setText(f"{self.spin_speed_multiplier}x")
                
                if self.wheel_mode == 'image':
                    self.mode_image_radio.setChecked(True)
                    self.image_mode_container.setVisible(True)
                    self.classic_mode_container.setVisible(False)
                else:
                    self.mode_classic_radio.setChecked(True)
                    self.image_mode_container.setVisible(False)
                    self.classic_mode_container.setVisible(True)
                    
                if hasattr(self, 'image_path_label'):
                    self.image_path_label.setText(os.path.basename(self.pointer_image_path))
                
                if self.pointer_image_path and os.path.exists(self.pointer_image_path):
                     if hasattr(self, 'calibrate_btn'):
                        self.calibrate_btn.setEnabled(True)
                    
                if "last_file" in settings and isinstance(settings["last_file"], str) and os.path.exists(settings["last_file"]):
                    self.current_file_path = settings["last_file"]
                    try:
                        with open(settings["last_file"], 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        self.items = []
                        for item_data in data:
                            # 驗證音效路徑是否存在
                            sound_file = item_data.get('sound_file', "")
                            sound_enable = item_data.get('sound_enable', False)
                            if sound_file and not os.path.exists(sound_file):
                                sound_file = ""
                                sound_enable = False
                            
                            self.items.append({
                                'name': item_data['name'],
                                'weight': float(item_data['weight']),
                                'color': QColor(item_data['color']),
                                'enabled': item_data.get('enabled', True),
                                'sound_enable': sound_enable,
                                'sound_file': sound_file
                            })
                        self.update_list()
                        items_loaded = True
                    except Exception as e:
                        print(f"Error loading last file: {e}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "錯誤", f"載入失敗: {str(e)}")
        
        # If items not loaded (settings missing, last_file missing, or load failed), try autosave
        if not items_loaded:
             autosave_path = external_path("autosave.json")
             if os.path.exists(autosave_path):
                 print(f"DEBUG: Auto-loading {autosave_path}")
                 try:
                    with open(autosave_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self.items = []
                    for item_data in data:
                        # 驗證音效路徑是否存在
                        sound_file = item_data.get('sound_file', "")
                        sound_enable = item_data.get('sound_enable', False)
                        if sound_file and not os.path.exists(sound_file):
                            sound_file = ""
                            sound_enable = False
                        
                        self.items.append({
                            'name': item_data['name'],
                            'weight': float(item_data['weight']),
                            'color': QColor(item_data['color']),
                            'enabled': item_data.get('enabled', True),
                            'sound_enable': sound_enable,
                            'sound_file': sound_file
                        })
                    self.update_list()
                 except:
                     pass

    def toggle_wheel(self):
        """切換轉盤視窗"""
        if self.wheel_window is None:
            active_items = [i for i in self.items if i.get('enabled', True)]
            if not active_items:
                msg = QMessageBox(self)
                msg.setWindowTitle("警告")
                msg.setText("請先新增並啟用至少一個選項")
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowModality(Qt.WindowModal)
                msg.exec()
                return
            self.wheel_window = WheelWindow()
            self.update_wheel()
            self.wheel_window.show()
            self.wheel_window.spin_finished.connect(self.add_history_record)
            self.wheel_window.window_closed.connect(self.on_wheel_closed)
            
            # 立即應用所有設定 (包含速度)
            self.update_wheel_settings()
            
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

    def on_mode_changed(self, button):
        self.wheel_mode = "image" if self.mode_image_radio.isChecked() else "classic"
        self.image_mode_container.setVisible(self.wheel_mode == "image")
        self.classic_mode_container.setVisible(self.wheel_mode == "classic")
        self.update_wheel_settings()
        self.save_settings()

    def on_classic_settings_changed(self):
        """經典模式設定變更"""
        self.classic_pointer_angle = self.pointer_angle_combo.currentIndex() * 45
        self.center_text = self.center_text_input.text()
        self.update_wheel_settings()

    def select_pointer_image(self):
        """選擇指針圖片"""
        dialog = QFileDialog(self, "選擇指針圖片", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        dialog.setWindowModality(Qt.WindowModal)
        
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                src_path = files[0]
                
                # 確保外部 PIC 資料夾存在
                pic_dir = external_path("PIC")
                if not os.path.exists(pic_dir):
                    try:
                        os.makedirs(pic_dir)
                    except:
                        pass # Should handle permission error?
                        
                # 複製檔案到 PIC 資料夾
                try:
                    filename = os.path.basename(src_path)
                    dest_path = os.path.join(pic_dir, filename)
                    
                    # 避免同名覆蓋確認? 使用者需求是簡單複製
                    shutil.copy2(src_path, dest_path)
                    
                    self.pointer_image_path = dest_path
                    self.image_path_label.setText(filename)
                    self.calibrate_btn.setEnabled(True)
                    self.update_wheel_settings()
                    self.save_settings()
                    
                    QMessageBox.information(self, "成功", f"圖片已複製到: PIC/{filename}")
                    
                except Exception as e:
                    msg = QMessageBox(self)
                    msg.setWindowTitle("錯誤")
                    msg.setText(f"複製圖片失敗: {str(e)}")
                    msg.setIcon(QMessageBox.Critical)
                    msg.setWindowModality(Qt.WindowModal)
                    msg.exec()
                    # Fallback to source path? Or just fail? 
                    # Use source path as fallback if copy fails
                    self.pointer_image_path = src_path
                    self.image_path_label.setText(os.path.basename(src_path))
                    self.update_wheel_settings()
                    self.save_settings()

    def open_calibration_dialog(self):
        """開啟圖片修正視窗"""
        active_items = [i for i in self.items if i.get('enabled', True)]
        # 如果沒有啟用的項目，則使用預設佔位符項目，讓使用者能看到東西
        if not active_items:
            active_items = [{'name': '測試', 'weight': 1, 'color': QColor('blue'), 'enabled': True}]

        dialog = ImageCalibrationDialog(self, active_items, self.pointer_image_path, self.pointer_angle_offset, self.pointer_scale)
        dialog.setWindowModality(Qt.WindowModal)
        if dialog.exec():
            self.pointer_angle_offset, self.pointer_scale = dialog.get_result()
            self.update_wheel_settings()
            self.pointer_angle_offset, self.pointer_scale = dialog.get_result()
            self.update_wheel_settings()
            self.save_settings()

    def toggle_pointer_line(self):
        """切換綠線顯示"""
        self.show_pointer_line = self.pointer_line_btn.isChecked()
        self.update_pointer_line_btn_state()
        self.update_wheel_settings()
        self.save_settings()

    def update_pointer_line_btn_state(self):
        """更新綠線按鈕狀態"""
        self.pointer_line_btn.setChecked(self.show_pointer_line)
        if self.show_pointer_line:
            self.pointer_line_btn.setText("輔助線: 開")
            self.pointer_line_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        else:
            self.pointer_line_btn.setText("輔助線: 關")
            self.pointer_line_btn.setStyleSheet("background-color: #f44336; color: white;")

    def update_wheel(self):
        """更新轉盤設定"""
        if self.wheel_window:
            active_items = [i for i in self.items if i.get('enabled', True)]
            self.wheel_window.update_settings(
                active_items, 
                self.border_enabled_check(), 
                self.border_color, 
                self.result_text_color,
                self.result_bg_color,
                self.separator_check.isChecked(),
                self.sound_check.isChecked(),
                self.finish_sound_check.isChecked(),
                int(self.opacity_slider.value() * 2.55),
                self.show_pointer_line,
                self.continuous_sound_check.isChecked()
            )
            self.wheel_window.set_classic_settings(self.classic_pointer_angle, self.center_text)
            # 應用新的模式設定
            self.wheel_window.set_mode(
                self.wheel_mode,
                self.pointer_image_path,
                self.pointer_angle_offset,
                self.pointer_scale
            )
            
            # 設定置頂/工具
            self.wheel_window.set_window_mode(self.window_mode)
            
            # 同步速度 (僅在未旋轉時更新，避免影響目前物理運算，雖物理運算其實已鎖定初速)
            if not self.wheel_window.is_spinning:
                self.wheel_window.spin_speed_multiplier = self.spin_speed_multiplier


    def on_window_mode_changed(self, index):
        """視窗模式變更時的回調"""
        modes = ['top', 'normal']
        if 0 <= index < len(modes):
            self.window_mode = modes[index]
            self.update_wheel_settings()


    def import_custom_sound(self):
        """匯入自訂音效"""
        dialog = QFileDialog(self, "匯入音效", "", "Audio Files (*.mp3 *.wav)")
        dialog.setWindowModality(Qt.WindowModal)
        
        if dialog.exec():
            files = dialog.selectedFiles()
            if not files:
                return
            
            src_path = files[0]
            
            # 檢查檔案大小 (10MB)
            if os.path.getsize(src_path) > 10 * 1024 * 1024:
                msg = QMessageBox(self)
                msg.setWindowTitle("錯誤")
                msg.setText("檔案大小不能超過 10MB")
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowModality(Qt.WindowModal)
                msg.exec()
                return

            # 選擇音效類型
            items = ["旋轉音效 (Tick)", "持續音效 (Loop)", "結束音效 (Finish)"]
            
            input_dialog = QInputDialog(self)
            input_dialog.setWindowModality(Qt.WindowModal)
            input_dialog.setWindowTitle("選擇音效類型")
            input_dialog.setLabelText("請選擇要設定的音效:")
            input_dialog.setComboBoxItems(items)
            input_dialog.setComboBoxEditable(False)
            
            ok = False
            item = ""
            if input_dialog.exec() == QInputDialog.Accepted:
                 item = input_dialog.textValue()
                 ok = True
            
            role = ""
            if ok and item:
                if "Tick" in item:
                    role = "tick"
                elif "Loop" in item:
                    role = "loop"
                elif "Finish" in item:
                    role = "finish"
            else:
                return # User cancelled

            # 儲存檔案
            try:
                sound_dir = external_path("SOUND")
                if not os.path.exists(sound_dir):
                    os.makedirs(sound_dir)
                
                # 取得副檔名
                _, ext = os.path.splitext(src_path)
                ext = ext.lower()
                
                target_filename = f"{role}{ext}"
                target_path = os.path.join(sound_dir, target_filename)
                
                # 偵測衝突
                other_ext = '.wav' if ext == '.mp3' else '.mp3'
                conflict_path = os.path.join(sound_dir, f"{role}{other_ext}")
                
                # Release locks if WheelWindow exists
                if self.wheel_window:
                    self.wheel_window.release_audio_locks()

                if os.path.exists(conflict_path):
                    # 發現不同格式的同名檔案，詢問使用者
                    dlg = SoundConflictDialog(self, conflict_path, src_path)
                    if dlg.exec():
                        if dlg.selected_action == 'replace_new':
                            # 使用新檔 -> 刪除舊檔 (衝突檔)
                            try:
                                os.remove(conflict_path)
                            except Exception as e:
                                print(f"Error removing conflict file: {e}")
                            # 繼續執行複製 (覆蓋同名同格式若是有的話)
                        elif dlg.selected_action == 'keep_old':
                            # 保留舊檔 -> 不執行複製
                            # Reload sounds since we released them
                            if self.wheel_window:
                                self.wheel_window.load_sounds()
                            return
                    else:
                        # 取消
                        # Reload sounds since we released them
                        if self.wheel_window:
                            self.wheel_window.load_sounds()
                        return
                
                # 執行複製 (若有同名同格式會覆蓋)
                if os.path.exists(target_path):
                    try:
                        os.remove(target_path)
                    except:
                        pass
                shutil.copy2(src_path, target_path)
                
                # 更新轉盤
                if self.wheel_window:
                    self.wheel_window.load_sounds()
                
                msg = QMessageBox(self)
                msg.setWindowTitle("成功")
                msg.setText(f"已匯入為 {item}")
                msg.setIcon(QMessageBox.Information)
                msg.setWindowModality(Qt.WindowModal)
                msg.exec()
                
            except Exception as e:
                msg = QMessageBox(self)
                msg.setWindowTitle("錯誤")
                msg.setText(f"匯入失敗: {str(e)}")
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowModality(Qt.WindowModal)
                msg.exec()
        
    def on_opacity_changed(self):
        val = self.opacity_slider.value()
        self.result_opacity = int(val * 2.55)
        self.opacity_label.setText(f"{val}%")
        
        if self.wheel_window:
            self.wheel_window.result_opacity = self.result_opacity
            self.wheel_window.preview_opacity()

    def on_speed_changed(self):
        """旋轉速度滑桿改變時的回調"""
        idx = self.speed_slider.value()
        if 0 <= idx < len(self.allowed_speeds):
            self.spin_speed_multiplier = self.allowed_speeds[idx]
            self.speed_label.setText(f"{self.spin_speed_multiplier}x")
        
        if self.wheel_window:
            self.wheel_window.spin_speed_multiplier = self.spin_speed_multiplier

    def on_font_size_changed(self):
        """轉盤文字大小改變時的回調"""
        val = self.font_size_spin.value()
        self.wheel_font_size = val
        if self.wheel_window:
            self.wheel_window.font_size = val
            self.wheel_window.update()
            
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

    def closeEvent(self, event):
        """視窗關閉事件"""
        # 自動儲存至 autosave.json
        try:
            autosave_path = external_path("autosave.json")
            data = []
            for item in self.items:
                data.append({
                    'name': item['name'],
                    'weight': item['weight'],
                    'color': item['color'].name(),
                    'enabled': item.get('enabled', True),
                    'sound_enable': item.get('sound_enable', False),
                    'sound_file': item.get('sound_file', "")
                })
            with open(autosave_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

        self.save_settings()
        if self.wheel_window:
            self.wheel_window.close()
        super().closeEvent(event)
