import random
import json
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, QListWidget, 
                               QListWidgetItem, QColorDialog, QMessageBox, QGroupBox, QFormLayout, 
                               QFileDialog, QCheckBox, QFrame, QTextEdit)
from PySide6.QtGui import QColor, QFont, QPainter, QBrush, QPen, QCursor
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from collections import Counter 
from wheel_window import WheelWindow

SETTINGS_FILE = "settings.json"
