import math
import random
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QMessageBox, QLabel, QListWidget, QListWidgetItem, QHBoxLayout, QFrame
from PySide6.QtGui import QPainter, QBrush, QPen, QColor, QPainterPath, QFont, QPolygonF, QCursor, QTextOption, QMouseEvent, QPixmap, QTransform
from PySide6.QtCore import Qt, QPointF, QRectF, QPropertyAnimation, QEasingCurve, Property, Signal, QRect, QTimer, QSize, QTime
import winsound
import os
import struct
import io
from utils import resource_path

class WavPitchShifter:
    """WAV 音高調整工具"""
    @staticmethod
    def shift_pitch(wav_data, target_freq_offset=0):
        try:
            data = bytearray(wav_data)
            if len(data) < 44:
                return None
            
            original_rate = struct.unpack('<I', data[24:28])[0]
            multiplier = target_freq_offset / 600.0
            if multiplier < 0.5:
                multiplier = 0.5
            if multiplier > 2.0:
                multiplier = 2.0
            
            new_rate = int(original_rate * multiplier)
            struct.pack_into('<I', data, 24, new_rate)
            return bytes(data)
        except:
            return None

class WheelWindow(QWidget):
    """轉盤視窗Class"""
    spin_finished = Signal(str)
    weights_changed = Signal()
    window_closed = Signal()

    def __init__(self, edit_mode=False):
        super().__init__()
        self.edit_mode = edit_mode
        self.setWindowTitle("轉盤")
        self.resize(500, 600)
        
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        if self.edit_mode:
            self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        self.show_resize_grip = True
        self.is_resizing_window = False
        
        self.grip_timer = QTimer(self)
        self.grip_timer.setInterval(10000)
        self.grip_timer.timeout.connect(self.hide_grip)
        self.grip_timer.start()
        
        self.result_timer = QTimer(self)
        self.result_timer.setSingleShot(True)
        self.result_timer.setInterval(3000)
        self.result_timer.timeout.connect(self.hide_result)
        
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(1500)
        self.preview_timer.timeout.connect(self.end_preview_opacity)
        self.is_previewing_opacity = False
        
        self.items = []
        self._rotation_angle = 0
        self.result_text = ""
        self.result_color = QColor(Qt.white)
        self.result_bg_color = QColor(Qt.black)
        self.border_enabled = True
        self.border_color = QColor(Qt.white)
        self.separator_enabled = True
        self.sound_enabled = False
        self.finish_sound_enabled = False
        self.result_opacity = 150
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.physics_update)
        self.is_spinning = False
        self.rotation_speed = 0
        self.deceleration = 0
        self.spin_speed_mult = 1.0
        
        self.old_pos = None
        self.drag_separator_index = -1
        self.hover_separator_index = -1
        self.setMouseTracking(True)
        self.is_dragging_window = False
        
        self.last_pointer_index = -1
        self.last_sound_time = QTime.currentTime()
        
        self.tick_sound_data = None
        self.load_tick_sound()

        self.wheel_font = QFont("Microsoft JhengHei")
        self.wheel_font.setBold(True)
        self.text_doc_option = QTextOption()
        self.text_doc_option.setWrapMode(QTextOption.WordWrap)
        self.text_doc_option.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        # 新功能：圖片指針模式
        self.wheel_mode = "classic"
        self.pointer_image_path = ""
        self.pointer_pixmap = None
        self.pointer_angle_offset = 0
        self.pointer_scale = 1.0
        self.spin_speed_multiplier = 1.0 # 速度倍率
        self.classic_pointer_angle = 0
        self.center_text = "GO"

    def set_classic_settings(self, angle, text):
        """設定經典模式參數"""
        self.classic_pointer_angle = angle
        self.center_text = text
        self.update()

    def set_mode(self, mode, image_path, angle_offset, scale=1.0):
        """設定轉盤模式"""
        self.wheel_mode = mode
        self.pointer_image_path = image_path
        self.pointer_angle_offset = angle_offset
        self.pointer_scale = scale
        self.load_pointer_image()
        self.update()

    def load_pointer_image(self):
        """載入指針圖片"""
        if self.pointer_image_path and os.path.exists(self.pointer_image_path):
            self.pointer_pixmap = QPixmap(self.pointer_image_path)
        else:
            self.pointer_pixmap = None

    def load_tick_sound(self):
        """載入滴答音效"""
        wav_path = resource_path("tick.wav")
        if os.path.exists(wav_path):
            try:
                with open(wav_path, 'rb') as f:
                    self.tick_sound_data = f.read()
            except:
                self.tick_sound_data = None
        else:
            self.tick_sound_data = None
        
    def preview_opacity(self):
        """預覽透明度"""
        self.is_previewing_opacity = True
        self.preview_timer.start()
        self.update()

    def end_preview_opacity(self):
        """結束透明度預覽"""
        self.is_previewing_opacity = False
        self.update()

    def hide_result(self):
        """隱藏結果文字"""
        self.result_text = ""
        self.update()

    def hide_grip(self):
        """隱藏調整大小控制點"""
        self.show_resize_grip = False
        self.update()
        
    def show_grip_func(self):
        """顯示調整大小控制點"""
        self.show_resize_grip = True
        self.update()
        self.reset_grip_timer()
        
    def reset_grip_timer(self):
        """重置控制點計時器"""
        self.grip_timer.start()

    def update_settings(self, items, border_enabled, border_color, result_color, result_bg_color, separator_enabled=True, sound_enabled=False, finish_sound_enabled=False, result_opacity=150):
        """更新轉盤設定"""
        self.items = items
        self.border_enabled = border_enabled
        self.border_color = border_color
        self.result_color = result_color
        self.result_bg_color = result_bg_color
        self.separator_enabled = separator_enabled
        self.sound_enabled = sound_enabled
        self.finish_sound_enabled = finish_sound_enabled
        self.result_opacity = result_opacity
        self.update()

    def get_rotation_angle(self):
        """取得旋轉角度"""
        return self._rotation_angle

    def set_rotation_angle(self, angle):
        """設定旋轉角度並處理音效"""
        self._rotation_angle = angle
        
        if self.sound_enabled:
            # 計算相對於轉盤的有效指針角度
            if self.wheel_mode == "image":
                # 圖片模式：統一邏輯：指針角度 = (90 + 旋轉角度 + 偏移量) % 360
                # 基準 90 (北方) 確保預設指向頂部。
                effective_angle = (90 + angle + self.pointer_angle_offset) % 360
            else:
                # 經典模式：轉盤旋轉。
                # 有效角度 = (指針角度 - 旋轉角度) % 360
                effective_angle = (self.classic_pointer_angle - angle) % 360
                
            total_weight = sum(item['weight'] for item in self.items)
            if total_weight > 0:
                current_angle_iter = 0
                found_index = -1
                for i, item in enumerate(self.items):
                    span = (item['weight'] / total_weight) * 360
                    if current_angle_iter <= effective_angle < current_angle_iter + span:
                        found_index = i
                        break
                    current_angle_iter += span
                    
                if found_index != -1 and found_index != self.last_pointer_index:
                    if self.last_pointer_index != -1:
                        current_time = QTime.currentTime()
                        ms_diff = self.last_sound_time.msecsTo(current_time)
                        self.last_sound_time = current_time
                        
                        if ms_diff < 1:
                            ms_diff = 1
                        
                        freq = 400 + int(8000 / ms_diff)
                        if freq > 1500:
                            freq = 1500
                        if freq < 200:
                            freq = 200
                        
                        self.play_tick_sound(freq)
                    else:
                        self.last_sound_time = QTime.currentTime()
                        
                    self.last_pointer_index = found_index
        self.update()

    def play_tick_sound(self, freq=600):
        """播放滴答音效"""
        try:
            wav_path = resource_path("tick.wav")
            if self.sound_enabled and os.path.exists(wav_path):
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif self.sound_enabled:
                winsound.Beep(600, 20)
        except Exception as e:
            pass

    def play_finish_sound(self):
        """播放結束音效"""
        try:
            if not self.finish_sound_enabled:
                return
            
            wav_path = resource_path("finish.wav")
            if os.path.exists(wav_path):
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                winsound.Beep(1000, 200)
        except:
            pass

    def auto_spin(self, speed_multiplier=1.0):
        """自動旋轉（用於連抽）"""
        if self.is_spinning:
            return
        self.start_spin(speed_multiplier)

    def start_spin(self, speed_multiplier=1.0):
        """開始旋轉"""
        self.result_text = ""
        self.spin_speed_mult = speed_multiplier
        # 應用使用者設定的旋轉速度倍率
        base_speed = random.uniform(20.0, 35.0)
        self.rotation_speed = base_speed * speed_multiplier * self.spin_speed_multiplier
        # 減速邏輯讓「轉速越快，持續時間越短」
        # 如果倍率 > 1 (快)，我們希望它更快停止 -> 更高的減速率。
        # 如果倍率 < 1 (慢)，我們希望它轉得更久/更慢 -> 更低的減速率。 
        # 減速率隨 速度^2 變化，則持續時間 ~ 速度 / 速度^2 ~ 1/速度。
        # 這給出一種線性反比關係（速度增加時持續時間減少）。
        
        base_decel = random.uniform(0.15, 0.25)
        
        # 依倍率平方縮放減速率，有效縮短較高速度下的旋轉時間。
        total_multiplier = speed_multiplier * self.spin_speed_multiplier
        self.deceleration = base_decel * (total_multiplier ** 2.0)
        
        self.is_spinning = True
        self.timer.start(25)

    def physics_update(self):
        """物理更新（旋轉動畫）"""
        if not self.is_spinning:
            self.timer.stop()
            return

        new_angle = self._rotation_angle + self.rotation_speed
        self.set_rotation_angle(new_angle % 360)
        
        self.rotation_speed -= self.deceleration
        
        if self.rotation_speed <= 0:
            self.rotation_speed = 0
            self.is_spinning = False
            self.timer.stop()
            self.on_spin_finished()

    def on_spin_finished(self):
        """旋轉結束處理"""
        final_angle = self._rotation_angle
        if self.wheel_mode == "image":
             # 圖片模式：統一邏輯 (90 為基準)。
             # 邏輯線 (獲勝者) 是純旋轉。偏移量僅影響圖片視覺。
             effective_angle = (90 + final_angle) % 360
        else:
             # 經典模式
             effective_angle = (self.classic_pointer_angle - final_angle) % 360
        
        current_angle = 0
        total_weight = sum(item['weight'] for item in self.items)
        
        winner_name = ""
        for item in self.items:
            span_angle = (item['weight'] / total_weight) * 360
            
            # Check range
            if current_angle <= effective_angle < current_angle + span_angle:
                winner_name = item['name']
                break
            current_angle += span_angle
            
            
        print(f"WH: {winner_name}")
        self.result_text = f"{winner_name} "
        self.update()
        self.spin_finished.emit(winner_name)
        self.play_finish_sound()
        self.result_timer.start()

    def spin(self):
        """開始旋轉（標準速度）"""
        self.start_spin()

    def paintEvent(self, event):
        """繪製轉盤"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        w = min(rect.width(), rect.height())
        wheel_rect = QRectF((rect.width() - w)/2, 0, w, w)
        center = wheel_rect.center()
        radius = w / 2 - 25
        self.wheel_center = center
        self.wheel_radius = radius
        
        if not self.items:
            return
        total_weight = sum(item['weight'] for item in self.items)
        if total_weight <= 0:
            return

        # Rotation Mode Check
        if self.wheel_mode == "image":
            # 圖片模式：轉盤起始角度固定為 0。
            # 指針圖片旋轉。
            start_angle = 0 # 固定背景
        else:
            # 經典模式：轉盤旋轉。
            start_angle = self._rotation_angle
        
        if self.border_enabled:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(self.border_color, 4))
            painter.drawEllipse(center, radius + 2, radius + 2)

        separator_angles = []
        for i, item in enumerate(self.items):
            weight = item['weight']
            span_angle = (weight / total_weight) * 360 if total_weight > 0 else 0
            
            painter.setBrush(QBrush(item['color']))
            if self.separator_enabled:
                painter.setPen(QPen(self.border_color, 2))
            else:
                painter.setPen(Qt.NoPen)
            
            painter.drawPie(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2), 
                            int(start_angle * 16), int(span_angle * 16))
            
            mid_angle = start_angle + span_angle / 2
            painter.save()
            painter.translate(center)
            painter.rotate(-mid_angle)
            
            if item['color'].lightness() < 128:
                painter.setPen(Qt.white)
            else:
                painter.setPen(Qt.black)
            
            calc_size = int(radius / 15)
            font_size = max(8, calc_size)
            if font_size <= 0: font_size = 8
            try:
                self.wheel_font.setPointSize(font_size)
            except:
                self.wheel_font.setPointSize(8)
            painter.setFont(self.wheel_font)
            
            text_rect_width = radius * 0.55
            text_rect_height = radius * 0.35
            text_rect = QRectF(radius * 0.35, -text_rect_height/2, text_rect_width, text_rect_height)
            
            raw_text = item['name']
            words = raw_text.split(' ')
            lines = []
            current_line = ""
            limit = 9
            
            for word in words:
                if len(word) > limit:
                    if current_line:
                        lines.append(current_line)
                        current_line = ""
                    
                    for k in range(0, len(word), limit):
                        lines.append(word[k:k+limit])
                    continue
                
                test_line = (current_line + " " + word).strip() if current_line else word
                if len(test_line) <= limit:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            
            if current_line:
                lines.append(current_line)
            
            display_text = "\n".join(lines)
            painter.drawText(text_rect, display_text, self.text_doc_option)
            painter.restore()
            
            start_angle += span_angle
            separator_angles.append(start_angle % 360)

        # 繪製圖片指針

        if self.wheel_mode == "image" and self.pointer_pixmap:
            painter.save()
            painter.translate(center)

            # 指針角度 = (90 + 旋轉角度 + 偏移量) % 360
            image_angle = (90 + self._rotation_angle + self.pointer_angle_offset) % 360
            painter.rotate(-image_angle)
            
            # 將圖片頂部對齊到局部 X 軸 (綠線/邏輯方向相對於其本身)
            # 圖片頂部是局部 -Y。旋轉(90) 順時針將 -Y 移動到 +X。
            painter.rotate(90)
            
            # 繪製圖片置中
            target_h = radius * 1.0 * getattr(self, 'pointer_scale', 1.0)
            target_w = target_h * (self.pointer_pixmap.width() / self.pointer_pixmap.height())
            
            painter.drawPixmap(QRectF(-target_w/2, -target_h/2, target_w, target_h), self.pointer_pixmap, self.pointer_pixmap.rect())
            
            painter.restore()

            # 偵錯：繪製邏輯線 (綠色)
            # 邏輯線代表「獲勝者偵測角度」。

            logic_angle = (90 + self._rotation_angle) % 360
            
            painter.save()
            painter.translate(center)
            painter.rotate(-logic_angle)
            painter.setPen(QPen(Qt.green, 5)) 
            painter.drawLine(0, 0, radius, 0)
            painter.restore()

        if self.edit_mode and len(self.items) > 1:
            for i, angle in enumerate(separator_angles):
                if i == len(self.items) - 1:
                    continue
                
                rad = math.radians(angle)
                hx = center.x() + radius * math.cos(rad)
                hy = center.y() - radius * math.sin(rad)
                painter.setPen(Qt.NoPen)
                
                if i == self.hover_separator_index or i == self.drag_separator_index:
                    painter.setBrush(Qt.yellow)
                    handle_size = 14
                else:
                    painter.setBrush(Qt.white)
                    handle_size = 10
                painter.drawEllipse(QPointF(hx, hy), handle_size, handle_size)

        if not self.edit_mode and self.wheel_mode != "image":
            painter.save()
            painter.translate(center)
            # 負向旋轉以匹配坐標系（逆時針為正）
            # 但 Qt rotate 是順時針。
            # 0度是東。若要指下(90)，需順時針90。
            painter.rotate(self.classic_pointer_angle)
            
            pointer_size = 25
            pointer_fill = QColor(255, 69, 0)
            painter.setBrush(QBrush(pointer_fill))
            painter.setPen(QPen(Qt.white, 2))
            
            # 使用局部坐標畫指針 (原本是在東邊)
            # 原本邏輯：center.x() + radius... 這是在全局坐標。
            # 現在 translate 到 center 了，所以用 (radius, 0)
            
            p1 = QPointF(radius - 5, 0)
            p2 = QPointF(radius + pointer_size, -15)
            p3 = QPointF(radius + pointer_size, 15)
            painter.drawPolygon(QPolygonF([p1, p2, p3]))
            painter.restore()
        
        if self.wheel_mode != "image" or self.edit_mode:
            painter.setBrush(QBrush(Qt.white))
            painter.setPen(QPen(Qt.black, 2))
            painter.drawEllipse(center, 30, 30)
            
            painter.setPen(Qt.black)
            font = painter.font()
            try:
                font.setPointSize(10)
            except:
                pass
            font.setBold(True)
            painter.setFont(font)
            btn_text = "關閉" if self.edit_mode else self.center_text
            painter.drawText(QRectF(center.x() - 30, center.y() - 30, 60, 60), Qt.AlignCenter, btn_text)
        
        should_show_box = False
        box_text = ""
        box_rect = QRectF(0, rect.height() - 100, rect.width(), 80)
        font_size = 24
        
        if self.result_text:
            should_show_box = True
            box_text = self.result_text
        elif self.is_resizing_window:
            should_show_box = True
            box_text = f"大小: {self.width()} x {self.height()}"
            font_size = 18
        elif self.is_previewing_opacity:
            should_show_box = True
            box_text = f"透明度預覽"
            font_size = 18

        if should_show_box:
            bg_color = QColor(self.result_bg_color)
            bg_color.setAlpha(self.result_opacity)
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(box_rect, 15, 15)
            painter.setPen(self.result_color)
            font = painter.font()
            font.setFamily("Microsoft JhengHei")
            try:
                valid_size = max(8, int(font_size))
                font.setPointSize(valid_size)
            except:
                pass
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(box_rect, Qt.AlignCenter, box_text)


        if self.wheel_mode == "image":
             curr_angle = (90 + self._rotation_angle + self.pointer_angle_offset) % 360
        else:
             curr_angle = (self.classic_pointer_angle - self._rotation_angle) % 360
        
        curr_winner = ""
        c_iter = 0
        tot_w = sum(i['weight'] for i in self.items)
        if tot_w > 0:
            for i in self.items:
                sp = (i['weight']/tot_w)*360
                if c_iter <= curr_angle < c_iter+sp:
                    curr_winner = i['name']
                    break
                c_iter += sp
        


        if not self.edit_mode and self.show_resize_grip:
            grip_radius = 10
            gx = rect.width() - 20
            gy = rect.height() - 20
            self.grip_rect = QRectF(gx - grip_radius, gy - grip_radius, grip_radius*2, grip_radius*2)
            painter.setBrush(QBrush(QColor(255, 255, 255, 150)))
            painter.setPen(QPen(Qt.black, 1))
            painter.drawEllipse(self.grip_rect)

    def mousePressEvent(self, event):
        """滑鼠按下事件"""
        if self.is_spinning:
            return

        self.reset_grip_timer()
        if event.button() == Qt.RightButton:
            self.hide_grip()
            return
            
        if event.button() == Qt.LeftButton:
            if not self.edit_mode and self.show_resize_grip and hasattr(self, 'grip_rect'):
                if self.grip_rect.contains(event.position()):
                    self.is_resizing_window = True
                    self.old_pos = event.globalPosition().toPoint()
                    self.update()
                    return

            if hasattr(self, 'wheel_center'):
                dist_sq = (event.position().x() - self.wheel_center.x())**2 + (event.position().y() - self.wheel_center.y())**2
                
                # Check based on mode
                clicked = False
                if self.edit_mode:
                    if dist_sq < 30**2: # 關閉按鈕
                        self.close()
                        return
                elif self.wheel_mode == "image":
                    # 檢查是否點擊在圖片內 (大約半徑 * 0.5)
                    # 圖片高度為 半徑 * 1.0，所以半高為 半徑 * 0.5
                    if hasattr(self, 'wheel_radius'):
                        click_radius = self.wheel_radius * 0.5
                        if dist_sq < click_radius**2:
                            clicked = True
                else: # 經典模式 GO 按鈕
                    if dist_sq < 30**2:
                        clicked = True
                
                if clicked:
                    self.spin()
                    return

            if self.edit_mode:
                idx = self.get_hover_separator_index(event.position())
                if idx != -1:
                    self.drag_separator_index = idx
                    return
            
            self.old_pos = event.globalPosition().toPoint()
            self.is_dragging_window = True
            if self.result_text:
                self.result_text = ""
                self.update()

    def mouseDoubleClickEvent(self, event):
        """滑鼠雙擊事件"""
        if hasattr(self, 'wheel_center'):
            if (event.position().x() - self.wheel_center.x())**2 + (event.position().y() - self.wheel_center.y())**2 >= 30**2:
                self.show_grip_func()

    def mouseMoveEvent(self, event):
        """滑鼠移動事件"""
        if self.grip_timer.isActive():
            self.grip_timer.start()

        if self.edit_mode:
            if self.drag_separator_index != -1:
                dx = event.position().x() - self.wheel_center.x()
                dy = self.wheel_center.y() - event.position().y()
                angle_rad = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_rad)
                if angle_deg < 0:
                    angle_deg += 360
                self.handle_drag(angle_deg)
            else:
                self.hover_separator_index = self.get_hover_separator_index(event.position())
                if self.hover_separator_index != -1:
                    self.setCursor(Qt.PointingHandCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
                self.update()
        else:
            if self.is_resizing_window and self.old_pos:
                delta = event.globalPosition().toPoint() - self.old_pos
                self.resize(self.width() + delta.x(), self.height() + delta.y())
                self.old_pos = event.globalPosition().toPoint()
                self.update()
                return
            if self.is_dragging_window and self.old_pos:
                delta = event.globalPosition().toPoint() - self.old_pos
                self.move(self.pos() + delta)
                self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        """滑鼠釋放事件"""
        if self.edit_mode:
            self.drag_separator_index = -1
        else:
            self.old_pos = None
            self.is_dragging_window = False
            self.is_resizing_window = False
            self.update()
            
    def resizeEvent(self, event):
        """視窗大小改變事件"""
        print(f"Wheel Window Size: {self.width()} x {self.height()}")
        super().resizeEvent(event)
    
    def closeEvent(self, event):
        """視窗關閉事件"""
        self.window_closed.emit()
        super().closeEvent(event)

    def get_hover_separator_index(self, pos):
        """取得滑鼠懸停的分隔線索引"""
        if not self.items:
            return -1
        total_weight = sum(item['weight'] for item in self.items)
        start_angle = self._rotation_angle
        handle_radius = self.wheel_radius
        threshold = 20
        
        for i, item in enumerate(self.items):
            if i == len(self.items) - 1:
                continue
            weight = item['weight']
            span_angle = (weight / total_weight) * 360 if total_weight > 0 else 360
            start_angle += span_angle
            angle = start_angle % 360
            rad = math.radians(angle)
            hx = self.wheel_center.x() + handle_radius * math.cos(rad)
            hy = self.wheel_center.y() - handle_radius * math.sin(rad)
            if (pos.x() - hx)**2 + (pos.y() - hy)**2 < threshold**2:
                return i
        return -1

    def handle_drag(self, current_mouse_angle):
        """處理拖曳分隔線以調整權重"""
        try:
            i = self.drag_separator_index
            if i < 0:
                return
            n = len(self.items)
            idx_current = i
            idx_next = (i + 1) % n
            item_current = self.items[idx_current]
            item_next = self.items[idx_next]
            total_weight = sum(item['weight'] for item in self.items)
            weight_before = 0
            for k in range(idx_current):
                weight_before += self.items[k]['weight']
            angle_start_current_rel = (weight_before / total_weight) * 360
            angle_start_current_abs = (self._rotation_angle + angle_start_current_rel) % 360
            diff = current_mouse_angle - angle_start_current_abs
            while diff < 0:
                diff += 360
            while diff >= 360:
                diff -= 360
            new_span_current = diff
            combined_weight = item_current['weight'] + item_next['weight']
            combined_span = (combined_weight / total_weight) * 360
            min_span = (total_weight * 0.005 / total_weight) * 360
            if new_span_current < min_span:
                return
            if new_span_current > combined_span - min_span:
                return
            new_weight_current = (new_span_current / 360.0) * total_weight
            new_weight_next = combined_weight - new_weight_current
            if new_weight_current < 0 or new_weight_next < 0:
                return
            item_current['weight'] = new_weight_current
            item_next['weight'] = new_weight_next
            self.weights_changed.emit()
            self.update()
        except Exception as e:
            print(f"Error handling drag: {e}")

    def keyPressEvent(self, event):
        """處理鍵盤事件"""
        if event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and event.key() == Qt.Key_F12:
            self.close()
        super().keyPressEvent(event)
