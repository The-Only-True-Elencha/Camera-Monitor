"""
Beautiful OpenCV Control Panel - Version 6.0
Modern, elegant GUI for multi-camera OpenCV processing

NEW IN V6:
- Kawaii pastel color scheme (less magenta!)
- Beautiful serif fonts throughout
- Built-in webcam renamed to "Built-in Webcam"
- Fixed pan dropdown to show all cameras
- Maximized video display area (reduced white space)
- Fixed ROI click offset with proper coordinate mapping
- Multi-range gradient heatmap overlay (not just binary)
- Added Gradient morphological operation
- Reorganized UI for logical grouping
- Fixed contour measurement (no more measuring entire frame)
- Contour filtering (area, aspect ratio, solidity)
- Load static images with drag-and-drop support
- Better measurement visualization

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
from tkinterdnd2 import DND_FILES, TkinterDnD

# Set appearance mode
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class CollapsibleModule(ctk.CTkFrame):
    """A collapsible frame that can be expanded/collapsed"""
    def __init__(self, parent, title, start_open=True, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.is_open = start_open
        self.title = title
        
        # Header button with kawaii pastel styling
        self.header = ctk.CTkButton(
            self,
            text=f"{'▼' if self.is_open else '▶'} {title}",
            command=self.toggle,
            font=("Georgia", 13, "bold"),
            fg_color="#FFB5D8",  # Soft pastel pink
            hover_color="#FFA0C8",  # Slightly darker pastel pink
            text_color="#5D4E6D",  # Muted purple text
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
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
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
        
        # Crop and resize back to original size
        cropped = frame[y1:y2, x1:x2]
        zoomed = cv2.resize(cropped, (w, h))
        
        return zoomed
    
    def release(self):
        """Release the camera"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_active = False

