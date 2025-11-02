"""
Beautiful OpenCV Control Panel - Version 5.0
Modern, elegant GUI for multi-camera OpenCV processing

NEW IN V5:
- Individual camera selection (checkboxes for any combination)
- Per-camera zoom and pan controls
- Double-click camera in grid for full view
- Calibration system (pixels to real-world units)
- Better measurement display (below video)
- Fixed ROI coordinate scaling
- ROI shows box only (no masking)
- Modern pink aesthetic with professional design
- Display size controls

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

# Set appearance mode
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class CollapsibleModule(ctk.CTkFrame):
    """A collapsible frame that can be expanded/collapsed"""
    def __init__(self, parent, title, start_open=True, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.is_open = start_open
        self.title = title
        
        # Header button with modern styling
        self.header = ctk.CTkButton(
            self,
            text=f"{'▼' if self.is_open else '▶'} {title}",
            command=self.toggle,
            font=("Segoe UI", 13, "bold"),
            fg_color="#C76B98",  # Rich pink
            hover_color="#B35583",  # Darker pink
            text_color="#FFFFFF",
            anchor="w",
            corner_radius=10,
            height=40
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

class BeautifulOpenCVPanelV5:
    def __init__(self, window):
        self.window = window
        self.window.title("OpenCV Vision Laboratory v5.0 🔬")
        self.window.geometry("1600x1000")
        self.window.minsize(1200, 700)
        
        # Modern pink color scheme
        self.colors = {
            'bg': '#FFF5F9',  # Very light pink background
            'card': '#FFFFFF',  # White cards
            'primary': '#C76B98',  # Rich pink
            'primary_dark': '#B35583',  # Darker pink for hover
            'secondary': '#E8B4D0',  # Lighter pink
            'accent': '#9B59B6',  # Purple accent
            'text_dark': '#2D1B2E',  # Very dark purple
            'text_medium': '#6B4C6D',  # Medium purple
            'text_light': '#9B7A9D',  # Light purple
            'success': '#A8D5BA',  # Mint green
            'warning': '#FFB6B9',  # Coral pink
            'shadow': '#00000015'  # Subtle shadow
        }
        
        # Camera management
        self.cameras = {}
        self.active_cameras = []
        self.camera_checkboxes = {}
        self.view_mode = ctk.StringVar(value="single")
        self.selected_camera = None  # For double-click full view
        self.previous_view_mode = None  # To return from double-click
        
        # Display settings
        self.display_scale = ctk.DoubleVar(value=1.0)  # Overall display size
        
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
        
        # ROI
        self.roi_enabled = ctk.BooleanVar(value=False)
        self.roi_coords = None
        self.roi_drawing = False
        self.roi_start = None
        
        # Color picker
        self.color_picker_mode = ctk.BooleanVar(value=False)
        
        # Morphological operations
        self.morph_enabled = ctk.BooleanVar(value=False)
        self.morph_operation = ctk.StringVar(value="opening")
        self.morph_kernel_size = ctk.IntVar(value=5)
        
        # Histogram
        self.show_histogram = ctk.BooleanVar(value=False)
        
        # Recording
        self.is_recording = ctk.BooleanVar(value=False)
        self.video_writer = None
        self.recording_filename = None
        
        # Kalman filter
        self.kalman_enabled = ctk.BooleanVar(value=False)
        self.kalman_filter = cv2.KalmanFilter(2, 1)
        self.kalman_filter.measurementMatrix = np.array([[1, 0]], np.float32)
        self.kalman_filter.transitionMatrix = np.array([[1, 1], [0, 1]], np.float32)
        self.kalman_filter.processNoiseCov = np.array([[1, 0], [0, 1]], np.float32) * 0.03
        
        # Storage
        self.current_image = None
        self.current_frame = None
        self.video_labels = {}
        self.measurement_labels = {}  # For displaying measurements below each camera
        
        # Create GUI first
        self.create_widgets()
        
        # Then initialize cameras in background
        self.window.after(100, self.initialize_cameras)
        
        # Start video loop
        self.update_frame()
    
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
        try:
            with open(self.calibration_file, 'w') as f:
                json.dump({'pixels_per_mm': self.pixels_per_mm.get()}, f)
        except:
            pass
    
    def initialize_cameras(self):
        """Detect and initialize available cameras"""
        status_label = ctk.CTkLabel(
            self.main_container,
            text="🔍 Detecting cameras...",
            font=("Segoe UI", 14),
            text_color=self.colors['text_medium']
        )
        status_label.place(relx=0.5, rely=0.5, anchor="center")
        
        def detect_in_thread():
            found_cameras = []
            for i in range(4):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        found_cameras.append(i)
                    cap.release()
            
            self.window.after(0, lambda: self.cameras_detected(found_cameras, status_label))
        
        threading.Thread(target=detect_in_thread, daemon=True).start()
    
    def cameras_detected(self, camera_indices, status_label):
        """Called when camera detection completes"""
        status_label.destroy()
        
        if not camera_indices:
            error_label = ctk.CTkLabel(
                self.video_panel,
                text="❌ No cameras detected!\nPlease connect a camera and restart.",
                font=("Segoe UI", 16),
                text_color=self.colors['warning']
            )
            error_label.place(relx=0.5, rely=0.5, anchor="center")
            return
        
        # Initialize camera feeds
        for idx in camera_indices:
            name = "Built-in Camera" if idx == 0 else f"Camera {idx}"
            self.cameras[idx] = CameraFeed(idx, name)
        
        # Open first camera by default
        first_cam = camera_indices[0]
        self.cameras[first_cam].open()
        self.active_cameras = [first_cam]
        self.selected_camera = first_cam
        
        # Update UI
        self.update_camera_controls()
    
    def create_widgets(self):
        """Create the main GUI layout"""
        # Main container with shadow effect
        self.main_container = ctk.CTkFrame(
            self.window,
            fg_color=self.colors['bg'],
            corner_radius=0
        )
        self.main_container.pack(fill="both", expand=True)
        
        # Title bar
        title_bar = ctk.CTkFrame(
            self.main_container,
            fg_color=self.colors['card'],
            height=70,
            corner_radius=0
        )
        title_bar.pack(fill="x", padx=0, pady=0)
        title_bar.pack_propagate(False)
        
        title = ctk.CTkLabel(
            title_bar,
            text="🔬 OpenCV Vision Laboratory",
            font=("Segoe UI", 28, "bold"),
            text_color=self.colors['primary']
        )
        title.pack(side="left", padx=30, pady=15)
        
        version = ctk.CTkLabel(
            title_bar,
            text="v5.0",
            font=("Segoe UI", 14),
            text_color=self.colors['text_light']
        )
        version.pack(side="left", padx=10)
        
        # Content area
        self.content_area = ctk.CTkFrame(self.main_container, fg_color=self.colors['bg'])
        self.content_area.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Configure grid
        self.content_area.grid_columnconfigure(0, weight=4, minsize=800)
        self.content_area.grid_columnconfigure(1, weight=1, minsize=350)
        self.content_area.grid_rowconfigure(0, weight=1)
        
        # Video panel (left)
        self.create_video_panel()
        
        # Controls panel (right)
        self.create_controls_panel()
    
    def create_video_panel(self):
        """Create the video display area"""
        self.video_panel = ctk.CTkFrame(
            self.content_area,
            fg_color=self.colors['card'],
            corner_radius=15,
            border_width=2,
            border_color=self.colors['secondary']
        )
        self.video_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # Single video label
        self.video_label = ctk.CTkLabel(
            self.video_panel,
            text="Initializing...",
            font=("Segoe UI", 14)
        )
        self.video_label.pack(expand=True, fill="both", padx=15, pady=15)
        
        # Measurement display (below video)
        self.measurement_display = ctk.CTkFrame(
            self.video_panel,
            fg_color=self.colors['bg'],
            corner_radius=10,
            height=60
        )
        
        self.measurement_value_label = ctk.CTkLabel(
            self.measurement_display,
            text="No measurement",
            font=("Segoe UI", 20, "bold"),
            text_color=self.colors['primary']
        )
        self.measurement_value_label.pack(expand=True)
        
        # Grid container
        self.grid_container = ctk.CTkFrame(self.video_panel, fg_color="transparent")
        
        # Bind mouse events
        self.video_label.bind('<Button-1>', self.on_video_click)
        self.video_label.bind('<B1-Motion>', self.on_video_drag)
        self.video_label.bind('<ButtonRelease-1>', self.on_video_release)
        self.video_label.bind('<Double-Button-1>', self.on_video_double_click)
    
    def create_controls_panel(self):
        """Create the scrollable controls panel"""
        controls_scroll = ctk.CTkScrollableFrame(
            self.content_area,
            fg_color=self.colors['card'],
            corner_radius=15,
            border_width=2,
            border_color=self.colors['secondary']
        )
        controls_scroll.grid(row=0, column=1, sticky="nsew")
        
        # Camera Selection Module
        self.camera_module = CollapsibleModule(
            controls_scroll,
            "📹 Camera Selection",
            start_open=True,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        self.camera_module.pack(fill="x", padx=10, pady=5)
        self.camera_controls_content = self.camera_module.content
        
        ctk.CTkLabel(
            self.camera_controls_content,
            text="Detecting cameras...",
            font=("Segoe UI", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=15)
        
        # Zoom & Pan Module
        zoom_module = CollapsibleModule(
            controls_scroll,
            "🔍 Zoom & Pan",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        zoom_module.pack(fill="x", padx=10, pady=5)
        self.create_zoom_controls(zoom_module.content)
        
        # Calibration Module
        cal_module = CollapsibleModule(
            controls_scroll,
            "📐 Calibration",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        cal_module.pack(fill="x", padx=10, pady=5)
        self.create_calibration_controls(cal_module.content)
        
        # Basic Adjustments Module
        basic_module = CollapsibleModule(
            controls_scroll,
            "⚙️ Basic Adjustments",
            start_open=True,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        basic_module.pack(fill="x", padx=10, pady=5)
        self.create_basic_controls(basic_module.content)
        
        # Threshold Module
        threshold_module = CollapsibleModule(
            controls_scroll,
            "🔥 Heat Map & Threshold",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        threshold_module.pack(fill="x", padx=10, pady=5)
        self.create_threshold_controls(threshold_module.content)
        
        # Edge Detection Module
        edge_module = CollapsibleModule(
            controls_scroll,
            "🔍 Edge Detection",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        edge_module.pack(fill="x", padx=10, pady=5)
        self.create_edge_controls(edge_module.content)
        
        # Measurement Module
        measurement_module = CollapsibleModule(
            controls_scroll,
            "📏 Measurements",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        measurement_module.pack(fill="x", padx=10, pady=5)
        self.create_measurement_controls(measurement_module.content)
        
        # ROI Module
        roi_module = CollapsibleModule(
            controls_scroll,
            "🎯 ROI Selection",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        roi_module.pack(fill="x", padx=10, pady=5)
        self.create_roi_controls(roi_module.content)
        
        # Color Picker Module
        picker_module = CollapsibleModule(
            controls_scroll,
            "🎨 Color Picker",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        picker_module.pack(fill="x", padx=10, pady=5)
        self.create_picker_controls(picker_module.content)
        
        # Advanced Processing Module
        advanced_module = CollapsibleModule(
            controls_scroll,
            "🔧 Advanced Processing",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        advanced_module.pack(fill="x", padx=10, pady=5)
        self.create_advanced_controls(advanced_module.content)
        
        # Analysis Module
        analysis_module = CollapsibleModule(
            controls_scroll,
            "📊 Analysis",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        analysis_module.pack(fill="x", padx=10, pady=5)
        self.create_analysis_controls(analysis_module.content)
        
        # Recording Module
        recording_module = CollapsibleModule(
            controls_scroll,
            "💾 Recording",
            start_open=False,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        recording_module.pack(fill="x", padx=10, pady=5)
        self.create_recording_controls(recording_module.content)
        
        # Actions Module
        actions_module = CollapsibleModule(
            controls_scroll,
            "⚡ Actions",
            start_open=True,
            fg_color=self.colors['bg'],
            corner_radius=10
        )
        actions_module.pack(fill="x", padx=10, pady=5)
        self.create_action_controls(actions_module.content)
    
    def update_camera_controls(self):
        """Update camera selection controls after cameras are detected"""
        for widget in self.camera_controls_content.winfo_children():
            widget.destroy()
        
        if not self.cameras:
            ctk.CTkLabel(
                self.camera_controls_content,
                text="No cameras available",
                font=("Segoe UI", 12),
                text_color=self.colors['warning']
            ).pack(pady=15)
            return
        
        # Select All / Deselect All buttons
        button_frame = ctk.CTkFrame(self.camera_controls_content, fg_color="transparent")
        button_frame.pack(fill="x", pady=(5, 10))
        
        ctk.CTkButton(
            button_frame,
            text="Select All",
            command=self.select_all_cameras,
            font=("Segoe UI", 11),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary_dark'],
            width=100,
            height=32,
            corner_radius=8
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="Deselect All",
            command=self.deselect_all_cameras,
            font=("Segoe UI", 11),
            fg_color=self.colors['warning'],
            hover_color=self.colors['primary_dark'],
            width=100,
            height=32,
            corner_radius=8
        ).pack(side="left", padx=5)
        
        # Camera checkboxes
        for idx, cam in self.cameras.items():
            var = ctk.BooleanVar(value=(idx in self.active_cameras))
            self.camera_checkboxes[idx] = var
            
            checkbox = ctk.CTkCheckBox(
                self.camera_controls_content,
                text=f"{cam.name}",
                variable=var,
                command=lambda i=idx: self.on_camera_checkbox_change(i),
                font=("Segoe UI", 12),
                fg_color=self.colors['primary'],
                hover_color=self.colors['primary_dark'],
                checkmark_color=self.colors['card']
            )
            checkbox.pack(pady=5, padx=15, anchor="w")
    
    def select_all_cameras(self):
        """Select all available cameras"""
        for idx, var in self.camera_checkboxes.items():
            var.set(True)
        self.update_active_cameras()
    
    def deselect_all_cameras(self):
        """Deselect all cameras"""
        for idx, var in self.camera_checkboxes.items():
            var.set(False)
        self.update_active_cameras()
    
    def on_camera_checkbox_change(self, camera_index):
        """Handle camera checkbox change"""
        self.update_active_cameras()
    
    def update_active_cameras(self):
        """Update which cameras are active based on checkboxes"""
        new_active = [idx for idx, var in self.camera_checkboxes.items() if var.get()]
        
        # Close cameras that were deselected
        for idx in self.active_cameras:
            if idx not in new_active and idx in self.cameras:
                self.cameras[idx].release()
        
        # Open newly selected cameras
        for idx in new_active:
            if idx not in self.active_cameras and idx in self.cameras:
                self.cameras[idx].open()
        
        self.active_cameras = new_active
        
        # Update grid if in grid mode
        if len(self.active_cameras) > 1:
            self.view_mode.set("grid")
            self.switch_to_grid_view()
        elif len(self.active_cameras) == 1:
            self.view_mode.set("single")
            self.selected_camera = self.active_cameras[0]
            self.switch_to_single_view()
    
    def create_zoom_controls(self, parent):
        """Create zoom and pan controls"""
        # Info label
        ctk.CTkLabel(
            parent,
            text="Controls apply to selected camera",
            font=("Segoe UI", 10),
            text_color=self.colors['text_light']
        ).pack(pady=(5, 10))
        
        # Camera selector for zoom/pan
        self.zoom_camera_var = ctk.StringVar(value="Camera 0")
        
        ctk.CTkLabel(
            parent,
            text="Camera:",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(pady=(5, 2))
        
        self.zoom_camera_dropdown = ctk.CTkOptionMenu(
            parent,
            variable=self.zoom_camera_var,
            values=["Camera 0"],
            font=("Segoe UI", 11),
            fg_color=self.colors['primary'],
            button_color=self.colors['primary_dark'],
            button_hover_color=self.colors['accent']
        )
        self.zoom_camera_dropdown.pack(pady=5, padx=15, fill="x")
        
        # Zoom slider
        ctk.CTkLabel(
            parent,
            text="Zoom Level:",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(pady=(15, 2))
        
        zoom_frame = ctk.CTkFrame(parent, fg_color="transparent")
        zoom_frame.pack(fill="x", padx=15, pady=5)
        
        self.zoom_value_label = ctk.CTkLabel(
            zoom_frame,
            text="1.0x",
            font=("Segoe UI", 11),
            text_color=self.colors['text_medium']
        )
        self.zoom_value_label.pack(side="right")
        
        self.zoom_slider = ctk.CTkSlider(
            zoom_frame,
            from_=1.0,
            to=5.0,
            command=self.on_zoom_change,
            progress_color=self.colors['primary'],
            button_color=self.colors['primary'],
            button_hover_color=self.colors['primary_dark']
        )
        self.zoom_slider.set(1.0)
        self.zoom_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Pan controls
        ctk.CTkLabel(
            parent,
            text="Pan Controls:",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(pady=(15, 5))
        
        # Arrow buttons for pan
        pan_grid = ctk.CTkFrame(parent, fg_color="transparent")
        pan_grid.pack(pady=10)
        
        # Up arrow
        ctk.CTkButton(
            pan_grid,
            text="▲",
            command=lambda: self.pan_camera(0, -20),
            width=50,
            height=50,
            font=("Segoe UI", 16),
            fg_color=self.colors['secondary'],
            hover_color=self.colors['primary']
        ).grid(row=0, column=1, padx=2, pady=2)
        
        # Left arrow
        ctk.CTkButton(
            pan_grid,
            text="◀",
            command=lambda: self.pan_camera(-20, 0),
            width=50,
            height=50,
            font=("Segoe UI", 16),
            fg_color=self.colors['secondary'],
            hover_color=self.colors['primary']
        ).grid(row=1, column=0, padx=2, pady=2)
        
        # Center button
        ctk.CTkButton(
            pan_grid,
            text="⊙",
            command=self.reset_pan,
            width=50,
            height=50,
            font=("Segoe UI", 16),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark']
        ).grid(row=1, column=1, padx=2, pady=2)
        
        # Right arrow
        ctk.CTkButton(
            pan_grid,
            text="▶",
            command=lambda: self.pan_camera(20, 0),
            width=50,
            height=50,
            font=("Segoe UI", 16),
            fg_color=self.colors['secondary'],
            hover_color=self.colors['primary']
        ).grid(row=1, column=2, padx=2, pady=2)
        
        # Down arrow
        ctk.CTkButton(
            pan_grid,
            text="▼",
            command=lambda: self.pan_camera(0, 20),
            width=50,
            height=50,
            font=("Segoe UI", 16),
            fg_color=self.colors['secondary'],
            hover_color=self.colors['primary']
        ).grid(row=2, column=1, padx=2, pady=2)
        
        ctk.CTkLabel(
            parent,
            text="Or click & drag on video to pan",
            font=("Segoe UI", 10),
            text_color=self.colors['text_light']
        ).pack(pady=5)
    
    def on_zoom_change(self, value):
        """Handle zoom slider change"""
        self.zoom_value_label.configure(text=f"{value:.1f}x")
        
        # Get selected camera from dropdown
        cam_text = self.zoom_camera_var.get()
        cam_idx = int(cam_text.split()[-1])
        
        if cam_idx in self.cameras:
            self.cameras[cam_idx].zoom_level = float(value)
    
    def pan_camera(self, dx, dy):
        """Pan the selected camera"""
        cam_text = self.zoom_camera_var.get()
        cam_idx = int(cam_text.split()[-1])
        
        if cam_idx in self.cameras:
            self.cameras[cam_idx].pan_x += dx
            self.cameras[cam_idx].pan_y += dy
    
    def reset_pan(self):
        """Reset pan to center"""
        cam_text = self.zoom_camera_var.get()
        cam_idx = int(cam_text.split()[-1])
        
        if cam_idx in self.cameras:
            self.cameras[cam_idx].pan_x = 0
            self.cameras[cam_idx].pan_y = 0
    
    def create_calibration_controls(self, parent):
        """Create calibration controls"""
        ctk.CTkLabel(
            parent,
            text="Convert pixels to millimeters",
            font=("Segoe UI", 11),
            text_color=self.colors['text_medium']
        ).pack(pady=(5, 10))
        
        # Pixels per mm input
        input_frame = ctk.CTkFrame(parent, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(
            input_frame,
            text="Pixels per mm:",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(side="left")
        
        self.cal_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.pixels_per_mm,
            width=80,
            font=("Segoe UI", 11),
            fg_color=self.colors['card'],
            border_color=self.colors['primary']
        )
        self.cal_entry.pack(side="right")
        
        # Calibration mode toggle
        ctk.CTkSwitch(
            parent,
            text="Calibration Mode",
            variable=self.calibration_mode,
            font=("Segoe UI", 11),
            progress_color=self.colors['primary']
        ).pack(pady=10, padx=15, anchor="w")
        
        ctk.CTkLabel(
            parent,
            text="Measure a known width,\nthen enter the real measurement",
            font=("Segoe UI", 10),
            text_color=self.colors['text_light']
        ).pack(pady=5)
        
        # Save/Load buttons
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(pady=10)
        
        ctk.CTkButton(
            button_frame,
            text="💾 Save",
            command=self.save_calibration,
            font=("Segoe UI", 11),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary_dark'],
            width=100,
            height=32,
            corner_radius=8
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            button_frame,
            text="📂 Load",
            command=self.load_calibration,
            font=("Segoe UI", 11),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            width=100,
            height=32,
            corner_radius=8
        ).pack(side="left", padx=5)
    
    def create_basic_controls(self, parent):
        """Create basic adjustment sliders"""
        self.create_slider(parent, "Brightness", self.brightness, -100, 100, self.colors['warning'])
        self.create_slider(parent, "Contrast", self.contrast, 0.5, 3.0, self.colors['secondary'])
        self.create_slider(parent, "Blur", self.blur_amount, 1, 31, self.colors['accent'])
    
    def create_threshold_controls(self, parent):
        """Create threshold controls"""
        self.create_slider(parent, "Threshold", self.threshold_value, 0, 255, self.colors['primary'])
        
        ctk.CTkSwitch(
            parent,
            text="Heat Map Overlay",
            variable=self.show_threshold,
            font=("Segoe UI", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=15, anchor="w")
    
    def create_edge_controls(self, parent):
        """Create edge detection controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Edges",
            variable=self.show_edges,
            font=("Segoe UI", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=15, anchor="w")
        
        ctk.CTkSwitch(
            parent,
            text="Grayscale",
            variable=self.show_gray,
            font=("Segoe UI", 11),
            progress_color=self.colors['text_medium']
        ).pack(pady=5, padx=15, anchor="w")
    
    def create_measurement_controls(self, parent):
        """Create measurement controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Contours",
            variable=self.show_contours,
            font=("Segoe UI", 11),
            progress_color=self.colors['secondary']
        ).pack(pady=5, padx=15, anchor="w")
        
        ctk.CTkSwitch(
            parent,
            text="Measure Width",
            variable=self.measure_width,
            font=("Segoe UI", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=15, anchor="w")
        
        ctk.CTkSwitch(
            parent,
            text="Show Measurements",
            variable=self.show_measurements,
            font=("Segoe UI", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=15, anchor="w")
        
        ctk.CTkSwitch(
            parent,
            text="Kalman Filter (Smooth)",
            variable=self.kalman_enabled,
            font=("Segoe UI", 11),
            progress_color=self.colors['success']
        ).pack(pady=5, padx=15, anchor="w")
    
    def create_roi_controls(self, parent):
        """Create ROI controls"""
        ctk.CTkSwitch(
            parent,
            text="Enable ROI Selection",
            variable=self.roi_enabled,
            font=("Segoe UI", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=15, anchor="w")
        
        ctk.CTkLabel(
            parent,
            text="Click and drag on video\nto select region of interest",
            font=("Segoe UI", 10),
            text_color=self.colors['text_light']
        ).pack(pady=5)
        
        ctk.CTkButton(
            parent,
            text="Clear ROI",
            command=self.clear_roi,
            font=("Segoe UI", 11),
            fg_color=self.colors['warning'],
            hover_color=self.colors['primary_dark'],
            width=140,
            height=32,
            corner_radius=8
        ).pack(pady=10)
    
    def create_picker_controls(self, parent):
        """Create color picker controls"""
        ctk.CTkSwitch(
            parent,
            text="Color Picker Mode",
            variable=self.color_picker_mode,
            font=("Segoe UI", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=15, anchor="w")
        
        ctk.CTkLabel(
            parent,
            text="Click on video to pick color\nfor threshold adjustment",
            font=("Segoe UI", 10),
            text_color=self.colors['text_light']
        ).pack(pady=5)
    
    def create_advanced_controls(self, parent):
        """Create advanced processing controls"""
        ctk.CTkSwitch(
            parent,
            text="Morphological Operations",
            variable=self.morph_enabled,
            font=("Segoe UI", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=15, anchor="w")
        
        operations = ["erosion", "dilation", "opening", "closing"]
        
        ctk.CTkLabel(
            parent,
            text="Operation:",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 2))
        
        for op in operations:
            ctk.CTkRadioButton(
                parent,
                text=op.capitalize(),
                variable=self.morph_operation,
                value=op,
                font=("Segoe UI", 11),
                fg_color=self.colors['secondary'],
                hover_color=self.colors['primary']
            ).pack(pady=2, padx=20, anchor="w")
        
        self.create_slider(parent, "Kernel Size", self.morph_kernel_size, 1, 21, self.colors['accent'])
    
    def create_analysis_controls(self, parent):
        """Create analysis controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Histogram",
            variable=self.show_histogram,
            font=("Segoe UI", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=15, anchor="w")
    
    def create_recording_controls(self, parent):
        """Create recording controls"""
        self.record_button = ctk.CTkButton(
            parent,
            text="⏺ Start Recording",
            command=self.toggle_recording,
            font=("Segoe UI", 13, "bold"),
            fg_color=self.colors['warning'],
            hover_color=self.colors['primary_dark'],
            width=200,
            height=45,
            corner_radius=10
        )
        self.record_button.pack(pady=15)
        
        self.record_status = ctk.CTkLabel(
            parent,
            text="Not recording",
            font=("Segoe UI", 11),
            text_color=self.colors['text_light']
        )
        self.record_status.pack(pady=5)
    
    def create_action_controls(self, parent):
        """Create action buttons"""
        ctk.CTkButton(
            parent,
            text="💾 Save Frame",
            command=self.save_frame,
            font=("Segoe UI", 12, "bold"),
            fg_color=self.colors['success'],
            hover_color=self.colors['primary_dark'],
            width=200,
            height=40,
            corner_radius=10
        ).pack(pady=5)
        
        ctk.CTkButton(
            parent,
            text="🔄 Reset Controls",
            command=self.reset_controls,
            font=("Segoe UI", 12, "bold"),
            fg_color=self.colors['accent'],
            hover_color=self.colors['primary_dark'],
            width=200,
            height=40,
            corner_radius=10
        ).pack(pady=5)
        
        ctk.CTkButton(
            parent,
            text="❌ Quit",
            command=self.quit_app,
            font=("Segoe UI", 12, "bold"),
            fg_color=self.colors['primary'],
            hover_color=self.colors['primary_dark'],
            width=200,
            height=40,
            corner_radius=10
        ).pack(pady=5)
    
    def create_slider(self, parent, label, variable, from_, to, color):
        """Create a labeled slider with modern styling"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=8)
        
        label_frame = ctk.CTkFrame(frame, fg_color="transparent")
        label_frame.pack(fill="x")
        
        label_widget = ctk.CTkLabel(
            label_frame,
            text=label,
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors['text_dark']
        )
        label_widget.pack(side="left")
        
        value_label = ctk.CTkLabel(
            label_frame,
            textvariable=variable,
            font=("Segoe UI", 11),
            text_color=self.colors['text_medium']
        )
        value_label.pack(side="right")
        
        slider = ctk.CTkSlider(
            frame,
            from_=from_,
            to=to,
            variable=variable,
            progress_color=color,
            button_color=color,
            button_hover_color=self.colors['primary_dark']
        )
        slider.pack(fill="x", pady=(5, 0))
    
    def switch_to_single_view(self):
        """Switch to single camera view"""
        self.grid_container.pack_forget()
        self.measurement_display.pack_forget()
        self.video_label.pack(expand=True, fill="both", padx=15, pady=15)
        self.measurement_display.pack(fill="x", padx=15, pady=(0, 15))
    
    def switch_to_grid_view(self):
        """Switch to grid view"""
        self.video_label.pack_forget()
        self.measurement_display.pack_forget()
        self.grid_container.pack(expand=True, fill="both", padx=15, pady=15)
        self.create_camera_grid()
    
    def create_camera_grid(self):
        """Create grid layout for multiple cameras"""
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        
        self.video_labels.clear()
        self.measurement_labels.clear()
        
        num_cameras = len(self.active_cameras)
        if num_cameras == 0:
            return
        
        # Determine grid layout
        if num_cameras == 1:
            rows, cols = 1, 1
        elif num_cameras == 2:
            rows, cols = 1, 2
        elif num_cameras <= 4:
            rows, cols = 2, 2
        elif num_cameras <= 6:
            rows, cols = 2, 3
        else:
            rows, cols = 3, 3
        
        # Configure grid
        for i in range(rows):
            self.grid_container.grid_rowconfigure(i, weight=1)
        for j in range(cols):
            self.grid_container.grid_columnconfigure(j, weight=1)
        
        # Create labels for each camera
        for i, idx in enumerate(self.active_cameras):
            row = i // cols
            col = i % cols
            
            cam = self.cameras[idx]
            
            frame = ctk.CTkFrame(
                self.grid_container,
                fg_color=self.colors['card'],
                corner_radius=10,
                border_width=2,
                border_color=self.colors['secondary']
            )
            frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            
            # Camera name label
            name_label = ctk.CTkLabel(
                frame,
                text=cam.name,
                font=("Segoe UI", 12, "bold"),
                text_color=self.colors['primary']
            )
            name_label.pack(pady=(8, 0))
            
            # Video label
            video_label = ctk.CTkLabel(frame, text="Loading...")
            video_label.pack(expand=True, fill="both", padx=8, pady=8)
            
            # Bind double-click for full view
            video_label.bind('<Double-Button-1>', lambda e, i=idx: self.on_grid_camera_double_click(i))
            
            # Measurement display for this camera
            meas_frame = ctk.CTkFrame(frame, fg_color=self.colors['bg'], corner_radius=8, height=40)
            meas_frame.pack(fill="x", padx=8, pady=(0, 8))
            meas_frame.pack_propagate(False)
            
            meas_label = ctk.CTkLabel(
                meas_frame,
                text="No measurement",
                font=("Segoe UI", 11),
                text_color=self.colors['text_medium']
            )
            meas_label.pack(expand=True)
            
            self.video_labels[idx] = video_label
            self.measurement_labels[idx] = meas_label
    
    def on_grid_camera_double_click(self, camera_index):
        """Handle double-click on camera in grid view"""
        self.previous_view_mode = "grid"
        self.selected_camera = camera_index
        self.view_mode.set("single")
        self.switch_to_single_view()
    
    def on_video_double_click(self, event):
        """Handle double-click on video in single view"""
        if self.previous_view_mode == "grid":
            self.view_mode.set("grid")
            self.switch_to_grid_view()
            self.previous_view_mode = None
    
    def on_video_click(self, event):
        """Handle mouse click on video"""
        if self.roi_enabled.get():
            self.roi_start = (event.x, event.y)
            self.roi_drawing = True
        elif self.color_picker_mode.get() and self.current_frame is not None:
            self.pick_color(event.x, event.y)
    
    def on_video_drag(self, event):
        """Handle mouse drag on video"""
        if self.roi_drawing and self.roi_start:
            self.roi_coords = (
                min(self.roi_start[0], event.x),
                min(self.roi_start[1], event.y),
                max(self.roi_start[0], event.x),
                max(self.roi_start[1], event.y)
            )
    
    def on_video_release(self, event):
        """Handle mouse release on video"""
        if self.roi_drawing:
            self.roi_drawing = False
    
    def clear_roi(self):
        """Clear the ROI selection"""
        self.roi_coords = None
        self.roi_enabled.set(False)
    
    def pick_color(self, x, y):
        """Pick color from video for threshold adjustment"""
        if self.current_frame is None:
            return
        
        height, width = self.current_frame.shape[:2]
        label_width = self.video_label.winfo_width()
        label_height = self.video_label.winfo_height()
        
        if label_width > 0 and label_height > 0:
            fx = int((x / label_width) * width)
            fy = int((y / label_height) * height)
            
            if 0 <= fx < width and 0 <= fy < height:
                gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
                value = gray[fy, fx]
                self.threshold_value.set(int(value))
    
    def toggle_recording(self):
        """Toggle video recording"""
        if not self.is_recording.get():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_filename = f"recording_{timestamp}.avi"
            
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(
                self.recording_filename,
                fourcc,
                20.0,
                (640, 480)
            )
            
            self.is_recording.set(True)
            self.record_button.configure(
                text="⏹ Stop Recording",
                fg_color=self.colors['primary']
            )
            self.record_status.configure(
                text=f"Recording: {self.recording_filename}",
                text_color=self.colors['primary']
            )
        else:
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            
            self.is_recording.set(False)
            self.record_button.configure(
                text="⏺ Start Recording",
                fg_color=self.colors['warning']
            )
            self.record_status.configure(
                text=f"Saved: {self.recording_filename}",
                text_color=self.colors['success']
            )
    
    def save_frame(self):
        """Save current frame as image"""
        if self.current_frame is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"frame_{timestamp}.png"
            cv2.imwrite(filename, self.current_frame)
            print(f"Saved: {filename}")
    
    def reset_controls(self):
        """Reset all controls to defaults"""
        self.brightness.set(0)
        self.contrast.set(1.0)
        self.blur_amount.set(1)
        self.threshold_value.set(127)
        self.show_edges.set(False)
        self.show_gray.set(False)
        self.show_threshold.set(False)
        self.show_contours.set(False)
        self.measure_width.set(False)
        self.show_measurements.set(False)
        self.roi_enabled.set(False)
        self.roi_coords = None
        self.color_picker_mode.set(False)
        self.morph_enabled.set(False)
        self.show_histogram.set(False)
        self.kalman_enabled.set(False)
        
        # Reset zoom/pan for all cameras
        for cam in self.cameras.values():
            cam.zoom_level = 1.0
            cam.pan_x = 0
            cam.pan_y = 0
        
        if hasattr(self, 'zoom_slider'):
            self.zoom_slider.set(1.0)
    
    def process_frame(self, frame):
        """Apply all processing to frame"""
        self.current_frame = frame.copy()
        
        # Basic adjustments
        brightness = self.brightness.get()
        contrast = self.contrast.get()
        frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)
        
        # Blur
        blur = self.blur_amount.get()
        if blur > 1:
            if blur % 2 == 0:
                blur += 1
            frame = cv2.GaussianBlur(frame, (blur, blur), 0)
        
        # Morphological operations
        if self.morph_enabled.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            kernel_size = self.morph_kernel_size.get()
            if kernel_size % 2 == 0:
                kernel_size += 1
            kernel = np.ones((kernel_size, kernel_size), np.uint8)
            
            op = self.morph_operation.get()
            if op == "erosion":
                gray = cv2.erode(gray, kernel, iterations=1)
            elif op == "dilation":
                gray = cv2.dilate(gray, kernel, iterations=1)
            elif op == "opening":
                gray = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
            elif op == "closing":
                gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            
            frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        
        original = frame.copy()
        
        # Grayscale
        if self.show_gray.get() and not self.show_edges.get() and not self.show_threshold.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        
        # Edge overlay
        if self.show_edges.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_overlay = np.zeros_like(original)
            edge_overlay[edges > 0] = [0, 255, 255]
            frame = cv2.addWeighted(original, 0.7, edge_overlay, 0.3, 0)
        
        # Heat map overlay
        if self.show_threshold.get():
            gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            threshold = self.threshold_value.get()
            _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
            
            heat_overlay = original.copy()
            if np.any(mask > 0):
                heat_overlay[mask > 0] = cv2.applyColorMap(
                    gray[mask > 0].reshape(-1, 1),
                    cv2.COLORMAP_HOT
                ).reshape(-1, 3)
            
            frame = cv2.addWeighted(original, 0.6, heat_overlay, 0.4, 0)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(frame, contours, -1, (0, 255, 0), 2)
        
        # Contour detection and measurement
        if self.show_contours.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, self.threshold_value.get(), 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(frame, contours, -1, (255, 0, 255), 2)
            
            # Measure width
            if self.measure_width.get() and len(contours) > 0:
                largest_contour = max(contours, key=cv2.contourArea)
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
                        f"{width_measurement}px",
                        (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )
            else:
                self.measurement_value_label.configure(text="No contours detected")
        
        # Draw ROI rectangle (no masking, just visual indicator)
        if self.roi_enabled.get() and self.roi_coords:
            x1, y1, x2, y2 = self.roi_coords
            
            # Scale ROI from label coords to frame coords
            height, width = frame.shape[:2]
            label_width = self.video_label.winfo_width()
            label_height = self.video_label.winfo_height()
            
            if label_width > 0 and label_height > 0:
                fx1 = int((x1 / label_width) * width)
                fy1 = int((y1 / label_height) * height)
                fx2 = int((x2 / label_width) * width)
                fy2 = int((y2 / label_height) * height)
                
                # Draw blue rectangle
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
        if self.view_mode.get() == "single" and self.selected_camera is not None:
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
                    
                    # Resize for display
                    display_width = 640
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
        
        elif self.view_mode.get() == "grid":
            # Multi-camera grid view
            for cam_idx in self.active_cameras:
                if cam_idx in self.cameras and cam_idx in self.video_labels:
                    frame = self.cameras[cam_idx].read()
                    
                    if frame is not None:
                        processed = self.process_frame(frame)
                        rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
                        
                        # Resize for grid
                        h, w = rgb.shape[:2]
                        grid_width = 350
                        scale = grid_width / w
                        new_w = grid_width
                        new_h = int(h * scale)
                        rgb = cv2.resize(rgb, (new_w, new_h))
                        
                        img = Image.fromarray(rgb)
                        ctk_image = ctk.CTkImage(
                            light_image=img,
                            dark_image=img,
                            size=(img.width, img.height)
                        )
                        
                        self.video_labels[cam_idx].configure(image=ctk_image, text="")
                        
                        # Update measurement for this camera
                        if cam_idx in self.measurement_labels:
                            if self.measured_width > 0:
                                meas_text = f"{self.measured_width_mm:.2f} mm ({int(self.measured_width)} px)"
                            else:
                                meas_text = "No measurement"
                            self.measurement_labels[cam_idx].configure(text=meas_text)
        
        self.window.after(33, self.update_frame)
    
    def quit_app(self):
        """Clean up and exit"""
        if self.is_recording.get() and self.video_writer:
            self.video_writer.release()
        
        # Release all cameras
        for cam in self.cameras.values():
            cam.release()
        
        self.window.destroy()

# Run the application
if __name__ == "__main__":
    root = ctk.CTk()
    app = BeautifulOpenCVPanelV5(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()
