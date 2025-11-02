"""
Beautiful OpenCV Control Panel - Version 10.2
Modern, elegant GUI for multi-camera OpenCV processing with auto-capture

NEW IN V10.2:
- TWO-WINDOW DESIGN: Separate feed window and floating control panel
- Soft pink/lavender theme with BLACK text (high contrast, no hot pink!)
- Fixed grid mode with proper error handling for multiple cameras
- Robust view mode switching (single <-> grid)
- All the great features from v10.1 (auto-capture, PID, etc.)

Author: Created for Chloe's germanium zone refining project
"""

import cv2
import customtkinter as ctk
from tkinter import Toplevel
from PIL import Image, ImageTk
import numpy as np
from datetime import datetime
import os
import threading
import json
import platform
import sys
import io
import time
from tkinter import filedialog

# Try to import PID controller (optional)
try:
    from furnace_pid_controller import FurnaceMotorController, MoltenZonePIDController
    HAS_PID = True
except ImportError:
    HAS_PID = False
    print("Note: PID controller not available. Place furnace_pid_controller.py in same directory.")

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"
IS_PI = IS_LINUX and (platform.machine().startswith('arm') or platform.machine().startswith('aarch'))

# Platform-specific imports for clipboard
if IS_WINDOWS:
    try:
        from PIL import ImageGrab
        import win32clipboard
        HAS_CLIPBOARD = True
    except ImportError:
        print("Note: win32clipboard not available. Install with: pip install pywin32")
        HAS_CLIPBOARD = False
elif IS_LINUX:
    try:
        import subprocess
        HAS_CLIPBOARD = True
    except ImportError:
        HAS_CLIPBOARD = False
else:  # macOS
    try:
        from PIL import ImageGrab
        import subprocess
        HAS_CLIPBOARD = True
    except ImportError:
        HAS_CLIPBOARD = False

# Try to import drag-and-drop support (optional)
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("Note: tkinterdnd2 not installed. Drag-and-drop disabled. Install with: pip install tkinterdnd2")

# Set appearance mode
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class CollapsibleModule(ctk.CTkFrame):
    """A collapsible frame that can be expanded/collapsed"""
    def __init__(self, parent, title, colors, start_open=True, **kwargs):
        super().__init__(parent, **kwargs)

        self.is_open = start_open
        self.title = title
        self.colors = colors

        # Header button with soft pink/lavender styling
        self.header = ctk.CTkButton(
            self,
            text=f"{'▼' if self.is_open else '▶'} {title}",
            command=self.toggle,
            font=("Georgia", 13, "bold"),
            fg_color=self.colors['primary'],  # Light pink
            hover_color=self.colors['primary_dark'],  # Slightly darker
            text_color=self.colors['text_dark'],  # BLACK text for contrast
            anchor="w",
            corner_radius=12,
            height=42
        )
        self.header.pack(fill="x", padx=5, pady=3)

        # Content frame
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        if self.is_open:
            self.content.pack(fill="both", expand=True, padx=5, pady=5)

    def toggle(self):
        """Toggle module open/closed"""
        self.is_open = not self.is_open

        if self.is_open:
            self.header.configure(text=f"▼ {self.title}")
            self.content.pack(fill="both", expand=True, padx=5, pady=5)
        else:
            self.header.configure(text=f"▶ {self.title}")
            self.content.pack_forget()

