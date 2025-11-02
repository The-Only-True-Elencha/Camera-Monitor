"""
Beautiful OpenCV Control Panel - Version 10.1
Modern, elegant GUI for multi-camera OpenCV processing with auto-capture

NEW IN V10.1:
- AUTO-CAPTURE MODE: Time-lapse dataset collection (30sec, 1min, 3min, 5min intervals)
- Custom save location for captures
- Vibrant Kawaii theme (readable, shiny, high contrast)
- Improved camera detection with manual rescan
- Better zoom interpolation (sharper quality)
- Fixed screenshot functionality
- Status messages for all save operations
- Grid mode implementation (dual camera support)

Author: Created for Chloe's germanium zone refining project
"""

import cv2
import customtkinter as ctk
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
    def __init__(self, parent, title, start_open=True, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.is_open = start_open
        self.title = title
        
        # Header button with VIBRANT kawaii styling
        self.header = ctk.CTkButton(
            self,
            text=f"{'▼' if self.is_open else '▶'} {title}",
            command=self.toggle,
            font=("Georgia", 13, "bold"),
            fg_color="#FF69B4",  # Hot pink - vibrant!
            hover_color="#FF1493",  # Deep pink hover
            text_color="#FFFFFF",  # White text - HIGH CONTRAST
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

class BeautifulOpenCVPanelV10_1(TkinterDnD.Tk if HAS_DND else ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("OpenCV Vision Laboratory v10.1 🔬✨ [Auto-Capture Ready]")
        self.geometry("1700x1000")
        self.minsize(1400, 800)
        
        # VIBRANT Kawaii color scheme - readable and shiny!
        self.colors = {
            'bg': '#FFFBFD',  # Crisp white with hint of pink
            'card': '#FFFFFF',  # Pure white cards
            'primary': '#FF69B4',  # Hot pink - VIBRANT
            'primary_dark': '#FF1493',  # Deep pink
            'secondary': '#DDA0DD',  # Plum - saturated lavender
            'accent': '#00CED1',  # Dark turquoise - bright!
            'text_dark': '#2C1A3D',  # Deep purple - HIGH CONTRAST
            'text_medium': '#5D4E6D',  # Medium purple
            'text_light': '#8B7B9B',  # Light purple
            'success': '#00FA9A',  # Medium spring green - BRIGHT
            'warning': '#FF6347',  # Tomato red - visible!
            'shadow': 'rgba(255, 105, 180, 0.1)'  # Pink shadow with glow
        }
        
        # Static image mode
        self.static_image = None
        self.static_mode = False
        
        # Capture mode
        self.capture_mode = ctk.StringVar(value="Live Feed")  # Live, 3fps, 1fps, 5sec
        self.last_capture_time = 0
        
        # AUTO-CAPTURE MODE (new in v10.1)
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
        
        # Calibration - ensure never zero
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
        self.measure_dimension = ctk.StringVar(value="width")  # width or height
        self.measured_width = 0.0
        self.measured_width_mm = 0.0
        self.all_measurements = []  # Store all zone measurements
        
        # PID Controller for furnace temperature
        self.pid_enabled = ctk.BooleanVar(value=False)
        self.pid_target_size = ctk.DoubleVar(value=5.0)  # Target molten zone size (mm)
        self.pid_kp = ctk.DoubleVar(value=1.0)
        self.pid_ki = ctk.DoubleVar(value=0.1)
        self.pid_kd = ctk.DoubleVar(value=0.05)
        self.pid_zone_select = ctk.IntVar(value=1)  # Which zone to control (1, 2, 3, etc)
        self.arduino_port = ctk.StringVar(value="/dev/ttyUSB0")  # COM3 on Windows
        self.steps_per_degree = ctk.IntVar(value=50)  # Motor steps per degree temp change
        self.motor_controller = None
        self.pid_controller = None
        
        # HSV color filtering for red/orange detection
        self.use_color_filter = ctk.BooleanVar(value=False)
        self.hue_min = ctk.IntVar(value=0)
        self.hue_max = ctk.IntVar(value=20)
        self.sat_min = ctk.IntVar(value=100)
        self.sat_max = ctk.IntVar(value=255)
        self.val_min = ctk.IntVar(value=50)
        self.val_max = ctk.IntVar(value=220)  # Upper limit to exclude white-hot coils
        self.morph_closing_iterations = ctk.IntVar(value=2)  # Adjustable closing iterations
        
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
        
        self.setup_ui()
        self.detect_cameras()
        
        # Enable drag and drop only if library is available
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.on_file_drop)
        
        self.update_frame()
    
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
        return 180  # Default to 3 minutes
    
    def check_auto_capture(self):
        """Check if it's time to auto-capture a frame"""
        if not self.auto_capture_enabled.get():
            return False
        
        current_time = time.time()
        interval_seconds = self.get_auto_capture_interval_seconds()
        
        if current_time - self.last_auto_capture_time >= interval_seconds:
            self.last_auto_capture_time = current_time
            return True
        return False
    
    def auto_capture_frame(self):
        """Auto-capture and save raw frame"""
        # Make sure save directory exists
        save_dir = self.auto_capture_save_path.get()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir)
            except Exception as e:
                self.status_label.configure(
                    text=f"❌ Cannot create directory: {str(e)}",
                    text_color=self.colors['warning']
                )
                return
        
        # Get RAW frame (no processing)
        if self.static_mode and self.static_image is not None:
            frame = self.static_image.copy()
        elif self.selected_camera is not None and self.selected_camera in self.cameras:
            frame = self.cameras[self.selected_camera].last_frame
            if frame is None:
                return
        else:
            return
        
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"furnace_{timestamp}.png"
        filepath = os.path.join(save_dir, filename)
        
        cv2.imwrite(filepath, frame)
        
        # Update status
        self.status_label.configure(
            text=f"✅ Auto-captured: {filename}",
            text_color=self.colors['success']
        )
    
    def choose_save_location(self):
        """Open folder picker for save location"""
        folder = filedialog.askdirectory(
            title="Choose Save Location for Auto-Captures",
            initialdir=self.auto_capture_save_path.get()
        )
        
        if folder:
            self.auto_capture_save_path.set(folder)
            if hasattr(self, 'save_path_label'):
                self.save_path_label.configure(text=folder)
            self.status_label.configure(
                text=f"✅ Save location updated",
                text_color=self.colors['success']
            )
    
    def on_file_drop(self, event):
        """Handle drag and drop of image files"""
        file_path = event.data
        # Clean up the file path (remove curly braces if present)
        file_path = file_path.strip('{}')
        self.load_static_image(file_path)
    
    def load_static_image(self, file_path=None):
        """Load a static image for analysis"""
        if file_path is None:
            from tkinter import filedialog
            file_path = filedialog.askopenfilename(
                title="Select Image",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"),
                    ("All files", "*.*")
                ]
            )
        
        if file_path and os.path.exists(file_path):
            self.static_image = cv2.imread(file_path)
            if self.static_image is not None:
                self.static_mode = True
                self.status_label.configure(
                    text=f"📷 Static Image: {os.path.basename(file_path)}",
                    text_color=self.colors['success']
                )
            else:
                self.status_label.configure(
                    text="❌ Failed to load image",
                    text_color=self.colors['warning']
                )
    
    def clear_static_image(self):
        """Return to live camera mode"""
        self.static_image = None
        self.static_mode = False
        self.status_label.configure(
            text="🎥 Live Camera Mode",
            text_color=self.colors['text_medium']
        )
    
    def setup_ui(self):
        """Create the user interface"""
        # Main container
        main_container = ctk.CTkFrame(self, fg_color=self.colors['bg'])
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left panel (video display) - MUCH WIDER NOW
        left_panel = ctk.CTkFrame(main_container, fg_color=self.colors['card'], corner_radius=15)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Title
        title_label = ctk.CTkLabel(
            left_panel,
            text="Vision Laboratory ✨",
            font=("Georgia", 24, "bold"),
            text_color=self.colors['text_dark']
        )
        title_label.pack(pady=(15, 10))
        
        # Status label
        self.status_label = ctk.CTkLabel(
            left_panel,
            text="🎥 Ready",
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        )
        self.status_label.pack(pady=5)
        
        # Video display area - MAXIMIZED
        video_frame = ctk.CTkFrame(left_panel, fg_color=self.colors['bg'], corner_radius=12)
        video_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.video_label = ctk.CTkLabel(
            video_frame,
            text="🎥 Waiting for camera...",
            font=("Georgia", 14),
            text_color=self.colors['text_light']
        )
        self.video_label.pack(fill="both", expand=True)
        
        # Bind mouse events for ROI
        self.video_label.bind("<Button-1>", self.on_mouse_down)
        self.video_label.bind("<B1-Motion>", self.on_mouse_drag)
        self.video_label.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.video_label.bind("<Double-Button-1>", self.on_double_click)
        
        # Measurement display below video - expanded for multiple zones
        measurement_frame = ctk.CTkFrame(left_panel, fg_color=self.colors['secondary'], corner_radius=10)
        measurement_frame.pack(fill="both", expand=False, padx=15, pady=(0, 15))
        
        ctk.CTkLabel(
            measurement_frame,
            text="📏 Measurements:",
            font=("Georgia", 13, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=15, pady=(10, 5))
        
        # Scrollable frame for multiple measurements
        self.measurement_list_frame = ctk.CTkScrollableFrame(
            measurement_frame,
            fg_color="transparent",
            height=80
        )
        self.measurement_list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.measurement_value_label = ctk.CTkLabel(
            self.measurement_list_frame,
            text="No measurement",
            font=("Georgia", 12),
            text_color=self.colors['text_medium'],
            anchor="w",
            justify="left"
        )
        self.measurement_value_label.pack(anchor="w", padx=5, pady=5)
        
        # Right panel (controls) - More compact
        right_panel = ctk.CTkScrollableFrame(
            main_container,
            fg_color=self.colors['card'],
            corner_radius=15,
            width=420
        )
        right_panel.pack(side="right", fill="y")
        
        # Setup control modules with better organization
        self.setup_auto_capture_controls(right_panel)  # NEW in v10.1 - Auto-capture first!
        self.setup_camera_controls(right_panel)
        self.setup_image_adjustment_controls(right_panel)
        self.setup_detection_controls(right_panel)
        self.setup_measurement_controls(right_panel)
        self.setup_pid_controls(right_panel)  # PID furnace control
        self.setup_roi_controls(right_panel)
        self.setup_display_controls(right_panel)
        self.setup_recording_controls(right_panel)
    
    def setup_auto_capture_controls(self, parent):
        """NEW in v10.1: Auto-capture mode for dataset collection"""
        module = CollapsibleModule(parent, "📸 Auto-Capture Mode", start_open=True)
        module.pack(fill="x", pady=5)
        
        # Enable auto-capture
        self.auto_capture_checkbox = ctk.CTkCheckBox(
            module.content,
            text="✅ Enable Auto-Capture",
            variable=self.auto_capture_enabled,
            font=("Georgia", 13, "bold"),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary'],
            text_color=self.colors['text_dark']
        )
        self.auto_capture_checkbox.pack(anchor="w", padx=10, pady=10)
        
        # Interval selection
        interval_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        interval_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            interval_frame,
            text="⏱️ Capture Interval:",
            font=("Georgia", 12, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkOptionMenu(
            interval_frame,
            values=["30 seconds", "1 minute", "3 minutes", "5 minutes"],
            variable=self.auto_capture_interval,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            button_color=self.colors['primary_dark'],
            button_hover_color=self.colors['primary'],
            text_color="#FFFFFF"
        ).pack(fill="x", padx=20, pady=5)
        
        # Save location
        location_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        location_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            location_frame,
            text="📁 Save Location:",
            font=("Georgia", 12, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        # Current path display
        self.save_path_label = ctk.CTkLabel(
            location_frame,
            text=self.auto_capture_save_path.get(),
            font=("Georgia", 9),
            text_color=self.colors['text_medium'],
            wraplength=350,
            anchor="w",
            justify="left"
        )
        self.save_path_label.pack(anchor="w", padx=10, pady=3)
        
        # Change location button
        ctk.CTkButton(
            location_frame,
            text="📂 Change Save Location",
            command=self.choose_save_location,
            font=("Georgia", 11),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            text_color="#FFFFFF",
            corner_radius=8,
            height=32
        ).pack(fill="x", padx=10, pady=5)
        
        # Info label
        ctk.CTkLabel(
            module.content,
            text="💡 Captures RAW frames for dataset labeling",
            font=("Georgia", 10, "italic"),
            text_color=self.colors['text_medium'],
            wraplength=350
        ).pack(padx=10, pady=(0, 10))
    
    def setup_camera_controls(self, parent):
        """Camera selection and view controls"""
        module = CollapsibleModule(parent, "📷 Camera Selection & View", start_open=True)
        module.pack(fill="x", pady=5)
        
        # Detect cameras button (NEW in v10.1)
        detect_btn = ctk.CTkButton(
            module.content,
            text="🔄 Detect Cameras",
            command=self.detect_cameras,
            font=("Georgia", 12, "bold"),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            text_color="#FFFFFF",
            corner_radius=10,
            height=40
        )
        detect_btn.pack(fill="x", padx=10, pady=5)
        
        # Load image button
        load_btn = ctk.CTkButton(
            module.content,
            text="📂 Load Static Image",
            command=self.load_static_image,
            font=("Georgia", 12),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            corner_radius=10
        )
        load_btn.pack(fill="x", padx=10, pady=5)
        
        # Clear static image button
        clear_btn = ctk.CTkButton(
            module.content,
            text="🎥 Return to Live Camera",
            command=self.clear_static_image,
            font=("Georgia", 12),
            fg_color=self.colors['secondary'],
            hover_color=self.colors['primary_dark'],
            corner_radius=10
        )
        clear_btn.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            module.content,
            text="💡 Tip: Drag & drop images onto the window!",
            font=("Georgia", 10, "italic"),
            text_color=self.colors['text_light']
        ).pack(pady=5)
        
        # View mode
        view_frame = ctk.CTkFrame(module.content, fg_color="transparent")
        view_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            view_frame,
            text="View Mode:",
            font=("Georgia", 12, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", pady=5)
        
        ctk.CTkRadioButton(
            view_frame,
            text="Single Camera",
            variable=self.view_mode,
            value="single",
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=20)
        
        ctk.CTkRadioButton(
            view_frame,
            text="Grid View",
            variable=self.view_mode,
            value="grid",
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=20)
        
        # Camera checkboxes container
        self.camera_list_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        self.camera_list_frame.pack(fill="x", padx=10, pady=10)
        
        # Focus controls (for IMX477 and other USB cameras with focus)
        if IS_LINUX:
            focus_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
            focus_frame.pack(fill="x", padx=10, pady=10)
            
            ctk.CTkLabel(
                focus_frame,
                text="🔍 Camera Focus:",
                font=("Georgia", 11, "bold"),
                text_color=self.colors['text_dark']
            ).pack(anchor="w", padx=10, pady=5)
            
            # Autofocus toggle
            self.autofocus_enabled = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(
                focus_frame,
                text="Auto Focus",
                variable=self.autofocus_enabled,
                command=self.toggle_autofocus,
                font=("Georgia", 10),
                fg_color=self.colors['primary'],
                hover_color=self.colors['primary_dark']
            ).pack(anchor="w", padx=10, pady=3)
            
            # Manual focus slider
            ctk.CTkLabel(
                focus_frame,
                text="Manual Focus (0-255):",
                font=("Georgia", 10)
            ).pack(anchor="w", padx=10, pady=(5, 0))
            
            self.focus_value = ctk.IntVar(value=50)
            focus_slider = ctk.CTkSlider(
                focus_frame,
                from_=0,
                to=255,
                variable=self.focus_value,
                command=self.adjust_focus,
                button_color=self.colors['primary'],
                button_hover_color=self.colors['primary_dark'],
                progress_color=self.colors['secondary']
            )
            focus_slider.pack(fill="x", padx=20, pady=5)
            
            ctk.CTkLabel(
                focus_frame,
                text="💡 Disable autofocus for stable measurements",
                font=("Georgia", 9, "italic"),
                text_color=self.colors['text_light'],
                wraplength=350
            ).pack(padx=10, pady=(0, 5))

    
    def setup_image_adjustment_controls(self, parent):
        """Basic image adjustment controls"""
        module = CollapsibleModule(parent, "🎨 Image Adjustments", start_open=True)
        module.pack(fill="x", pady=5)
        
        # Brightness
        ctk.CTkLabel(
            module.content,
            text="☀️ Brightness:",
            font=("Georgia", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        
        ctk.CTkSlider(
            module.content,
            from_=-100,
            to=100,
            variable=self.brightness,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=5)
        
        # Contrast
        ctk.CTkLabel(
            module.content,
            text="◐ Contrast:",
            font=("Georgia", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        
        ctk.CTkSlider(
            module.content,
            from_=0.1,
            to=3.0,
            variable=self.contrast,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=5)
        
        # Blur
        ctk.CTkLabel(
            module.content,
            text="～ Blur Amount:",
            font=("Georgia", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        
        ctk.CTkSlider(
            module.content,
            from_=1,
            to=31,
            number_of_steps=15,
            variable=self.blur_amount,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=5)
        
        # Display modes
        ctk.CTkCheckBox(
            module.content,
            text="⚫ Grayscale",
            variable=self.show_gray,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=20, pady=3)
    
    def setup_detection_controls(self, parent):
        """Detection and analysis controls"""
        module = CollapsibleModule(parent, "🔍 Detection & Analysis", start_open=True)
        module.pack(fill="x", pady=5)
        
        # HSV Color filtering for molten zone detection
        color_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        color_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkCheckBox(
            color_frame,
            text="🎨 HSV Color Filter (Detect Red/Orange)",
            variable=self.use_color_filter,
            font=("Georgia", 11, "bold"),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkLabel(
            color_frame,
            text="🔴 Hue Range (0-180):",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        hue_frame = ctk.CTkFrame(color_frame, fg_color="transparent")
        hue_frame.pack(fill="x", padx=20, pady=3)
        
        ctk.CTkLabel(hue_frame, text="Min:", font=("Georgia", 9)).pack(side="left", padx=5)
        ctk.CTkSlider(
            hue_frame,
            from_=0,
            to=180,
            variable=self.hue_min,
            width=100,
            button_color=self.colors['primary'],
            progress_color=self.colors['secondary']
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(hue_frame, text="Max:", font=("Georgia", 9)).pack(side="left", padx=5)
        ctk.CTkSlider(
            hue_frame,
            from_=0,
            to=180,
            variable=self.hue_max,
            width=100,
            button_color=self.colors['primary'],
            progress_color=self.colors['secondary']
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(
            color_frame,
            text="💧 Saturation Range (0-255):",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        sat_frame = ctk.CTkFrame(color_frame, fg_color="transparent")
        sat_frame.pack(fill="x", padx=20, pady=3)
        
        ctk.CTkLabel(sat_frame, text="Min:", font=("Georgia", 9)).pack(side="left", padx=5)
        ctk.CTkSlider(
            sat_frame,
            from_=0,
            to=255,
            variable=self.sat_min,
            width=100,
            button_color=self.colors['primary'],
            progress_color=self.colors['secondary']
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(sat_frame, text="Max:", font=("Georgia", 9)).pack(side="left", padx=5)
        ctk.CTkSlider(
            sat_frame,
            from_=0,
            to=255,
            variable=self.sat_max,
            width=100,
            button_color=self.colors['primary'],
            progress_color=self.colors['secondary']
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(
            color_frame,
            text="☀️ Value/Brightness (0-255):",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        val_frame = ctk.CTkFrame(color_frame, fg_color="transparent")
        val_frame.pack(fill="x", padx=20, pady=3)
        
        ctk.CTkLabel(val_frame, text="Min:", font=("Georgia", 9)).pack(side="left", padx=5)
        ctk.CTkSlider(
            val_frame,
            from_=0,
            to=255,
            variable=self.val_min,
            width=100,
            button_color=self.colors['primary'],
            progress_color=self.colors['secondary']
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(val_frame, text="Max:", font=("Georgia", 9)).pack(side="left", padx=5)
        ctk.CTkSlider(
            val_frame,
            from_=0,
            to=255,
            variable=self.val_max,
            width=100,
            button_color=self.colors['primary'],
            progress_color=self.colors['secondary']
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(
            color_frame,
            text="💡 Tip: Lower max brightness to exclude white-hot coils",
            font=("Georgia", 9, "italic"),
            text_color=self.colors['text_light'],
            wraplength=350
        ).pack(padx=10, pady=5)
        
        # Edge detection
        ctk.CTkCheckBox(
            module.content,
            text="✨ Edge Detection",
            variable=self.show_edges,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        # Threshold / Heatmap
        ctk.CTkCheckBox(
            module.content,
            text="🔥 Gradient Heatmap",
            variable=self.show_threshold,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        ctk.CTkLabel(
            module.content,
            text="🌡️ Threshold Level:",
            font=("Georgia", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        
        ctk.CTkSlider(
            module.content,
            from_=0,
            to=255,
            variable=self.threshold_value,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=5)
        
        # Contours
        ctk.CTkCheckBox(
            module.content,
            text="📐 Show Contours",
            variable=self.show_contours,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        # Morphological operations
        ctk.CTkLabel(
            module.content,
            text="🔬 Morphological Operation:",
            font=("Georgia", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        
        ctk.CTkOptionMenu(
            module.content,
            values=["None", "Erosion", "Dilation", "Opening", "Closing", "Gradient"],
            variable=self.morph_operation,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            button_color=self.colors['primary_dark'],
            button_hover_color=self.colors['primary']
        ).pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(
            module.content,
            text="📏 Kernel Size:",
            font=("Georgia", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        
        ctk.CTkSlider(
            module.content,
            from_=3,
            to=21,
            number_of_steps=9,
            variable=self.kernel_size,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=5)
        
        # Closing iterations for color filter
        ctk.CTkLabel(
            module.content,
            text="🔄 Closing Iterations (for HSV filter):",
            font=("Georgia", 11, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        
        ctk.CTkSlider(
            module.content,
            from_=1,
            to=10,
            number_of_steps=9,
            variable=self.morph_closing_iterations,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(
            module.content,
            text="💡 Higher = bridge larger gaps in molten zones",
            font=("Georgia", 9, "italic"),
            text_color=self.colors['text_light'],
            wraplength=350
        ).pack(padx=10, pady=(0, 5))
    
    def setup_measurement_controls(self, parent):
        """Measurement and calibration controls"""
        module = CollapsibleModule(parent, "📏 Measurement & Calibration", start_open=True)
        module.pack(fill="x", pady=5)
        
        # Calibration
        cal_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        cal_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            cal_frame,
            text="🎯 Calibration",
            font=("Georgia", 12, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkLabel(
            cal_frame,
            text="Pixels per mm:",
            font=("Georgia", 11)
        ).pack(anchor="w", padx=10)
        
        cal_entry = ctk.CTkEntry(
            cal_frame,
            textvariable=self.pixels_per_mm,
            font=("Georgia", 11),
            width=120
        )
        cal_entry.pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkButton(
            cal_frame,
            text="💾 Save Calibration",
            command=self.save_calibration,
            font=("Georgia", 11),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary_dark'],
            corner_radius=8,
            height=32
        ).pack(fill="x", padx=10, pady=5)
        
        # Measurement controls
        ctk.CTkCheckBox(
            module.content,
            text="📊 Show Measurements",
            variable=self.show_measurements,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        ctk.CTkCheckBox(
            module.content,
            text="📐 Enable Measurement",
            variable=self.measure_width,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        # Dimension selection
        dim_frame = ctk.CTkFrame(module.content, fg_color="transparent")
        dim_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            dim_frame,
            text="Measure:",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(side="left", padx=5)
        
        ctk.CTkRadioButton(
            dim_frame,
            text="Width ↔",
            variable=self.measure_dimension,
            value="width",
            font=("Georgia", 10),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(side="left", padx=5)
        
        ctk.CTkRadioButton(
            dim_frame,
            text="Height ↕",
            variable=self.measure_dimension,
            value="height",
            font=("Georgia", 10),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(side="left", padx=5)
        
        ctk.CTkCheckBox(
            module.content,
            text="🎯 Kalman Filter (Smoothing)",
            variable=self.kalman_enabled,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        # Contour filtering
        filter_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        filter_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            filter_frame,
            text="🔧 Contour Filters (Ignore Coils)",
            font=("Georgia", 12, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        # Min area
        ctk.CTkLabel(
            filter_frame,
            text="Min Area (px²):",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10)
        
        ctk.CTkSlider(
            filter_frame,
            from_=0,
            to=5000,
            variable=self.contour_min_area,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=3)
        
        # Max area
        ctk.CTkLabel(
            filter_frame,
            text="Max Area (px²):",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10)
        
        ctk.CTkSlider(
            filter_frame,
            from_=1000,
            to=500000,
            variable=self.contour_max_area,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=3)
        
        # Aspect ratio
        ctk.CTkLabel(
            filter_frame,
            text="Min Aspect Ratio:",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10)
        
        ctk.CTkSlider(
            filter_frame,
            from_=0.0,
            to=5.0,
            variable=self.contour_min_aspect,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=3)
        
        # Solidity
        ctk.CTkLabel(
            filter_frame,
            text="Min Solidity (blob-ness):",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10)
        
        ctk.CTkSlider(
            filter_frame,
            from_=0.0,
            to=1.0,
            variable=self.contour_min_solidity,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        ).pack(fill="x", padx=20, pady=3)
    
    def setup_pid_controls(self, parent):
        """PID Furnace Temperature Control"""
        module = CollapsibleModule(parent, "🔥 PID Furnace Control", start_open=False)
        module.pack(fill="x", pady=5)
        
        if not HAS_PID:
            ctk.CTkLabel(
                module.content,
                text="⚠️ PID controller not available\nInstall: pip3 install simple-pid pyserial",
                font=("Georgia", 10, "italic"),
                text_color=self.colors['warning']
            ).pack(padx=10, pady=10)
            return
        
        # Arduino connection
        conn_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        conn_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            conn_frame,
            text="🔌 Arduino Connection:",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        port_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        port_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(port_frame, text="Port:", font=("Georgia", 10)).pack(side="left", padx=5)
        
        ctk.CTkEntry(
            port_frame,
            textvariable=self.arduino_port,
            font=("Georgia", 10),
            width=150
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            conn_frame,
            text="Connect to Arduino",
            command=self.connect_arduino,
            font=("Georgia", 11),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary_dark'],
            height=32
        ).pack(fill="x", padx=10, pady=5)
        
        self.arduino_status_label = ctk.CTkLabel(
            conn_frame,
            text="⚪ Not connected",
            font=("Georgia", 10),
            text_color=self.colors['text_light']
        )
        self.arduino_status_label.pack(padx=10, pady=5)
        
        # PID Target
        target_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        target_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            target_frame,
            text="🎯 Target Molten Zone Size:",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        target_entry_frame = ctk.CTkFrame(target_frame, fg_color="transparent")
        target_entry_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkEntry(
            target_entry_frame,
            textvariable=self.pid_target_size,
            font=("Georgia", 11),
            width=80
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(
            target_entry_frame,
            text="mm",
            font=("Georgia", 11)
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(
            target_frame,
            text="Control Zone:",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10, pady=(10,0))
        
        zone_frame = ctk.CTkFrame(target_frame, fg_color="transparent")
        zone_frame.pack(fill="x", padx=10, pady=5)
        
        for i in range(1, 5):
            ctk.CTkRadioButton(
                zone_frame,
                text=f"Zone {i}",
                variable=self.pid_zone_select,
                value=i,
                font=("Georgia", 10),
                fg_color=self.colors['primary'],
                hover_color=self.colors['primary_dark']
            ).pack(side="left", padx=5)
        
        # PID Tuning
        tune_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        tune_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            tune_frame,
            text="🔧 PID Tuning:",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        # Kp
        kp_frame = ctk.CTkFrame(tune_frame, fg_color="transparent")
        kp_frame.pack(fill="x", padx=10, pady=3)
        
        ctk.CTkLabel(kp_frame, text="Kp:", font=("Georgia", 10), width=40).pack(side="left")
        ctk.CTkEntry(
            kp_frame,
            textvariable=self.pid_kp,
            font=("Georgia", 10),
            width=60
        ).pack(side="left", padx=5)
        
        # Ki
        ki_frame = ctk.CTkFrame(tune_frame, fg_color="transparent")
        ki_frame.pack(fill="x", padx=10, pady=3)
        
        ctk.CTkLabel(ki_frame, text="Ki:", font=("Georgia", 10), width=40).pack(side="left")
        ctk.CTkEntry(
            ki_frame,
            textvariable=self.pid_ki,
            font=("Georgia", 10),
            width=60
        ).pack(side="left", padx=5)
        
        # Kd
        kd_frame = ctk.CTkFrame(tune_frame, fg_color="transparent")
        kd_frame.pack(fill="x", padx=10, pady=3)
        
        ctk.CTkLabel(kd_frame, text="Kd:", font=("Georgia", 10), width=40).pack(side="left")
        ctk.CTkEntry(
            kd_frame,
            textvariable=self.pid_kd,
            font=("Georgia", 10),
            width=60
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            tune_frame,
            text="Apply Tuning",
            command=self.apply_pid_tuning,
            font=("Georgia", 10),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            height=28
        ).pack(fill="x", padx=10, pady=5)
        
        # Motor config
        motor_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        motor_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            motor_frame,
            text="⚙️ Motor Configuration:",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        steps_frame = ctk.CTkFrame(motor_frame, fg_color="transparent")
        steps_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(steps_frame, text="Steps/°C:", font=("Georgia", 10)).pack(side="left", padx=5)
        ctk.CTkEntry(
            steps_frame,
            textvariable=self.steps_per_degree,
            font=("Georgia", 10),
            width=80
        ).pack(side="left", padx=5)
        
        ctk.CTkLabel(
            motor_frame,
            text="💡 Depends on your pulley ratio",
            font=("Georgia", 9, "italic"),
            text_color=self.colors['text_light']
        ).pack(padx=10, pady=(0, 5))
        
        # Enable/Disable PID
        ctk.CTkCheckBox(
            module.content,
            text="✅ Enable PID Control",
            variable=self.pid_enabled,
            command=self.toggle_pid,
            font=("Georgia", 12, "bold"),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=10)
        
        # PID Status
        self.pid_status_label = ctk.CTkLabel(
            module.content,
            text="⏸️ PID Disabled",
            font=("Georgia", 11),
            text_color=self.colors['text_medium']
        )
        self.pid_status_label.pack(padx=10, pady=10)
    
    def setup_roi_controls(self, parent):
        """Region of Interest controls"""
        module = CollapsibleModule(parent, "🎯 Region of Interest", start_open=False)
        module.pack(fill="x", pady=5)
        
        ctk.CTkCheckBox(
            module.content,
            text="✅ Enable ROI",
            variable=self.roi_enabled,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkButton(
            module.content,
            text="🗑️ Clear ROI",
            command=self.clear_roi,
            font=("Georgia", 11),
            fg_color=self.colors['warning'],
            hover_color=self.colors['primary_dark'],
            corner_radius=8,
            height=32
        ).pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            module.content,
            text="💡 Click and drag on video to set ROI",
            font=("Georgia", 10, "italic"),
            text_color=self.colors['text_light'],
            wraplength=350
        ).pack(padx=10, pady=5)
    
    def setup_display_controls(self, parent):
        """Display options"""
        module = CollapsibleModule(parent, "👁️ Display Options", start_open=False)
        module.pack(fill="x", pady=5)
        
        ctk.CTkCheckBox(
            module.content,
            text="📊 Show Histogram",
            variable=self.show_histogram,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        ctk.CTkCheckBox(
            module.content,
            text="🎨 Color Picker Mode",
            variable=self.color_picker_mode,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
        # Zoom and pan for selected camera
        zoom_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        zoom_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            zoom_frame,
            text="🔍 Zoom & Pan Controls",
            font=("Georgia", 12, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        # Camera selection for zoom/pan
        ctk.CTkLabel(
            zoom_frame,
            text="Select Camera:",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10)
        
        self.zoom_camera_var = ctk.StringVar(value="0")
        self.zoom_camera_menu = ctk.CTkOptionMenu(
            zoom_frame,
            values=["0"],
            variable=self.zoom_camera_var,
            font=("Georgia", 10),
            fg_color=self.colors['primary'],
            button_color=self.colors['primary_dark']
        )
        self.zoom_camera_menu.pack(fill="x", padx=10, pady=5)
        
        # Zoom slider
        ctk.CTkLabel(
            zoom_frame,
            text="Zoom Level:",
            font=("Georgia", 10)
        ).pack(anchor="w", padx=10)
        
        self.zoom_slider = ctk.CTkSlider(
            zoom_frame,
            from_=1.0,
            to=4.0,
            command=self.update_zoom,
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark'],
            progress_color=self.colors['secondary']
        )
        self.zoom_slider.pack(fill="x", padx=20, pady=3)
        self.zoom_slider.set(1.0)
        
        # Pan controls
        pan_controls = ctk.CTkFrame(zoom_frame, fg_color="transparent")
        pan_controls.pack(pady=5)
        
        ctk.CTkButton(
            pan_controls,
            text="⬆️",
            command=lambda: self.pan_camera(0, -20),
            width=40,
            font=("Georgia", 14),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).grid(row=0, column=1, padx=2, pady=2)
        
        ctk.CTkButton(
            pan_controls,
            text="⬅️",
            command=lambda: self.pan_camera(-20, 0),
            width=40,
            font=("Georgia", 14),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).grid(row=1, column=0, padx=2, pady=2)
        
        ctk.CTkButton(
            pan_controls,
            text="🎯",
            command=self.reset_zoom_pan,
            width=40,
            font=("Georgia", 14),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark']
        ).grid(row=1, column=1, padx=2, pady=2)
        
        ctk.CTkButton(
            pan_controls,
            text="➡️",
            command=lambda: self.pan_camera(20, 0),
            width=40,
            font=("Georgia", 14),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).grid(row=1, column=2, padx=2, pady=2)
        
        ctk.CTkButton(
            pan_controls,
            text="⬇️",
            command=lambda: self.pan_camera(0, 20),
            width=40,
            font=("Georgia", 14),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).grid(row=2, column=1, padx=2, pady=2)
    
    def setup_recording_controls(self, parent):
        """Recording and capture controls"""
        module = CollapsibleModule(parent, "🎬 Recording & Capture", start_open=False)
        module.pack(fill="x", pady=5)
        
        # Capture mode selector
        capture_frame = ctk.CTkFrame(module.content, fg_color=self.colors['bg'], corner_radius=8)
        capture_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            capture_frame,
            text="📹 Capture Mode:",
            font=("Georgia", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkOptionMenu(
            capture_frame,
            values=["Live Feed", "3 fps", "1 fps", "1 per 5 sec"],
            variable=self.capture_mode,
            font=("Georgia", 10),
            fg_color=self.colors['primary'],
            button_color=self.colors['primary_dark'],
            button_hover_color=self.colors['primary']
        ).pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(
            capture_frame,
            text="💡 Lower rates reduce processing load",
            font=("Georgia", 9, "italic"),
            text_color=self.colors['text_light'],
            wraplength=350
        ).pack(padx=10, pady=(0, 5))
        
        # Frame grab button
        ctk.CTkButton(
            module.content,
            text="📸 Frame Grab",
            command=self.frame_grab,
            font=("Georgia", 12),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary_dark'],
            corner_radius=10,
            height=40
        ).pack(fill="x", padx=10, pady=5)
        
        # Screenshot button
        ctk.CTkButton(
            module.content,
            text="📋 Screenshot to Clipboard",
            command=self.take_screenshot,
            font=("Georgia", 12),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            corner_radius=10,
            height=40
        ).pack(fill="x", padx=10, pady=5)
        
        ctk.CTkCheckBox(
            module.content,
            text="🔴 Record Video",
            variable=self.is_recording,
            command=self.toggle_recording,
            font=("Georgia", 11),
            fg_color=self.colors['warning'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=5)
        
        ctk.CTkButton(
            module.content,
            text="❌ Quit",
            command=self.quit_app,
            font=("Georgia", 12, "bold"),
            fg_color=self.colors['warning'],
            hover_color="#FF9090",
            corner_radius=10,
            height=40
        ).pack(fill="x", padx=10, pady=10)
    
    def detect_cameras(self):
        """Detect available cameras with improved logic"""
        # Clear existing cameras
        for cam in self.cameras.values():
            cam.release()
        self.cameras.clear()
        
        # Clear existing checkboxes
        for widget in self.camera_list_frame.winfo_children():
            widget.destroy()
        self.camera_checkboxes.clear()
        
        # Detect cameras - stop after 2 consecutive failures
        consecutive_failures = 0
        max_failures = 2
        
        for i in range(10):  # Check up to 10 indices
            if consecutive_failures >= max_failures:
                break
            
            camera = CameraFeed(i)
            if camera.open():
                self.cameras[i] = camera
                self.add_camera_checkbox(i, camera.name)
                consecutive_failures = 0  # Reset failure counter
                
                # Set first camera as active by default
                if len(self.active_cameras) == 0:
                    self.active_cameras.append(i)
                    self.selected_camera = i
            else:
                consecutive_failures += 1
                camera.release()
        
        # Update zoom camera dropdown with all detected cameras
        self.update_zoom_camera_dropdown()
        
        if not self.cameras:
            self.status_label.configure(
                text="⚠️ No cameras detected",
                text_color=self.colors['warning']
            )
        else:
            self.status_label.configure(
                text=f"✅ {len(self.cameras)} camera(s) detected",
                text_color=self.colors['success']
            )
    
    def update_zoom_camera_dropdown(self):
        """Update the zoom/pan camera dropdown with all detected cameras"""
        camera_names = [f"{idx}: {cam.name}" for idx, cam in self.cameras.items()]
        if camera_names:
            self.zoom_camera_menu.configure(values=camera_names)
            # Set to first camera by default
            first_idx = list(self.cameras.keys())[0]
            self.zoom_camera_var.set(f"{first_idx}: {self.cameras[first_idx].name}")
    
    def add_camera_checkbox(self, camera_idx, camera_name):
        """Add checkbox for camera selection"""
        var = ctk.BooleanVar(value=(camera_idx == 0))
        
        checkbox = ctk.CTkCheckBox(
            self.camera_list_frame,
            text=camera_name,
            variable=var,
            command=lambda: self.toggle_camera(camera_idx),
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        )
        checkbox.pack(anchor="w", padx=10, pady=3)
        
        self.camera_checkboxes[camera_idx] = var
    
    def toggle_camera(self, camera_idx):
        """Toggle camera active state"""
        if self.camera_checkboxes[camera_idx].get():
            if camera_idx not in self.active_cameras:
                self.active_cameras.append(camera_idx)
                if self.selected_camera is None:
                    self.selected_camera = camera_idx
        else:
            if camera_idx in self.active_cameras:
                self.active_cameras.remove(camera_idx)
                if self.selected_camera == camera_idx:
                    self.selected_camera = self.active_cameras[0] if self.active_cameras else None
    
    def update_zoom(self, value):
        """Update zoom for selected camera"""
        camera_idx = self.get_selected_zoom_camera()
        if camera_idx is not None and camera_idx in self.cameras:
            self.cameras[camera_idx].zoom_level = float(value)
    
    def pan_camera(self, dx, dy):
        """Pan selected camera"""
        camera_idx = self.get_selected_zoom_camera()
        if camera_idx is not None and camera_idx in self.cameras:
            self.cameras[camera_idx].pan_x += dx
            self.cameras[camera_idx].pan_y += dy
    
    def reset_zoom_pan(self):
        """Reset zoom and pan for selected camera"""
        camera_idx = self.get_selected_zoom_camera()
        if camera_idx is not None and camera_idx in self.cameras:
            self.cameras[camera_idx].zoom_level = 1.0
            self.cameras[camera_idx].pan_x = 0
            self.cameras[camera_idx].pan_y = 0
            self.zoom_slider.set(1.0)
    
    def get_selected_zoom_camera(self):
        """Get the camera index from zoom camera dropdown"""
        try:
            # Extract camera index from "0: Built-in Webcam" format
            return int(self.zoom_camera_var.get().split(":")[0])
        except:
            return None
    
    def on_mouse_down(self, event):
        """Handle mouse button press for ROI"""
        if self.roi_enabled.get():
            self.roi_drawing = True
            self.roi_start = (event.x, event.y)
    
    def on_mouse_drag(self, event):
        """Handle mouse drag for ROI"""
        if self.roi_drawing and self.roi_start:
            x1, y1 = self.roi_start
            x2, y2 = event.x, event.y
            self.roi_coords = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    
    def on_mouse_up(self, event):
        """Handle mouse button release"""
        if self.roi_drawing:
            self.roi_drawing = False
    
    def on_double_click(self, event):
        """Handle double-click for full view"""
        if self.view_mode.get() == "grid":
            # Determine which camera was clicked
            # This is simplified - would need proper grid position calculation
            if self.active_cameras:
                self.previous_view_mode = "grid"
                self.selected_camera = self.active_cameras[0]
                self.view_mode.set("single")
        elif self.view_mode.get() == "single" and self.previous_view_mode == "grid":
            # Return to grid view
            self.view_mode.set("grid")
            self.previous_view_mode = None
    
    def clear_roi(self):
        """Clear ROI selection"""
        self.roi_coords = None
    
    def load_calibration(self):
        """Load calibration from file"""
        if os.path.exists(self.calibration_file):
            try:
                with open(self.calibration_file, 'r') as f:
                    data = json.load(f)
                    value = data.get('pixels_per_mm', 1.0)
                    # Prevent division by zero
                    if value <= 0:
                        value = 1.0
                    self.pixels_per_mm.set(value)
            except:
                self.pixels_per_mm.set(1.0)
        else:
            self.pixels_per_mm.set(1.0)
    
    def save_calibration(self):
        """Save calibration to file"""
        # Validate before saving
        value = self.pixels_per_mm.get()
        if value <= 0:
            value = 1.0
            self.pixels_per_mm.set(value)
            self.status_label.configure(
                text="⚠️ Calibration must be > 0, set to 1.0",
                text_color=self.colors['warning']
            )
            self.after(2000, lambda: self.status_label.configure(
                text="🎥 Ready",
                text_color=self.colors['text_medium']
            ))
            return
        
        data = {'pixels_per_mm': value}
        with open(self.calibration_file, 'w') as f:
            json.dump(data, f)
        
        self.status_label.configure(
            text="✅ Calibration saved!",
            text_color=self.colors['success']
        )
        self.after(2000, lambda: self.status_label.configure(
            text="🎥 Ready",
            text_color=self.colors['text_medium']
        ))
    
    def frame_grab(self):
        """Save the current processed frame with visible confirmation"""
        if self.selected_camera is not None and self.selected_camera in self.cameras:
            frame = self.cameras[self.selected_camera].last_frame
            if frame is not None:
                # Process the frame the same way it's displayed
                processed = self.process_frame(frame.copy())
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Save to current directory (where script is running)
                filename = f"frame_grab_{timestamp}.png"
                filepath = os.path.abspath(filename)
                
                cv2.imwrite(filepath, processed)
                
                self.status_label.configure(
                    text=f"✅ Saved: {filename}",
                    text_color=self.colors['success']
                )
        elif self.static_mode and self.static_image is not None:
            # Save static image with processing
            processed = self.process_frame(self.static_image.copy())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"frame_grab_{timestamp}.png"
            filepath = os.path.abspath(filename)
            
            cv2.imwrite(filepath, processed)
            
            self.status_label.configure(
                text=f"✅ Saved: {filename}",
                text_color=self.colors['success']
            )
    
    def take_screenshot(self):
        """Capture the entire program window to clipboard"""
        if not HAS_CLIPBOARD:
            self.status_label.configure(
                text="❌ Clipboard not available on this platform",
                text_color=self.colors['warning']
            )
            return
        
        try:
            # Get window position and size
            x = self.winfo_rootx()
            y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            
            if IS_WINDOWS:
                # Windows: Use PIL ImageGrab
                screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                
                # Copy to clipboard
                output = io.BytesIO()
                screenshot.convert('RGB').save(output, 'BMP')
                data = output.getvalue()[14:]  # Remove BMP header
                output.close()
                
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
                
            elif IS_LINUX:
                # Linux/Pi: Use scrot + xclip
                # First save to temp file
                temp_file = "/tmp/opencv_screenshot.png"
                
                # Capture using scrot or import (ImageMagick)
                try:
                    # Try scrot first (faster)
                    subprocess.run([
                        'scrot', '-a', f'{x},{y},{w},{h}', temp_file
                    ], check=True, capture_output=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    try:
                        # Fall back to import (ImageMagick)
                        subprocess.run([
                            'import', '-window', 'root',
                            '-crop', f'{w}x{h}+{x}+{y}',
                            temp_file
                        ], check=True, capture_output=True)
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # Last resort: use PIL with tkinter
                        # This is less reliable but doesn't need external tools
                        self.update()  # Update window to ensure it's drawn
                        import tkinter as tk
                        # Take screenshot using Tk's postscript
                        # Note: This won't work perfectly but it's a fallback
                        self.status_label.configure(
                            text="❌ Install scrot or imagemagick: sudo apt install scrot",
                            text_color=self.colors['warning']
                        )
                        return
                
                # Copy to clipboard using xclip
                try:
                    subprocess.run([
                        'xclip', '-selection', 'clipboard',
                        '-t', 'image/png', '-i', temp_file
                    ], check=True, capture_output=True)
                    
                    # Clean up temp file
                    os.remove(temp_file)
                    
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self.status_label.configure(
                        text="❌ Install xclip: sudo apt install xclip",
                        text_color=self.colors['warning']
                    )
                    return
                    
            elif IS_MACOS:
                # macOS: Use PIL ImageGrab and pbcopy
                screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                
                # Save to temp file and copy with pbcopy
                temp_file = "/tmp/opencv_screenshot.png"
                screenshot.save(temp_file, 'PNG')
                
                subprocess.run(['osascript', '-e',
                    f'set the clipboard to (read (POSIX file "{temp_file}") as PNG picture)'],
                    check=True)
                
                os.remove(temp_file)
            
            self.status_label.configure(
                text="✅ Screenshot copied to clipboard!",
                text_color=self.colors['success']
            )
            self.after(2000, lambda: self.status_label.configure(
                text="🎥 Ready",
                text_color=self.colors['text_medium']
            ))
            
        except Exception as e:
            self.status_label.configure(
                text=f"❌ Screenshot failed: {str(e)}",
                text_color=self.colors['warning']
            )

    
    def toggle_recording(self):
        """Toggle video recording"""
        if self.is_recording.get():
            # Start recording
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_filename = f"recording_{timestamp}.avi"
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(self.recording_filename, fourcc, 20.0, (640, 480))
            
            self.status_label.configure(
                text=f"🔴 Recording: {self.recording_filename}",
                text_color=self.colors['warning']
            )
        else:
            # Stop recording
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
                
                self.status_label.configure(
                    text=f"✅ Saved: {self.recording_filename}",
                    text_color=self.colors['success']
                )
    
    def connect_arduino(self):
        """Connect to Arduino motor controller"""
        if not HAS_PID:
            return
        
        try:
            # Import here to avoid errors if not installed
            from furnace_pid_controller import FurnaceMotorController, MoltenZonePIDController
            
            # Create motor controller
            self.motor_controller = FurnaceMotorController(
                serial_port=self.arduino_port.get(),
                steps_per_degree=self.steps_per_degree.get()
            )
            
            # Try to connect
            if self.motor_controller.connect():
                self.arduino_status_label.configure(
                    text="✅ Arduino connected",
                    text_color=self.colors['success']
                )
                
                # Create PID controller
                self.pid_controller = MoltenZonePIDController(
                    motor_controller=self.motor_controller,
                    target_size_mm=self.pid_target_size.get(),
                    Kp=self.pid_kp.get(),
                    Ki=self.pid_ki.get(),
                    Kd=self.pid_kd.get()
                )
            else:
                self.arduino_status_label.configure(
                    text="❌ Connection failed",
                    text_color=self.colors['warning']
                )
                
        except Exception as e:
            self.arduino_status_label.configure(
                text=f"❌ Error: {str(e)}",
                text_color=self.colors['warning']
            )
    
    def toggle_pid(self):
        """Enable/disable PID control"""
        if not self.pid_controller:
            self.pid_enabled.set(False)
            self.pid_status_label.configure(
                text="⚠️ Connect Arduino first",
                text_color=self.colors['warning']
            )
            return
        
        if self.pid_enabled.get():
            # Enable PID
            self.pid_controller.set_target(self.pid_target_size.get())
            self.pid_controller.enable()
            self.pid_status_label.configure(
                text=f"✅ PID Active - Target: {self.pid_target_size.get()} mm",
                text_color=self.colors['success']
            )
        else:
            # Disable PID
            self.pid_controller.disable()
            self.pid_status_label.configure(
                text="⏸️ PID Disabled",
                text_color=self.colors['text_medium']
            )
    
    def apply_pid_tuning(self):
        """Apply new PID tuning parameters"""
        if self.pid_controller:
            self.pid_controller.tune(
                Kp=self.pid_kp.get(),
                Ki=self.pid_ki.get(),
                Kd=self.pid_kd.get()
            )
            self.status_label.configure(
                text="✅ PID tuning updated",
                text_color=self.colors['success']
            )
    
    def toggle_autofocus(self):
        """Toggle autofocus on/off"""
        if not IS_LINUX:
            return
        
        if self.selected_camera is None:
            self.autofocus_enabled.set(False)
            return
        
        try:
            import subprocess
            device = f"/dev/video{self.selected_camera}"
            
            if self.autofocus_enabled.get():
                # Enable autofocus
                subprocess.run([
                    'v4l2-ctl', '-d', device,
                    '-c', 'focus_automatic_continuous=1'
                ], check=True, capture_output=True)
                
                self.status_label.configure(
                    text="✅ Autofocus enabled",
                    text_color=self.colors['success']
                )
            else:
                # Disable autofocus
                subprocess.run([
                    'v4l2-ctl', '-d', device,
                    '-c', 'focus_automatic_continuous=0'
                ], check=True, capture_output=True)
                
                self.status_label.configure(
                    text="✅ Autofocus disabled",
                    text_color=self.colors['success']
                )
                
        except subprocess.CalledProcessError as e:
            self.status_label.configure(
                text="⚠️ Focus control not available on this camera",
                text_color=self.colors['warning']
            )
        except FileNotFoundError:
            self.status_label.configure(
                text="⚠️ v4l2-ctl not installed (sudo apt install v4l-utils)",
                text_color=self.colors['warning']
            )
    
    def adjust_focus(self, value):
        """Adjust manual focus"""
        if not IS_LINUX:
            return
        
        if self.selected_camera is None:
            return
        
        # Disable autofocus first if it's on
        if self.autofocus_enabled.get():
            return
        
        try:
            import subprocess
            device = f"/dev/video{self.selected_camera}"
            focus_val = int(value)
            
            # Set manual focus
            subprocess.run([
                'v4l2-ctl', '-d', device,
                '-c', f'focus_absolute={focus_val}'
            ], check=True, capture_output=True)
            
        except subprocess.CalledProcessError:
            pass  # Silently fail for smoother slider experience
        except FileNotFoundError:
            pass  # v4l2-ctl not installed


    
    def filter_contours(self, contours):
        """Filter contours based on size, aspect ratio, and solidity"""
        filtered = []
        
        min_area = self.contour_min_area.get()
        max_area = self.contour_max_area.get()
        min_aspect = self.contour_min_aspect.get()
        max_aspect = self.contour_max_aspect.get()
        min_solidity = self.contour_min_solidity.get()
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Area filter
            if area < min_area or area > max_area:
                continue
            
            # Aspect ratio filter
            x, y, w, h = cv2.boundingRect(contour)
            if h > 0:
                aspect_ratio = float(w) / h
                if aspect_ratio < min_aspect or aspect_ratio > max_aspect:
                    continue
            
            # Solidity filter (how "filled" the shape is)
            hull = cv2.convexHull(contour)
            hull_area = cv2.contourArea(hull)
            if hull_area > 0:
                solidity = area / hull_area
                if solidity < min_solidity:
                    continue
            
            filtered.append(contour)
        
        return filtered
    
    def process_frame(self, frame):
        """Apply all image processing operations"""
        original = frame.copy()
        
        # Basic adjustments
        brightness = self.brightness.get()
        if brightness != 0:
            frame = cv2.convertScaleAbs(frame, alpha=1, beta=brightness)
        
        contrast = self.contrast.get()
        if contrast != 1.0:
            frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=0)
        
        # Blur
        blur = self.blur_amount.get()
        if blur > 1:
            if blur % 2 == 0:
                blur += 1
            frame = cv2.GaussianBlur(frame, (blur, blur), 0)
        
        # Grayscale
        if self.show_gray.get():
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        
        # Morphological operations
        morph_op = self.morph_operation.get()
        if morph_op != "None":
            kernel_size = self.kernel_size.get()
            if kernel_size % 2 == 0:
                kernel_size += 1
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            
            gray_morph = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            if morph_op == "Erosion":
                processed = cv2.erode(gray_morph, kernel, iterations=1)
            elif morph_op == "Dilation":
                processed = cv2.dilate(gray_morph, kernel, iterations=1)
            elif morph_op == "Opening":
                processed = cv2.morphologyEx(gray_morph, cv2.MORPH_OPEN, kernel)
            elif morph_op == "Closing":
                processed = cv2.morphologyEx(gray_morph, cv2.MORPH_CLOSE, kernel)
            elif morph_op == "Gradient":
                processed = cv2.morphologyEx(gray_morph, cv2.MORPH_GRADIENT, kernel)
            
            frame = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
        
        # Edge detection overlay
        if self.show_edges.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_overlay = np.zeros_like(original)
            edge_overlay[edges > 0] = [0, 255, 255]
            frame = cv2.addWeighted(original, 0.7, edge_overlay, 0.3, 0)
        
        # Multi-range gradient heatmap overlay
        if self.show_threshold.get():
            gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            
            # Create multi-level heatmap
            heat_overlay = original.copy()
            
            # Define brightness ranges with different colors
            # Ultra-bright (240-255): White/yellow - molten zone
            mask_ultra = (gray >= 240) & (gray <= 255)
            if np.any(mask_ultra):
                heat_overlay[mask_ultra] = [0, 255, 255]  # Yellow
            
            # Very bright (200-239): Orange/red - heating coils
            mask_very = (gray >= 200) & (gray < 240)
            if np.any(mask_very):
                heat_overlay[mask_very] = [0, 165, 255]  # Orange
            
            # Bright (160-199): Pink - hot but not glowing
            mask_bright = (gray >= 160) & (gray < 200)
            if np.any(mask_bright):
                heat_overlay[mask_bright] = [147, 20, 255]  # Pink
            
            # Moderate (120-159): Purple - warm
            mask_moderate = (gray >= 120) & (gray < 160)
            if np.any(mask_moderate):
                heat_overlay[mask_moderate] = [255, 0, 128]  # Purple
            
            # Below threshold: Blue tint - cool
            mask_below = gray < 120
            if np.any(mask_below):
                heat_overlay[mask_below] = cv2.addWeighted(
                    original[mask_below],
                    0.8,
                    np.full_like(original[mask_below], [255, 100, 0]),  # Blue tint
                    0.2,
                    0
                )
            
            frame = cv2.addWeighted(original, 0.5, heat_overlay, 0.5, 0)
            
            # Draw contours on threshold
            threshold = self.threshold_value.get()
            _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(frame, contours, -1, (0, 255, 0), 2)
        
        # Contour detection and measurement
        if self.show_contours.get() or self.measure_width.get():
            # Determine if we're using color filtering or brightness threshold
            if self.use_color_filter.get():
                # HSV color filtering for red/orange molten zones
                hsv = cv2.cvtColor(original, cv2.COLOR_BGR2HSV)
                
                # Handle red hue wrap-around (red is at both 0 and 180)
                hue_min = self.hue_min.get()
                hue_max = self.hue_max.get()
                sat_min = self.sat_min.get()
                sat_max = self.sat_max.get()
                val_min = self.val_min.get()
                val_max = self.val_max.get()
                
                # Create mask for red/orange hues
                if hue_min <= hue_max:
                    # Normal case
                    lower = np.array([hue_min, sat_min, val_min])
                    upper = np.array([hue_max, sat_max, val_max])
                    mask = cv2.inRange(hsv, lower, upper)
                else:
                    # Red wraps around (e.g., 170-20 means 170-180 and 0-20)
                    lower1 = np.array([0, sat_min, val_min])
                    upper1 = np.array([hue_max, sat_max, val_max])
                    lower2 = np.array([hue_min, sat_min, val_min])
                    upper2 = np.array([180, sat_max, val_max])
                    mask1 = cv2.inRange(hsv, lower1, upper1)
                    mask2 = cv2.inRange(hsv, lower2, upper2)
                    mask = cv2.bitwise_or(mask1, mask2)
                
                # Apply morphological closing to fill gaps from mesh
                kernel_size = self.kernel_size.get()
                if kernel_size % 2 == 0:
                    kernel_size += 1
                kernel = np.ones((kernel_size, kernel_size), np.uint8)
                iterations = self.morph_closing_iterations.get()
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=iterations)
                
                thresh = mask
            else:
                # Traditional brightness threshold
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray, self.threshold_value.get(), 255, cv2.THRESH_BINARY)
            
            # Apply ROI mask if enabled
            if self.roi_enabled.get() and self.roi_coords:
                x1, y1, x2, y2 = self.roi_coords
                
                # Get actual image dimensions
                frame_h, frame_w = frame.shape[:2]
                
                # Get label dimensions
                label_w = self.video_label.winfo_width()
                label_h = self.video_label.winfo_height()
                
                if label_w > 0 and label_h > 0:
                    # Calculate actual display size
                    frame_aspect = frame_w / frame_h
                    label_aspect = label_w / label_h
                    
                    if frame_aspect > label_aspect:
                        display_w = label_w
                        display_h = int(label_w / frame_aspect)
                        offset_x = 0
                        offset_y = (label_h - display_h) // 2
                    else:
                        display_h = label_h
                        display_w = int(label_h * frame_aspect)
                        offset_x = (label_w - display_w) // 2
                        offset_y = 0
                    
                    # Map ROI to frame coordinates
                    fx1 = int(((x1 - offset_x) / display_w) * frame_w)
                    fy1 = int(((y1 - offset_y) / display_h) * frame_h)
                    fx2 = int(((x2 - offset_x) / display_w) * frame_w)
                    fy2 = int(((y2 - offset_y) / display_h) * frame_h)
                    
                    # Clamp to frame bounds
                    fx1 = max(0, min(fx1, frame_w))
                    fy1 = max(0, min(fy1, frame_h))
                    fx2 = max(0, min(fx2, frame_w))
                    fy2 = max(0, min(fy2, frame_h))
                    
                    # Create ROI mask
                    roi_mask = np.zeros_like(thresh)
                    roi_mask[fy1:fy2, fx1:fx2] = 255
                    
                    # Apply ROI mask to threshold
                    thresh = cv2.bitwise_and(thresh, roi_mask)
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours
            filtered_contours = self.filter_contours(contours)
            
            # Draw all filtered contours
            if self.show_contours.get():
                cv2.drawContours(frame, filtered_contours, -1, (255, 0, 255), 2)
            
            # Measure ALL filtered contours
            if self.measure_width.get() and len(filtered_contours) > 0:
                # Clear previous measurements
                self.all_measurements = []
                
                # Sort contours by area (largest first) for consistent numbering
                sorted_contours = sorted(filtered_contours, key=cv2.contourArea, reverse=True)
                
                # Measure each contour
                for idx, contour in enumerate(sorted_contours, 1):
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Select dimension to measure
                    if self.measure_dimension.get() == "width":
                        measurement = w
                        dim_label = "width"
                        draw_line_start = (x, y + h//2)
                        draw_line_end = (x + w, y + h//2)
                    else:  # height
                        measurement = h
                        dim_label = "height"
                        draw_line_start = (x + w//2, y)
                        draw_line_end = (x + w//2, y + h)
                    
                    # Validate pixels_per_mm to prevent division by zero
                    ppm = self.pixels_per_mm.get()
                    if ppm <= 0:
                        ppm = 1.0
                        self.pixels_per_mm.set(1.0)
                    
                    measurement_mm = measurement / ppm
                    
                    # Store measurement
                    self.all_measurements.append({
                        'zone': idx,
                        'pixels': measurement,
                        'mm': measurement_mm,
                        'dimension': dim_label
                    })
                    
                    # Draw measurement on frame
                    if self.show_measurements.get():
                        # Draw bounding box
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                        
                        # Draw measurement line
                        cv2.line(frame, draw_line_start, draw_line_end, (0, 255, 0), 3)
                        
                        # Draw zone number and measurement
                        cv2.putText(
                            frame,
                            f"Zone {idx}: {measurement_mm:.2f}mm",
                            (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 255),
                            2
                        )
                
                # Update measurement display list
                if self.all_measurements:
                    measurement_text = "\n".join([
                        f"Zone {m['zone']}: {m['mm']:.2f} mm ({m['pixels']} px) {m['dimension']}"
                        for m in self.all_measurements
                    ])
                    self.measurement_value_label.configure(text=measurement_text)
                    
                    # Update PID controller if enabled
                    if self.pid_enabled.get() and self.pid_controller:
                        # Get measurement for selected zone
                        zone_number = self.pid_zone_select.get()
                        if zone_number <= len(self.all_measurements):
                            zone_measurement = self.all_measurements[zone_number - 1]['mm']
                            
                            # Update PID (sends motor commands to Arduino)
                            self.pid_controller.update(zone_measurement)
                else:
                    self.measurement_value_label.configure(text="No valid contours")
            else:
                if self.measure_width.get():
                    self.measurement_value_label.configure(text="No valid contours")
                else:
                    self.measurement_value_label.configure(text="Measurement disabled")
        
        # Draw ROI rectangle (fixed coordinate mapping)
        if self.roi_enabled.get() and self.roi_coords:
            x1, y1, x2, y2 = self.roi_coords
            
            # Get actual image dimensions
            frame_h, frame_w = frame.shape[:2]
            
            # Get label dimensions
            label_w = self.video_label.winfo_width()
            label_h = self.video_label.winfo_height()
            
            if label_w > 0 and label_h > 0:
                # Calculate actual display size accounting for aspect ratio preservation
                frame_aspect = frame_w / frame_h
                label_aspect = label_w / label_h
                
                if frame_aspect > label_aspect:
                    # Frame is wider - fits to width
                    display_w = label_w
                    display_h = int(label_w / frame_aspect)
                    offset_x = 0
                    offset_y = (label_h - display_h) // 2
                else:
                    # Frame is taller - fits to height
                    display_h = label_h
                    display_w = int(label_h * frame_aspect)
                    offset_x = (label_w - display_w) // 2
                    offset_y = 0
                
                # Map click coordinates to frame coordinates
                fx1 = int(((x1 - offset_x) / display_w) * frame_w)
                fy1 = int(((y1 - offset_y) / display_h) * frame_h)
                fx2 = int(((x2 - offset_x) / display_w) * frame_w)
                fy2 = int(((y2 - offset_y) / display_h) * frame_h)
                
                # Clamp to frame bounds
                fx1 = max(0, min(fx1, frame_w))
                fy1 = max(0, min(fy1, frame_h))
                fx2 = max(0, min(fx2, frame_w))
                fy2 = max(0, min(fy2, frame_h))
                
                # Draw rectangle
                cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (255, 100, 100), 3)
                cv2.putText(
                    frame,
                    "ROI",
                    (fx1 + 10, fy1 + 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 100, 100),
                    2
                )
        
        # Histogram
        if self.show_histogram.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist_height = 100
            hist_width = 256
            hist_img = np.zeros((hist_height, hist_width, 3), dtype=np.uint8)
            
            cv2.normalize(hist, hist, 0, hist_height, cv2.NORM_MINMAX)
            
            for i in range(256):
                cv2.line(
                    hist_img,
                    (i, hist_height),
                    (i, hist_height - int(hist[i])),
                    (255, 255, 255),
                    1
                )
            
            frame[10:10+hist_height, 10:10+hist_width] = hist_img
        
        return frame
    
    def update_frame(self):
        """Capture and display video with adjustable capture rate and auto-capture"""
        current_time = time.time()
        
        # Check if it's time for auto-capture (NEW in v10.1)
        if self.check_auto_capture():
            self.auto_capture_frame()
        
        # Check capture mode timing (only for live camera, not static images)
        should_update = True
        
        if not self.static_mode:
            capture_mode = self.capture_mode.get()
            
            if capture_mode == "3 fps":
                should_update = (current_time - self.last_capture_time) >= (1.0 / 3.0)
            elif capture_mode == "1 fps":
                should_update = (current_time - self.last_capture_time) >= 1.0
            elif capture_mode == "1 per 5 sec":
                should_update = (current_time - self.last_capture_time) >= 5.0
            # "Live Feed" always updates (should_update stays True)
            
            if should_update:
                self.last_capture_time = current_time
        
        if self.static_mode and self.static_image is not None:
            # Process static image (always update for static)
            frame = self.static_image.copy()
            processed = self.process_frame(frame)
            
            # Display
            rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            
            # Resize to fit display nicely
            display_width = 900
            h, w = rgb.shape[:2]
            if w > display_width:
                scale = display_width / w
                new_w = display_width
                new_h = int(h * scale)
                rgb = cv2.resize(rgb, (new_w, new_h))
            
            img = Image.fromarray(rgb)
            ctk_image = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(img.width, img.height)
            )
            
            self.current_image = ctk_image
            self.video_label.configure(image=ctk_image, text="")
        
        elif self.view_mode.get() == "single" and self.selected_camera is not None and should_update:
            # Single camera view - only update if timing permits
            if self.selected_camera in self.cameras:
                frame = self.cameras[self.selected_camera].read()
                
                if frame is not None:
                    processed = self.process_frame(frame)
                    
                    # Record if enabled
                    if self.is_recording.get() and self.video_writer:
                        record_frame = cv2.resize(processed, (640, 480))
                        self.video_writer.write(record_frame)
                    
                    # Display
                    rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
                    
                    # Resize for display - BIGGER NOW
                    display_width = 900
                    h, w = rgb.shape[:2]
                    if w > display_width:
                        scale = display_width / w
                        new_w = display_width
                        new_h = int(h * scale)
                        rgb = cv2.resize(rgb, (new_w, new_h))
                    
                    img = Image.fromarray(rgb)
                    ctk_image = ctk.CTkImage(
                        light_image=img,
                        dark_image=img,
                        size=(img.width, img.height)
                    )
                    
                    self.current_image = ctk_image
                    self.video_label.configure(image=ctk_image, text="")
        
        elif self.view_mode.get() == "grid" and len(self.active_cameras) > 0 and should_update:
            # GRID MODE - NEW IMPLEMENTATION for v10.1
            grid_frames = []
            
            for cam_idx in self.active_cameras[:4]:  # Max 4 cameras in grid
                if cam_idx in self.cameras:
                    frame = self.cameras[cam_idx].read()
                    if frame is not None:
                        # Process each frame
                        processed = self.process_frame(frame.copy())
                        grid_frames.append(processed)
            
            if grid_frames:
                # Arrange in grid (2x2 for up to 4 cameras)
                num_cams = len(grid_frames)
                
                if num_cams == 1:
                    final_frame = grid_frames[0]
                elif num_cams == 2:
                    # Side by side
                    final_frame = np.hstack(grid_frames)
                elif num_cams == 3:
                    # Top 2, bottom 1 centered
                    top_row = np.hstack(grid_frames[:2])
                    # Pad bottom frame to match width
                    bottom_frame = grid_frames[2]
                    pad_width = top_row.shape[1] - bottom_frame.shape[1]
                    if pad_width > 0:
                        padding = np.zeros((bottom_frame.shape[0], pad_width, 3), dtype=np.uint8)
                        bottom_frame = np.hstack([padding//2, bottom_frame, padding//2])
                    final_frame = np.vstack([top_row, bottom_frame])
                else:  # 4 cameras
                    # 2x2 grid
                    top_row = np.hstack(grid_frames[:2])
                    bottom_row = np.hstack(grid_frames[2:4])
                    final_frame = np.vstack([top_row, bottom_row])
                
                # Display
                rgb = cv2.cvtColor(final_frame, cv2.COLOR_BGR2RGB)
                
                # Resize for display
                display_width = 900
                h, w = rgb.shape[:2]
                if w > display_width:
                    scale = display_width / w
                    new_w = display_width
                    new_h = int(h * scale)
                    rgb = cv2.resize(rgb, (new_w, new_h))
                
                img = Image.fromarray(rgb)
                ctk_image = ctk.CTkImage(
                    light_image=img,
                    dark_image=img,
                    size=(img.width, img.height)
                )
                
                self.current_image = ctk_image
                self.video_label.configure(image=ctk_image, text="")
        
        self.after(33, self.update_frame)
    
    def quit_app(self):
        """Clean up and exit"""
        # Disable PID and disconnect Arduino
        if self.pid_controller:
            self.pid_controller.disable()
        if self.motor_controller:
            self.motor_controller.disconnect()
        
        if self.is_recording.get() and self.video_writer:
            self.video_writer.release()
        
        # Release all cameras
        for cam in self.cameras.values():
            cam.release()
        
        self.destroy()

# Run the application
if __name__ == "__main__":
    # Print platform info
    print(f"OpenCV Vision Laboratory v10.1")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {sys.version}")
    if IS_PI:
        print("🥧 Raspberry Pi detected!")
    print("="*50)
    
    app = BeautifulOpenCVPanelV10_1()
    app.protocol("WM_DELETE_WINDOW", app.quit_app)
    app.mainloop()