class BeautifulOpenCVPanelV6(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("OpenCV Vision Laboratory v6.0 🔬✨")
        self.geometry("1700x1000")
        self.minsize(1400, 800)
        
        # Kawaii pastel color scheme
        self.colors = {
            'bg': '#FFF9FC',  # Barely-there pink white
            'card': '#FFFFFF',  # Pure white cards
            'primary': '#FFB5D8',  # Soft pastel pink
            'primary_dark': '#FFA0C8',  # Medium pastel pink
            'secondary': '#E8D5F2',  # Lavender
            'accent': '#B8E0F6',  # Sky blue
            'text_dark': '#5D4E6D',  # Muted purple
            'text_medium': '#8B7B9B',  # Light purple
            'text_light': '#B8AABF',  # Very light purple
            'success': '#C5E8D5',  # Mint
            'warning': '#FFD4B8',  # Peach
            'shadow': '#00000008'  # Very subtle shadow
        }
        
        # Static image mode
        self.static_image = None
        self.static_mode = False
        
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
        self.measured_width = 0.0
        self.measured_width_mm = 0.0
        
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
        
        # Enable drag and drop
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_file_drop)
        
        self.update_frame()
    
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
        
        # Measurement display below video
        measurement_frame = ctk.CTkFrame(left_panel, fg_color=self.colors['secondary'], corner_radius=10)
        measurement_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        ctk.CTkLabel(
            measurement_frame,
            text="📏 Measurement:",
            font=("Georgia", 13, "bold"),
            text_color=self.colors['text_dark']
        ).pack(side="left", padx=15, pady=10)
        
        self.measurement_value_label = ctk.CTkLabel(
            measurement_frame,
            text="No measurement",
            font=("Georgia", 13),
            text_color=self.colors['text_medium']
        )
        self.measurement_value_label.pack(side="left", padx=5, pady=10)
        
        # Right panel (controls) - More compact
        right_panel = ctk.CTkScrollableFrame(
            main_container,
            fg_color=self.colors['card'],
            corner_radius=15,
            width=420
        )
        right_panel.pack(side="right", fill="y")
        
        # Setup control modules with better organization
        self.setup_camera_controls(right_panel)
        self.setup_image_adjustment_controls(right_panel)
        self.setup_detection_controls(right_panel)
        self.setup_measurement_controls(right_panel)
        self.setup_roi_controls(right_panel)
        self.setup_display_controls(right_panel)
        self.setup_recording_controls(right_panel)
    
    def setup_camera_controls(self, parent):
        """Camera selection and view controls"""
        module = CollapsibleModule(parent, "📷 Camera Selection & View", start_open=True)
        module.pack(fill="x", pady=5)
        
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
            text="📐 Measure Width",
            variable=self.measure_width,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).pack(anchor="w", padx=10, pady=3)
        
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
        
        ctk.CTkButton(
            module.content,
            text="📸 Take Screenshot",
            command=self.take_screenshot,
            font=("Georgia", 12),
            fg_color=self.colors['success'],
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
        """Detect available cameras"""
        for i in range(5):  # Check first 5 indices
            camera = CameraFeed(i)
            if camera.open():
                self.cameras[i] = camera
                self.add_camera_checkbox(i, camera.name)
                
                # Set first camera as active by default
                if len(self.active_cameras) == 0:
                    self.active_cameras.append(i)
                    self.selected_camera = i
        
        # Update zoom camera dropdown with all detected cameras
        self.update_zoom_camera_dropdown()
        
        if not self.cameras:
            self.status_label.configure(
                text="⚠️ No cameras detected",
                text_color=self.colors['warning']
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
                    self.pixels_per_mm.set(data.get('pixels_per_mm', 1.0))
            except:
                pass
    
    def save_calibration(self):
        """Save calibration to file"""
        data = {'pixels_per_mm': self.pixels_per_mm.get()}
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
    
    def take_screenshot(self):
        """Take a screenshot"""
        if self.selected_camera is not None and self.selected_camera in self.cameras:
            frame = self.cameras[self.selected_camera].read()
            if frame is not None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
                cv2.imwrite(filename, frame)
                
                self.status_label.configure(
                    text=f"📸 Saved: {filename}",
                    text_color=self.colors['success']
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
        if self.show_contours.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, self.threshold_value.get(), 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter contours
            filtered_contours = self.filter_contours(contours)
            
            # Draw all filtered contours
            cv2.drawContours(frame, filtered_contours, -1, (255, 0, 255), 2)
            
            # Measure width
            if self.measure_width.get() and len(filtered_contours) > 0:
                # Find largest filtered contour
                largest_contour = max(filtered_contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                width_measurement = w
                
                # Apply Kalman filter if enabled
                if self.kalman_enabled.get():
                    self.kalman_filter.correct(np.array([[np.float32(width_measurement)]]))
                    prediction = self.kalman_filter.predict()
                    width_measurement = int(prediction[0][0])
                
                self.measured_width = width_measurement
                self.measured_width_mm = width_measurement / self.pixels_per_mm.get()
                
                # Update measurement display
                self.measurement_value_label.configure(
                    text=f"{self.measured_width_mm:.2f} mm ({width_measurement} px)"
                )
                
                # Draw measurement on frame
                if self.show_measurements.get():
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 3)
                    cv2.putText(
                        frame,
                        f"{self.measured_width_mm:.2f}mm",
                        (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )
            else:
                if self.measure_width.get():
                    self.measurement_value_label.configure(text="No valid contours")
        
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
        """Capture and display video"""
        if self.static_mode and self.static_image is not None:
            # Process static image
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
        
        elif self.view_mode.get() == "single" and self.selected_camera is not None:
            # Single camera view
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
        
        self.after(33, self.update_frame)
    
    def quit_app(self):
        """Clean up and exit"""
        if self.is_recording.get() and self.video_writer:
            self.video_writer.release()
        
        # Release all cameras
        for cam in self.cameras.values():
            cam.release()
        
        self.destroy()

# Run the application
if __name__ == "__main__":
    app = BeautifulOpenCVPanelV6()
    app.protocol("WM_DELETE_WINDOW", app.quit_app)
    app.mainloop()