class CameraFeed:
    """Manages a single camera feed with zoom and pan"""
    def __init__(self, camera_index, name=None):
        self.camera_index = camera_index
        # Give built-in camera a friendly name
        if camera_index == 0:
            self.name = "Built-in Webcam"
        else:
            self.name = name or f"Camera {camera_index}"

        self.cap = None
        self.is_active = False
        self.last_frame = None

        # Zoom and pan
        self.zoom_level = 1.0  # 1.0 = no zoom, 2.0 = 2x zoom
        self.pan_x = 0  # Pan offset in pixels
        self.pan_y = 0

    def open(self):
        """Open the camera"""
        if self.cap is None or not self.cap.isOpened():
            # Use DirectShow on Windows, V4L2 on Linux (Pi), default on Mac
            if IS_WINDOWS:
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            elif IS_LINUX:
                self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
            else:
                self.cap = cv2.VideoCapture(self.camera_index)
            self.is_active = self.cap.isOpened()
        return self.is_active

    def read(self):
        """Read a frame from the camera with zoom and pan applied"""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.last_frame = frame

                # Apply zoom and pan
                if self.zoom_level > 1.0:
                    frame = self.apply_zoom_pan(frame)

                return frame
        return self.last_frame

    def apply_zoom_pan(self, frame):
        """Apply zoom and pan to frame"""
        h, w = frame.shape[:2]

        # Calculate zoomed dimensions
        new_w = int(w / self.zoom_level)
        new_h = int(h / self.zoom_level)

        # Calculate center with pan offset
        center_x = w // 2 + self.pan_x
        center_y = h // 2 + self.pan_y

        # Clamp to valid region
        x1 = max(0, center_x - new_w // 2)
        y1 = max(0, center_y - new_h // 2)
        x2 = min(w, x1 + new_w)
        y2 = min(h, y1 + new_h)

        # Adjust if we hit boundaries
        if x2 - x1 < new_w:
            x1 = max(0, x2 - new_w)
        if y2 - y1 < new_h:
            y1 = max(0, y2 - new_h)

        # Crop and resize back to original size with BETTER interpolation
        cropped = frame[y1:y2, x1:x2]
        # Use LANCZOS for sharper zoom (better than default LINEAR)
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)

        return zoomed

    def release(self):
        """Release the camera"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_active = False

class BeautifulOpenCVPanelV10_2(TkinterDnD.Tk if HAS_DND else ctk.CTk):
    def __init__(self):
        super().__init__()

        # SOFT PINK/LAVENDER color scheme with BLACK text
        self.colors = {
            'bg': '#FDFAFF',  # Very light lavender-tinted white
            'card': '#FFFFFF',  # Pure white cards
            'primary': '#FFB6C1',  # Light pink (NOT hot pink!)
            'primary_dark': '#FFB6D9',  # Slightly darker light pink
            'secondary': '#E6E6FA',  # Lavender
            'accent': '#DDA0DD',  # Plum
            'text_dark': '#000000',  # BLACK - high contrast!
            'text_medium': '#2C1A3D',  # Very dark purple
            'text_light': '#5D4E6D',  # Medium purple
            'success': '#90EE90',  # Light green
            'warning': '#FFB347',  # Light orange
            'shadow': 'rgba(230, 230, 250, 0.3)'  # Lavender shadow
        }

        # Feed window setup
        self.title("Vision Laboratory v10.2 - Feed")
        self.geometry("1200x900")
        self.minsize(800, 600)

        # Static image mode
        self.static_image = None
        self.static_mode = False

        # Capture mode
        self.capture_mode = ctk.StringVar(value="Live Feed")
        self.last_capture_time = 0

        # AUTO-CAPTURE MODE
        self.auto_capture_enabled = ctk.BooleanVar(value=False)
        self.auto_capture_interval = ctk.StringVar(value="3 minutes")
        self.auto_capture_save_path = ctk.StringVar(value=r"C:\Users\bbryant\Documents\OpenCV Images")
        self.last_auto_capture_time = 0

        # Camera management
        self.cameras = {}
        self.active_cameras = []
        self.camera_checkboxes = {}
        self.view_mode = ctk.StringVar(value="single")
        self.selected_camera = None
        self.previous_view_mode = None

        # Display settings
        self.display_scale = ctk.DoubleVar(value=1.0)

        # Calibration
        self.calibration_mode = ctk.BooleanVar(value=False)
        self.pixels_per_mm = ctk.DoubleVar(value=1.0)
        self.calibration_file = "calibration.json"
        self.load_calibration()

        # Control variables
        self.brightness = ctk.IntVar(value=0)
        self.contrast = ctk.DoubleVar(value=1.0)
        self.blur_amount = ctk.IntVar(value=1)

        # Display modes
        self.show_edges = ctk.BooleanVar(value=False)
        self.show_gray = ctk.BooleanVar(value=False)
        self.show_threshold = ctk.BooleanVar(value=False)
        self.threshold_value = ctk.IntVar(value=127)

        # Measurement tools
        self.show_contours = ctk.BooleanVar(value=False)
        self.show_measurements = ctk.BooleanVar(value=False)
        self.measure_width = ctk.BooleanVar(value=False)
        self.measure_dimension = ctk.StringVar(value="width")
        self.measured_width = 0.0
        self.measured_width_mm = 0.0
        self.all_measurements = []

        # PID Controller
        self.pid_enabled = ctk.BooleanVar(value=False)
        self.pid_target_size = ctk.DoubleVar(value=5.0)
        self.pid_kp = ctk.DoubleVar(value=1.0)
        self.pid_ki = ctk.DoubleVar(value=0.1)
        self.pid_kd = ctk.DoubleVar(value=0.05)
        self.pid_zone_select = ctk.IntVar(value=1)
        self.arduino_port = ctk.StringVar(value="/dev/ttyUSB0")
        self.steps_per_degree = ctk.IntVar(value=50)
        self.motor_controller = None
        self.pid_controller = None

        # HSV color filtering
        self.use_color_filter = ctk.BooleanVar(value=False)
        self.hue_min = ctk.IntVar(value=0)
        self.hue_max = ctk.IntVar(value=20)
        self.sat_min = ctk.IntVar(value=100)
        self.sat_max = ctk.IntVar(value=255)
        self.val_min = ctk.IntVar(value=50)
        self.val_max = ctk.IntVar(value=220)
        self.morph_closing_iterations = ctk.IntVar(value=2)

        # Contour filtering
        self.contour_min_area = ctk.IntVar(value=100)
        self.contour_max_area = ctk.IntVar(value=100000)
        self.contour_min_aspect = ctk.DoubleVar(value=0.0)
        self.contour_max_aspect = ctk.DoubleVar(value=10.0)
        self.contour_min_solidity = ctk.DoubleVar(value=0.0)

        # ROI
        self.roi_enabled = ctk.BooleanVar(value=False)
        self.roi_coords = None
        self.roi_drawing = False
        self.roi_start = None

        # Color picker
        self.color_picker_mode = ctk.BooleanVar(value=False)

        # Morphological operations
        self.morph_operation = ctk.StringVar(value="None")
        self.kernel_size = ctk.IntVar(value=5)

        # Recording
        self.is_recording = ctk.BooleanVar(value=False)
        self.video_writer = None
        self.recording_filename = None

        # Histogram
        self.show_histogram = ctk.BooleanVar(value=False)

        # Kalman filter
        self.kalman_enabled = ctk.BooleanVar(value=False)
        self.kalman_filter = cv2.KalmanFilter(2, 1)
        self.kalman_filter.measurementMatrix = np.array([[1, 0]], np.float32)
        self.kalman_filter.transitionMatrix = np.array([[1, 1], [0, 1]], np.float32)
        self.kalman_filter.processNoiseCov = np.array([[1, 0], [0, 1]], np.float32) * 0.03

        # Setup both windows
        self.setup_feed_window()
        self.setup_control_window()

        # Enable drag and drop only if library is available
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.on_file_drop)

        self.detect_cameras()
        self.update_frame()

    def setup_feed_window(self):
        """Setup the main feed window (self) - FULLY RESPONSIVE"""
        # Main container - minimal padding
        main_container = ctk.CTkFrame(self, fg_color=self.colors['bg'])
        main_container.pack(fill="both", expand=True, padx=2, pady=2)

        # Compact header bar with title and status
        header_frame = ctk.CTkFrame(main_container, fg_color=self.colors['secondary'], height=40)
        header_frame.pack(fill="x", padx=2, pady=2)
        header_frame.pack_propagate(False)  # Don't let it shrink

        # Title - compact
        title_label = ctk.CTkLabel(
            header_frame,
            text="Vision Lab v10.2",
            font=("Georgia", 16, "bold"),
            text_color=self.colors['text_dark']
        )
        title_label.pack(side="left", padx=10)

        # Status label - compact
        self.status_label = ctk.CTkLabel(
            header_frame,
            text="🎥 Ready",
            font=("Georgia", 11),
            text_color=self.colors['text_medium']
        )
        self.status_label.pack(side="left", padx=10)

        # Quit button in header
        quit_btn = ctk.CTkButton(
            header_frame,
            text="Quit (Q)",
            command=self.quit_app,
            font=("Georgia", 11, "bold"),
            fg_color=self.colors['warning'],
            hover_color="#FF8C42",
            text_color=self.colors['text_dark'],
            width=80,
            height=28
        )
        quit_btn.pack(side="right", padx=10)

        # Video display area - THIS IS THE KEY: fill ALL remaining space
        video_frame = ctk.CTkFrame(main_container, fg_color="#000000", corner_radius=0)
        video_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.video_label = ctk.CTkLabel(
            video_frame,
            text="🎥 Waiting for camera...",
            font=("Georgia", 14),
            text_color="#FFFFFF"
        )
        self.video_label.pack(fill="both", expand=True, padx=0, pady=0)

        # Bind mouse events for ROI
        self.video_label.bind("<Button-1>", self.on_mouse_down)
        self.video_label.bind("<B1-Motion>", self.on_mouse_drag)
        self.video_label.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.video_label.bind("<Double-Button-1>", self.on_double_click)

        # Compact measurement display at bottom - FIXED HEIGHT
        measurement_frame = ctk.CTkFrame(main_container, fg_color=self.colors['secondary'], corner_radius=5, height=100)
        measurement_frame.pack(fill="x", padx=2, pady=2)
        measurement_frame.pack_propagate(False)  # Don't expand

        # Measurement header - inline
        measure_header = ctk.CTkFrame(measurement_frame, fg_color="transparent")
        measure_header.pack(fill="x", padx=5, pady=3)

        ctk.CTkLabel(
            measure_header,
            text="📏 Measurements:",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(side="left")

        # Scrollable measurement display - compact
        self.measurement_list_frame = ctk.CTkScrollableFrame(
            measurement_frame,
            fg_color="transparent",
            height=60
        )
        self.measurement_list_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self.measurement_value_label = ctk.CTkLabel(
            self.measurement_list_frame,
            text="No measurement",
            font=("Georgia", 10),
            text_color=self.colors['text_medium'],
            anchor="w",
            justify="left"
        )
        self.measurement_value_label.pack(anchor="w", padx=2, pady=2)

        # Bind keyboard shortcuts
        self.bind("<q>", lambda e: self.quit_app())
        self.bind("<Q>", lambda e: self.quit_app())
        self.bind("<Escape>", lambda e: self.quit_app())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())

    def setup_control_window(self):
        """Setup the floating control panel - RESPONSIVE GRID LAYOUT"""
        self.control_window = Toplevel(self)
        self.control_window.title("Controls - Vision Lab v10.2")
        self.control_window.geometry("380x700")

        # Make it float on top
        self.control_window.attributes('-topmost', True)

        # Closing control window also closes app
        self.control_window.protocol("WM_DELETE_WINDOW", self.quit_app)

        # Configure colors
        self.control_window.configure(bg=self.colors['bg'])

        # Scrollable frame for all controls
        self.control_scroll = ctk.CTkScrollableFrame(
            self.control_window,
            fg_color=self.colors['card'],
            corner_radius=8
        )
        self.control_scroll.pack(fill="both", expand=True, padx=3, pady=3)

        # Configure grid to be responsive (columns configured dynamically in reflow_controls)

        # Store all control modules for responsive layout
        self.control_modules = []

        # Add all the control modules
        self.control_modules.append(self.setup_auto_capture_controls(self.control_scroll))
        self.control_modules.append(self.setup_camera_controls(self.control_scroll))
        self.control_modules.append(self.setup_image_adjustment_controls(self.control_scroll))
        self.control_modules.append(self.setup_detection_controls(self.control_scroll))
        self.control_modules.append(self.setup_measurement_controls(self.control_scroll))
        pid_module = self.setup_pid_controls(self.control_scroll)
        if pid_module:  # Only if PID is available
            self.control_modules.append(pid_module)
        self.control_modules.append(self.setup_roi_controls(self.control_scroll))
        self.control_modules.append(self.setup_display_controls(self.control_scroll))
        self.control_modules.append(self.setup_recording_controls(self.control_scroll))

        # Initial layout (1 column)
        self.current_columns = 1
        self.reflow_controls()

        # Bind resize event to reflow layout
        self.control_window.bind("<Configure>", lambda e: self.on_control_window_resize(e))

    def on_control_window_resize(self, event):
        """Handle control window resize - reflow controls into grid"""
        # Only respond to width changes
        if event.widget == self.control_window:
            width = event.width

            # Calculate columns based on width
            # Each module needs ~300px minimum to be readable
            MIN_MODULE_WIDTH = 300
            desired_columns = max(1, width // MIN_MODULE_WIDTH)

            # Only reflow if column count changed
            if desired_columns != self.current_columns:
                self.current_columns = desired_columns
                self.reflow_controls()

    def reflow_controls(self):
        """Rearrange control modules in a responsive grid"""
        # Remove all modules from grid
        for module in self.control_modules:
            if module:
                module.grid_forget()

        # Configure columns dynamically based on current_columns
        for col in range(self.current_columns):
            self.control_scroll.grid_columnconfigure(col, weight=1)

        # Place modules in grid based on current column count
        for i, module in enumerate(self.control_modules):
            if module:
                row = i // self.current_columns
                col = i % self.current_columns
                module.grid(row=row, column=col, sticky="ew", padx=2, pady=2)

    def setup_auto_capture_controls(self, parent):
        """Auto-capture mode for dataset collection"""
        module = CollapsibleModule(parent, "📸 Auto-Capture", self.colors, start_open=True)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        # Enable toggle
        enable_switch = ctk.CTkSwitch(
            content,
            text="Enable Auto-Capture",
            variable=self.auto_capture_enabled,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        )
        enable_switch.pack(pady=5, padx=5)

        # Interval selection
        ctk.CTkLabel(
            content,
            text="Interval:",
            font=("Georgia", 10),
            text_color=self.colors['text_dark']
        ).pack(pady=(5, 2), padx=5, anchor="w")

        interval_menu = ctk.CTkOptionMenu(
            content,
            variable=self.auto_capture_interval,
            values=["30 seconds", "1 minute", "3 minutes", "5 minutes"],
            font=("Georgia", 10),
            fg_color=self.colors['primary'],
            button_color=self.colors['accent'],
            button_hover_color=self.colors['primary_dark'],
            text_color=self.colors['text_dark']
        )
        interval_menu.pack(pady=3, padx=5, fill="x")

        # Save location
        ctk.CTkLabel(
            content,
            text="Save To:",
            font=("Georgia", 10),
            text_color=self.colors['text_dark']
        ).pack(pady=(5, 2), padx=5, anchor="w")

        path_frame = ctk.CTkFrame(content, fg_color="transparent")
        path_frame.pack(fill="x", pady=3, padx=5)

        path_entry = ctk.CTkEntry(
            path_frame,
            textvariable=self.auto_capture_save_path,
            font=("Georgia", 9),
            fg_color=self.colors['bg'],
            text_color=self.colors['text_dark']
        )
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 3))

        browse_btn = ctk.CTkButton(
            path_frame,
            text="...",
            command=self.browse_save_location,
            font=("Georgia", 10),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            text_color=self.colors['text_dark'],
            width=50
        )
        browse_btn.pack(side="left")

        # Status
        self.auto_capture_status = ctk.CTkLabel(
            content,
            text="Status: Disabled",
            font=("Georgia", 9),
            text_color=self.colors['text_medium']
        )
        self.auto_capture_status.pack(pady=5, padx=5)

        return module

    def setup_camera_controls(self, parent):
        """Camera selection and control"""
        module = CollapsibleModule(parent, "📷 Cameras", self.colors, start_open=True)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        # Detect cameras button
        detect_btn = ctk.CTkButton(
            content,
            text="🔍 Detect Cameras",
            command=self.detect_cameras,
            font=("Georgia", 11, "bold"),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            text_color=self.colors['text_dark'],
            height=32
        )
        detect_btn.pack(pady=5, padx=5, fill="x")

        # Camera list frame
        self.camera_list_frame = ctk.CTkFrame(content, fg_color=self.colors['bg'], corner_radius=5)
        self.camera_list_frame.pack(fill="both", expand=True, pady=5, padx=5)

        # View mode
        ctk.CTkLabel(
            content,
            text="View Mode:",
            font=("Georgia", 10),
            text_color=self.colors['text_dark']
        ).pack(pady=(5, 2), padx=5, anchor="w")

        view_frame = ctk.CTkFrame(content, fg_color="transparent")
        view_frame.pack(fill="x", pady=3, padx=5)

        ctk.CTkRadioButton(
            view_frame,
            text="Single",
            variable=self.view_mode,
            value="single",
            font=("Georgia", 9),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(side="left", padx=5)

        ctk.CTkRadioButton(
            view_frame,
            text="Grid",
            variable=self.view_mode,
            value="grid",
            font=("Georgia", 9),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(side="left", padx=5)

        # Zoom controls
        ctk.CTkLabel(
            content,
            text="Zoom Level:",
            font=("Georgia", 11),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 5))

        zoom_frame = ctk.CTkFrame(content, fg_color="transparent")
        zoom_frame.pack(fill="x", pady=5)

        zoom_slider = ctk.CTkSlider(
            zoom_frame,
            from_=1.0,
            to=5.0,
            command=self.update_zoom,
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary'],
            button_color=self.colors['accent'],
            button_hover_color=self.colors['primary_dark']
        )
        zoom_slider.set(1.0)
        zoom_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.zoom_value_label = ctk.CTkLabel(
            zoom_frame,
            text="1.0x",
            font=("Georgia", 10),
            text_color=self.colors['text_dark'],
            width=50
        )
        self.zoom_value_label.pack(side="left")

        return module

    def setup_image_adjustment_controls(self, parent):
        """Image adjustment controls"""
        module = CollapsibleModule(parent, "🎨 Image Adjustments", self.colors, start_open=False)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        # Brightness
        ctk.CTkLabel(
            content,
            text="Brightness:",
            font=("Georgia", 11),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 5))

        ctk.CTkSlider(
            content,
            from_=-100,
            to=100,
            variable=self.brightness,
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary'],
            button_color=self.colors['accent']
        ).pack(fill="x", padx=10, pady=5)

        # Contrast
        ctk.CTkLabel(
            content,
            text="Contrast:",
            font=("Georgia", 11),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 5))

        ctk.CTkSlider(
            content,
            from_=0.1,
            to=3.0,
            variable=self.contrast,
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary'],
            button_color=self.colors['accent']
        ).pack(fill="x", padx=10, pady=5)

        # Blur
        ctk.CTkLabel(
            content,
            text="Blur Amount:",
            font=("Georgia", 11),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 5))

        ctk.CTkSlider(
            content,
            from_=1,
            to=31,
            variable=self.blur_amount,
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary'],
            button_color=self.colors['accent']
        ).pack(fill="x", padx=10, pady=5)

        return module

    def setup_detection_controls(self, parent):
        """Detection and display mode controls"""
        module = CollapsibleModule(parent, "🔍 Detection Modes", self.colors, start_open=False)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        # Display mode toggles
        ctk.CTkSwitch(
            content,
            text="Edge Detection",
            variable=self.show_edges,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkSwitch(
            content,
            text="Grayscale",
            variable=self.show_gray,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkSwitch(
            content,
            text="Threshold",
            variable=self.show_threshold,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        # Threshold value
        ctk.CTkLabel(
            content,
            text="Threshold Value:",
            font=("Georgia", 10),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 5))

        ctk.CTkSlider(
            content,
            from_=0,
            to=255,
            variable=self.threshold_value,
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary'],
            button_color=self.colors['accent']
        ).pack(fill="x", padx=10, pady=5)

        # HSV Color filtering
        ctk.CTkSwitch(
            content,
            text="HSV Color Filter (Red/Orange)",
            variable=self.use_color_filter,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=(10, 5))

        return module

    def setup_measurement_controls(self, parent):
        """Measurement controls"""
        module = CollapsibleModule(parent, "📏 Measurements", self.colors, start_open=False)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        ctk.CTkSwitch(
            content,
            text="Show Contours",
            variable=self.show_contours,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkSwitch(
            content,
            text="Show Measurements",
            variable=self.show_measurements,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        # Calibration
        ctk.CTkLabel(
            content,
            text="Calibration (pixels/mm):",
            font=("Georgia", 10),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 5))

        calib_frame = ctk.CTkFrame(content, fg_color="transparent")
        calib_frame.pack(fill="x", pady=5)

        calib_entry = ctk.CTkEntry(
            calib_frame,
            textvariable=self.pixels_per_mm,
            font=("Georgia", 10),
            fg_color=self.colors['bg'],
            text_color=self.colors['text_dark']
        )
        calib_entry.pack(side="left", fill="x", expand=True, padx=(10, 5))

        calib_btn = ctk.CTkButton(
            calib_frame,
            text="Calibrate",
            command=self.start_calibration,
            font=("Georgia", 10),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            text_color=self.colors['text_dark'],
            width=100
        )
        calib_btn.pack(side="left")

        return module

    def setup_pid_controls(self, parent):
        """PID controller for furnace"""
        if not HAS_PID:
            return

        module = CollapsibleModule(parent, "🌡️ PID Controller", self.colors, start_open=False)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        ctk.CTkLabel(
            content,
            text="Furnace Temperature Control",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(pady=10)

        ctk.CTkSwitch(
            content,
            text="Enable PID Control",
            variable=self.pid_enabled,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        # Target zone size
        ctk.CTkLabel(
            content,
            text="Target Zone Size (mm):",
            font=("Georgia", 10),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 5))

        ctk.CTkEntry(
            content,
            textvariable=self.pid_target_size,
            font=("Georgia", 10),
            fg_color=self.colors['bg'],
            text_color=self.colors['text_dark']
        ).pack(pady=5, padx=5, fill="x")

        return module

    def setup_roi_controls(self, parent):
        """ROI controls"""
        module = CollapsibleModule(parent, "🎯 Region of Interest", self.colors, start_open=False)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        ctk.CTkSwitch(
            content,
            text="Enable ROI",
            variable=self.roi_enabled,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkLabel(
            content,
            text="Double-click video to set ROI",
            font=("Georgia", 10),
            text_color=self.colors['text_medium']
        ).pack(pady=10)

        clear_roi_btn = ctk.CTkButton(
            content,
            text="Clear ROI",
            command=self.clear_roi,
            font=("Georgia", 10),
            fg_color=self.colors['warning'],
            hover_color="#FF8C42",
            text_color=self.colors['text_dark'],
            width=120
        )
        clear_roi_btn.pack(pady=10)

        return module

    def setup_display_controls(self, parent):
        """Display controls"""
        module = CollapsibleModule(parent, "💾 Screenshot & Display", self.colors, start_open=False)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        # Screenshot button
        screenshot_btn = ctk.CTkButton(
            content,
            text="📸 Take Screenshot (S)",
            command=self.save_screenshot,
            font=("Georgia", 11, "bold"),
            fg_color=self.colors['success'],
            hover_color="#7FD97F",
            text_color=self.colors['text_dark']
        )
        screenshot_btn.pack(pady=10)

        # Histogram
        ctk.CTkSwitch(
            content,
            text="Show Histogram",
            variable=self.show_histogram,
            font=("Georgia", 11),
            text_color=self.colors['text_dark'],
            fg_color=self.colors['secondary'],
            progress_color=self.colors['primary']
        ).pack(anchor="w", padx=10, pady=5)

        return module

    def setup_recording_controls(self, parent):
        """Recording controls"""
        module = CollapsibleModule(parent, "🎬 Video Recording", self.colors, start_open=False)
        # Don't pack - will be gridded by reflow_controls()

        content = module.content

        self.record_btn = ctk.CTkButton(
            content,
            text="⏺️ Start Recording (R)",
            command=self.toggle_recording,
            font=("Georgia", 11, "bold"),
            fg_color=self.colors['warning'],
            hover_color="#FF8C42",
            text_color=self.colors['text_dark']
        )
        self.record_btn.pack(pady=10)

        self.recording_status = ctk.CTkLabel(
            content,
            text="Not recording",
            font=("Georgia", 10),
            text_color=self.colors['text_medium']
        )
        self.recording_status.pack(pady=5)

        return module

    # Camera management methods
    def detect_cameras(self):
        """Detect available cameras"""
        self.status_label.configure(text="🔍 Detecting cameras...")

        # Clear existing camera list
        for widget in self.camera_list_frame.winfo_children():
            widget.destroy()

        # Close all existing cameras
        for cam_idx in list(self.cameras.keys()):
            self.cameras[cam_idx].release()
        self.cameras.clear()
        self.active_cameras.clear()

        # Try to detect cameras (0-9)
        detected_count = 0
        for i in range(10):
            camera = CameraFeed(i)
            if camera.open():
                self.cameras[i] = camera
                detected_count += 1

                # Add checkbox for this camera
                checkbox = ctk.CTkCheckBox(
                    self.camera_list_frame,
                    text=camera.name,
                    command=lambda idx=i: self.toggle_camera(idx),
                    font=("Georgia", 11),
                    text_color=self.colors['text_dark'],
                    fg_color=self.colors['primary'],
                    hover_color=self.colors['primary_dark']
                )
                checkbox.pack(anchor="w", padx=10, pady=5)
                self.camera_checkboxes[i] = checkbox

                # Auto-select first camera
                if i == 0:
                    checkbox.select()
                    self.active_cameras.append(i)
                    self.selected_camera = i
            else:
                camera.release()

        if detected_count > 0:
            self.status_label.configure(text=f"✅ Found {detected_count} camera(s)")
        else:
            self.status_label.configure(text="❌ No cameras found")

        # Add load image button
        load_btn = ctk.CTkButton(
            self.camera_list_frame,
            text="📁 Load Static Image",
            command=self.load_static_image,
            font=("Georgia", 10),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            text_color=self.colors['text_dark']
        )
        load_btn.pack(pady=10)

    def toggle_camera(self, camera_idx):
        """Toggle camera active state"""
        if camera_idx in self.active_cameras:
            self.active_cameras.remove(camera_idx)
        else:
            self.active_cameras.append(camera_idx)

        # Update selected camera (use first active camera)
        if len(self.active_cameras) > 0:
            self.selected_camera = self.active_cameras[0]
        else:
            self.selected_camera = None

    def load_static_image(self):
        """Load a static image for processing"""
        filename = filedialog.askopenfilename(
            title="Load Image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*")]
        )
        if filename:
            img = cv2.imread(filename)
            if img is not None:
                self.static_image = img
                self.static_mode = True
                self.status_label.configure(text=f"📁 Loaded: {os.path.basename(filename)}")

    def update_zoom(self, value):
        """Update zoom level for selected camera"""
        zoom_level = float(value)
        self.zoom_value_label.configure(text=f"{zoom_level:.1f}x")

        if self.selected_camera is not None and self.selected_camera in self.cameras:
            self.cameras[self.selected_camera].zoom_level = zoom_level

    # Frame update loop
    def update_frame(self):
        """Main update loop for video feed"""
        try:
            frame = None

            # Check auto-capture
            self.check_auto_capture()

            # Get frame based on mode
            if self.static_mode and self.static_image is not None:
                frame = self.static_image.copy()
            elif self.view_mode.get() == "single" and self.selected_camera is not None:
                if self.selected_camera in self.cameras:
                    frame = self.cameras[self.selected_camera].read()
            elif self.view_mode.get() == "grid" and len(self.active_cameras) > 0:
                # FIXED GRID MODE with error handling
                try:
                    grid_frames = []

                    for cam_idx in self.active_cameras[:4]:  # Max 4 cameras
                        if cam_idx in self.cameras:
                            cam_frame = self.cameras[cam_idx].read()
                            if cam_frame is not None:
                                # Don't process - just resize for grid
                                # Processing in grid is too slow!
                                grid_frames.append(cam_frame)

                    if grid_frames:
                        # Make all frames same size first
                        h, w = grid_frames[0].shape[:2]
                        target_size = (w//2, h//2)  # Quarter size for grid
                        resized = [cv2.resize(f, target_size) for f in grid_frames]

                        # Arrange in grid
                        if len(resized) == 1:
                            frame = resized[0]
                        elif len(resized) == 2:
                            frame = np.hstack(resized)
                        elif len(resized) == 3:
                            top = np.hstack(resized[:2])
                            bot = resized[2]
                            # Pad bottom to match width
                            if bot.shape[1] < top.shape[1]:
                                pad_width = top.shape[1] - bot.shape[1]
                                pad = np.zeros((bot.shape[0], pad_width, 3), dtype=np.uint8)
                                bot = np.hstack([bot, pad])
                            frame = np.vstack([top, bot])
                        else:  # 4
                            top = np.hstack(resized[:2])
                            bot = np.hstack(resized[2:4])
                            frame = np.vstack([top, bot])

                except Exception as e:
                    print(f"Grid mode error: {e}")
                    # Don't crash - just skip this frame
                    pass

            # Process and display frame
            if frame is not None:
                # Apply image adjustments
                frame = self.apply_adjustments(frame)

                # Apply detection modes
                frame = self.apply_detection_modes(frame)

                # Apply measurements
                if self.show_contours.get() or self.show_measurements.get():
                    frame = self.apply_measurements(frame)

                # Display frame
                self.display_frame(frame)

        except Exception as e:
            print(f"Update error: {e}")

        # Continue loop
        self.after(33, self.update_frame)  # ~30 FPS

    def apply_adjustments(self, frame):
        """Apply brightness, contrast, blur"""
        # Apply brightness
        brightness = self.brightness.get()
        if brightness != 0:
            frame = cv2.convertScaleAbs(frame, beta=brightness)

        # Apply contrast
        contrast = self.contrast.get()
        if contrast != 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=contrast)

        # Apply blur
        blur = self.blur_amount.get()
        if blur > 1:
            # Ensure kernel size is odd
            kernel_size = blur if blur % 2 == 1 else blur + 1
            frame = cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)

        return frame

    def apply_detection_modes(self, frame):
        """Apply edge detection, grayscale, threshold, etc."""
        # Grayscale
        if self.show_gray.get():
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        # Edge detection
        if self.show_edges.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            frame = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        # Threshold
        if self.show_threshold.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, self.threshold_value.get(), 255, cv2.THRESH_BINARY)
            frame = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

        # HSV color filter
        if self.use_color_filter.get():
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Create masks for red (wraps around hue)
            lower_red1 = np.array([0, self.sat_min.get(), self.val_min.get()])
            upper_red1 = np.array([self.hue_max.get(), self.sat_max.get(), self.val_max.get()])
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)

            lower_red2 = np.array([180 - self.hue_max.get(), self.sat_min.get(), self.val_min.get()])
            upper_red2 = np.array([180, self.sat_max.get(), self.val_max.get()])
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

            mask = cv2.bitwise_or(mask1, mask2)

            # Apply morphological closing
            iterations = self.morph_closing_iterations.get()
            if iterations > 0:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=iterations)

            # Apply mask
            frame = cv2.bitwise_and(frame, frame, mask=mask)

        return frame

    def apply_measurements(self, frame):
        """Apply contour detection and measurements"""
        # Convert to grayscale for contour detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply threshold or color filter mask
        if self.use_color_filter.get():
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_red1 = np.array([0, self.sat_min.get(), self.val_min.get()])
            upper_red1 = np.array([self.hue_max.get(), self.sat_max.get(), self.val_max.get()])
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            lower_red2 = np.array([180 - self.hue_max.get(), self.sat_min.get(), self.val_min.get()])
            upper_red2 = np.array([180, self.sat_max.get(), self.val_max.get()])
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            mask = cv2.bitwise_or(mask1, mask2)
        else:
            _, mask = cv2.threshold(gray, self.threshold_value.get(), 255, cv2.THRESH_BINARY)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter contours
        filtered_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.contour_min_area.get() <= area <= self.contour_max_area.get():
                filtered_contours.append(contour)

        # Draw contours
        if self.show_contours.get():
            cv2.drawContours(frame, filtered_contours, -1, (0, 255, 0), 2)

        # Measure and display
        if self.show_measurements.get() and len(filtered_contours) > 0:
            self.all_measurements.clear()

            for i, contour in enumerate(filtered_contours):
                x, y, w, h = cv2.boundingRect(contour)

                # Draw bounding box
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

                # Calculate dimensions
                width_px = w
                height_px = h
                width_mm = width_px / self.pixels_per_mm.get()
                height_mm = height_px / self.pixels_per_mm.get()

                # Store measurement
                self.all_measurements.append({
                    'zone': i + 1,
                    'width_px': width_px,
                    'height_px': height_px,
                    'width_mm': width_mm,
                    'height_mm': height_mm
                })

                # Draw measurement text
                text = f"Zone {i+1}: {width_mm:.1f}mm x {height_mm:.1f}mm"
                cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

            # Update measurement display
            self.update_measurement_display()

        return frame

    def update_measurement_display(self):
        """Update the measurement display panel"""
        if len(self.all_measurements) > 0:
            text = ""
            for m in self.all_measurements:
                text += f"Zone {m['zone']}: {m['width_mm']:.2f} x {m['height_mm']:.2f} mm\n"
            self.measurement_value_label.configure(text=text.strip())
        else:
            self.measurement_value_label.configure(text="No measurements")

    def display_frame(self, frame):
        """Display frame in video label - FILLS ENTIRE SPACE"""
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Convert to PIL Image
        pil_image = Image.fromarray(frame_rgb)

        # Get CURRENT label size (updates dynamically as window resizes)
        label_width = self.video_label.winfo_width()
        label_height = self.video_label.winfo_height()

        # Make sure we have valid dimensions
        if label_width <= 1 or label_height <= 1:
            # Window not fully initialized yet, use default
            label_width = 800
            label_height = 600

        # FILL THE ENTIRE LABEL - scale to whichever dimension fills better
        img_ratio = pil_image.width / pil_image.height
        label_ratio = label_width / label_height

        # Calculate both possible scales
        scale_width = label_width / pil_image.width
        scale_height = label_height / pil_image.height

        # Use the LARGER scale to ensure we fill the space (may crop)
        # This eliminates blank space around the image
        scale = max(scale_width, scale_height)

        # Calculate new size
        new_width = int(pil_image.width * scale)
        new_height = int(pil_image.height * scale)

        # Ensure we don't go below label size
        new_width = max(new_width, label_width)
        new_height = max(new_height, label_height)

        # Resize with high quality
        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convert to CTkImage
        ctk_image = ctk.CTkImage(light_image=pil_image, size=(new_width, new_height))

        # Update label
        self.video_label.configure(image=ctk_image, text="")
        self.video_label.image = ctk_image  # Keep reference

    # Auto-capture functionality
    def check_auto_capture(self):
        """Check if auto-capture should trigger"""
        if not self.auto_capture_enabled.get():
            self.auto_capture_status.configure(text="Status: Disabled")
            return

        interval_seconds = self.get_auto_capture_interval_seconds()
        current_time = time.time()

        if current_time - self.last_auto_capture_time >= interval_seconds:
            self.perform_auto_capture()
            self.last_auto_capture_time = current_time

        # Update status
        time_since_last = current_time - self.last_auto_capture_time
        time_until_next = interval_seconds - time_since_last
        self.auto_capture_status.configure(
            text=f"Status: Active | Next in {int(time_until_next)}s"
        )

    def get_auto_capture_interval_seconds(self):
        """Convert auto-capture interval string to seconds"""
        interval = self.auto_capture_interval.get()
        if interval == "30 seconds":
            return 30
        elif interval == "1 minute":
            return 60
        elif interval == "3 minutes":
            return 180
        elif interval == "5 minutes":
            return 300
        return 180  # Default 3 minutes

    def perform_auto_capture(self):
        """Perform an auto-capture"""
        try:
            # Get current frame
            frame = None
            if self.static_mode and self.static_image is not None:
                frame = self.static_image.copy()
            elif self.selected_camera is not None and self.selected_camera in self.cameras:
                frame = self.cameras[self.selected_camera].read()

            if frame is None:
                return

            # Apply processing
            frame = self.apply_adjustments(frame)
            frame = self.apply_detection_modes(frame)
            if self.show_contours.get() or self.show_measurements.get():
                frame = self.apply_measurements(frame)

            # Save to specified location
            save_dir = self.auto_capture_save_path.get()
            os.makedirs(save_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(save_dir, f"auto_capture_{timestamp}.png")

            cv2.imwrite(filename, frame)
            print(f"Auto-captured: {filename}")

        except Exception as e:
            print(f"Auto-capture error: {e}")

    def browse_save_location(self):
        """Browse for save location"""
        directory = filedialog.askdirectory(title="Select Save Location")
        if directory:
            self.auto_capture_save_path.set(directory)

    # Calibration
    def load_calibration(self):
        """Load calibration from file"""
        try:
            if os.path.exists(self.calibration_file):
                with open(self.calibration_file, 'r') as f:
                    data = json.load(f)
                    self.pixels_per_mm.set(data.get('pixels_per_mm', 1.0))
        except Exception as e:
            print(f"Error loading calibration: {e}")

    def save_calibration(self):
        """Save calibration to file"""
        try:
            data = {'pixels_per_mm': self.pixels_per_mm.get()}
            with open(self.calibration_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving calibration: {e}")

    def start_calibration(self):
        """Start calibration mode"""
        self.calibration_mode.set(True)
        self.status_label.configure(text="📏 Calibration: Draw a line of known length")

    # ROI methods
    def clear_roi(self):
        """Clear ROI"""
        self.roi_coords = None
        self.roi_enabled.set(False)

    def on_mouse_down(self, event):
        """Handle mouse down for ROI"""
        if self.roi_enabled.get():
            self.roi_drawing = True
            self.roi_start = (event.x, event.y)

    def on_mouse_drag(self, event):
        """Handle mouse drag for ROI"""
        pass  # Could show preview

    def on_mouse_up(self, event):
        """Handle mouse up for ROI"""
        if self.roi_enabled.get() and self.roi_drawing:
            self.roi_drawing = False
            self.roi_coords = (self.roi_start[0], self.roi_start[1], event.x, event.y)

    def on_double_click(self, event):
        """Handle double click"""
        self.clear_roi()

    # File operations
    def save_screenshot(self):
        """Save screenshot"""
        try:
            # Get current frame
            frame = None
            if self.static_mode and self.static_image is not None:
                frame = self.static_image.copy()
            elif self.selected_camera is not None and self.selected_camera in self.cameras:
                frame = self.cameras[self.selected_camera].read()

            if frame is None:
                self.status_label.configure(text="❌ No frame to save")
                return

            # Apply processing
            frame = self.apply_adjustments(frame)
            frame = self.apply_detection_modes(frame)
            if self.show_contours.get() or self.show_measurements.get():
                frame = self.apply_measurements(frame)

            # Save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            cv2.imwrite(filename, frame)

            self.status_label.configure(text=f"✅ Saved: {filename}")

        except Exception as e:
            self.status_label.configure(text=f"❌ Error: {e}")

    def on_file_drop(self, event):
        """Handle file drop"""
        try:
            file_path = event.data
            # Remove curly braces if present
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]

            img = cv2.imread(file_path)
            if img is not None:
                self.static_image = img
                self.static_mode = True
                self.status_label.configure(text=f"📁 Loaded: {os.path.basename(file_path)}")
        except Exception as e:
            self.status_label.configure(text=f"❌ Error loading file: {e}")

    # Recording
    def toggle_recording(self):
        """Toggle video recording"""
        if not self.is_recording.get():
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start recording"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_filename = f"recording_{timestamp}.avi"

            # Get frame size from current camera
            frame = None
            if self.selected_camera is not None and self.selected_camera in self.cameras:
                frame = self.cameras[self.selected_camera].read()

            if frame is None:
                self.recording_status.configure(text="❌ No camera active")
                return

            height, width = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(self.recording_filename, fourcc, 20.0, (width, height))

            self.is_recording.set(True)
            self.record_btn.configure(text="⏹️ Stop Recording (R)")
            self.recording_status.configure(text=f"🔴 Recording: {self.recording_filename}")

        except Exception as e:
            self.recording_status.configure(text=f"❌ Error: {e}")

    def stop_recording(self):
        """Stop recording"""
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        self.is_recording.set(False)
        self.record_btn.configure(text="⏺️ Start Recording (R)")
        self.recording_status.configure(text=f"✅ Saved: {self.recording_filename}")

    # Fullscreen
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        current = self.attributes('-fullscreen')
        self.attributes('-fullscreen', not current)

    # Quit
    def quit_app(self):
        """Quit application"""
        # Stop recording if active
        if self.is_recording.get():
            self.stop_recording()

        # Release cameras
        for cam in self.cameras.values():
            cam.release()

        # Save calibration
        self.save_calibration()

        # Close windows
        try:
            self.control_window.destroy()
        except:
            pass

        self.quit()

if __name__ == "__main__":
    app = BeautifulOpenCVPanelV10_2()
    app.mainloop()
