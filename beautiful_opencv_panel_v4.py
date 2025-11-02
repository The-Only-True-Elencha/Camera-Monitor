"""
Beautiful OpenCV Control Panel - Version 4.0
An elegant, feature-rich GUI for OpenCV image processing and analysis

NEW IN V4:
- Multi-camera support with proper initialization
- Camera switching without hanging
- Grid view for multiple simultaneous cameras
- Threaded camera initialization (no GUI freeze)
- Individual camera labels and controls

Author: Created for Chloe's germanium zone refining project
"""

import cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np
from datetime import datetime
import os
import threading

# Set appearance mode
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class CollapsibleModule(ctk.CTkFrame):
    """A collapsible frame that can be expanded/collapsed"""
    def __init__(self, parent, title, start_open=True, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.is_open = start_open
        self.title = title
        
        # Header button
        self.header = ctk.CTkButton(
            self,
            text=f"{'▼' if self.is_open else '▶'} {title}",
            command=self.toggle,
            font=("Georgia", 13),
            fg_color="#D4A5A5",
            hover_color="#C9A9C9",
            text_color="#4A3C4A",
            anchor="w",
            corner_radius=8
        )
        self.header.pack(fill="x", padx=5, pady=2)
        
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
    """Manages a single camera feed"""
    def __init__(self, camera_index, name=None):
        self.camera_index = camera_index
        self.name = name or f"Camera {camera_index}"
        self.cap = None
        self.is_active = False
        self.last_frame = None
        
    def open(self):
        """Open the camera"""
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            self.is_active = self.cap.isOpened()
        return self.is_active
    
    def read(self):
        """Read a frame from the camera"""
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.last_frame = frame
                return frame
        return self.last_frame
    
    def release(self):
        """Release the camera"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_active = False

class BeautifulOpenCVPanelV4:
    def __init__(self, window):
        self.window = window
        self.window.title("OpenCV Vision Laboratory v4.0 🔬")
        self.window.geometry("1400x900")
        self.window.minsize(1000, 600)
        
        # Color scheme
        self.colors = {
            'bg': '#FFF0F5',
            'card': '#FFFFFF',
            'primary': '#D4A5A5',
            'secondary': '#C9A9C9',
            'accent': '#A8C5D4',
            'text_dark': '#4A3C4A',
            'text_medium': '#6B5B6B',
            'text_light': '#8B7B8B',
            'success': '#B8D4B8',
            'warning': '#E8C4A8'
        }
        
        # Camera management
        self.cameras = {}  # Dict of camera_index: CameraFeed
        self.active_cameras = []  # List of indices currently being displayed
        self.view_mode = ctk.StringVar(value="single")  # "single" or "grid"
        self.selected_camera = ctk.IntVar(value=0)
        
        # Control variables - Basic
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
        self.video_labels = {}  # Dict to store multiple video labels for grid view
        
        # Create GUI first
        self.create_widgets()
        
        # Then initialize cameras in background (won't freeze GUI)
        self.window.after(100, self.initialize_cameras)
        
        # Start video loop
        self.update_frame()
    
    def initialize_cameras(self):
        """Detect and initialize available cameras without freezing GUI"""
        status_label = ctk.CTkLabel(
            self.main_container,
            text="🔍 Detecting cameras...",
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        )
        status_label.place(relx=0.5, rely=0.5, anchor="center")
        
        def detect_in_thread():
            # Try cameras 0-3
            found_cameras = []
            for i in range(4):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        found_cameras.append(i)
                    cap.release()
            
            # Update GUI in main thread
            self.window.after(0, lambda: self.cameras_detected(found_cameras, status_label))
        
        # Run detection in background thread
        threading.Thread(target=detect_in_thread, daemon=True).start()
    
    def cameras_detected(self, camera_indices, status_label):
        """Called when camera detection completes"""
        status_label.destroy()
        
        if not camera_indices:
            # No cameras found, show error
            error_label = ctk.CTkLabel(
                self.video_panel,
                text="❌ No cameras detected!\nPlease connect a camera and restart.",
                font=("Georgia", 14),
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
        self.selected_camera.set(first_cam)
        
        # Update camera selection UI
        self.update_camera_controls()
    
    def create_widgets(self):
        """Create the main GUI layout"""
        # Main container
        self.main_container = ctk.CTkFrame(self.window, fg_color=self.colors['bg'])
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title = ctk.CTkLabel(
            self.main_container,
            text="🔬 OpenCV Vision Laboratory v4.0 - Multi-Camera Edition",
            font=("Georgia", 22),
            text_color=self.colors['text_dark']
        )
        title.pack(pady=(0, 10))
        
        # Content area
        self.content_area = ctk.CTkFrame(self.main_container, fg_color=self.colors['bg'])
        self.content_area.pack(fill="both", expand=True)
        
        # Configure grid
        self.content_area.grid_columnconfigure(0, weight=3, minsize=600)
        self.content_area.grid_columnconfigure(1, weight=1, minsize=300)
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
            corner_radius=15
        )
        self.video_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        # Single video label (will be used for single view mode)
        self.video_label = ctk.CTkLabel(self.video_panel, text="Initializing...")
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Grid container (will be shown in grid mode)
        self.grid_container = ctk.CTkFrame(self.video_panel, fg_color="transparent")
        
        # Bind mouse events
        self.video_label.bind('<Button-1>', self.on_video_click)
        self.video_label.bind('<B1-Motion>', self.on_video_drag)
        self.video_label.bind('<ButtonRelease-1>', self.on_video_release)
    
    def create_controls_panel(self):
        """Create the scrollable controls panel"""
        controls_scroll = ctk.CTkScrollableFrame(
            self.content_area,
            fg_color=self.colors['card'],
            corner_radius=15
        )
        controls_scroll.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        
        # Camera Selection Module
        self.camera_module = CollapsibleModule(controls_scroll, "📹 Camera Selection", start_open=True,
                                               fg_color=self.colors['bg'], corner_radius=10)
        self.camera_module.pack(fill="x", padx=5, pady=5)
        self.camera_controls_content = self.camera_module.content
        
        # Placeholder until cameras are detected
        ctk.CTkLabel(
            self.camera_controls_content,
            text="Detecting cameras...",
            font=("Georgia", 11),
            text_color=self.colors['text_medium']
        ).pack(pady=10)
        
        # View Mode Module
        view_module = CollapsibleModule(controls_scroll, "👁️ View Mode", start_open=True,
                                       fg_color=self.colors['bg'], corner_radius=10)
        view_module.pack(fill="x", padx=5, pady=5)
        self.create_view_mode_controls(view_module.content)
        
        # Basic Adjustments Module
        basic_module = CollapsibleModule(controls_scroll, "📐 Basic Adjustments", start_open=True,
                                        fg_color=self.colors['bg'], corner_radius=10)
        basic_module.pack(fill="x", padx=5, pady=5)
        self.create_basic_controls(basic_module.content)
        
        # Heat Map & Threshold Module
        threshold_module = CollapsibleModule(controls_scroll, "🔥 Heat Map & Threshold", start_open=False,
                                            fg_color=self.colors['bg'], corner_radius=10)
        threshold_module.pack(fill="x", padx=5, pady=5)
        self.create_threshold_controls(threshold_module.content)
        
        # Edge Detection Module
        edge_module = CollapsibleModule(controls_scroll, "🔍 Edge Detection", start_open=False,
                                       fg_color=self.colors['bg'], corner_radius=10)
        edge_module.pack(fill="x", padx=5, pady=5)
        self.create_edge_controls(edge_module.content)
        
        # Measurement Module
        measurement_module = CollapsibleModule(controls_scroll, "📏 Measurements", start_open=False,
                                              fg_color=self.colors['bg'], corner_radius=10)
        measurement_module.pack(fill="x", padx=5, pady=5)
        self.create_measurement_controls(measurement_module.content)
        
        # ROI Module
        roi_module = CollapsibleModule(controls_scroll, "🎯 ROI Selection", start_open=False,
                                      fg_color=self.colors['bg'], corner_radius=10)
        roi_module.pack(fill="x", padx=5, pady=5)
        self.create_roi_controls(roi_module.content)
        
        # Color Picker Module
        picker_module = CollapsibleModule(controls_scroll, "🎨 Color Picker", start_open=False,
                                         fg_color=self.colors['bg'], corner_radius=10)
        picker_module.pack(fill="x", padx=5, pady=5)
        self.create_picker_controls(picker_module.content)
        
        # Advanced Processing Module
        advanced_module = CollapsibleModule(controls_scroll, "🔧 Advanced Processing", start_open=False,
                                           fg_color=self.colors['bg'], corner_radius=10)
        advanced_module.pack(fill="x", padx=5, pady=5)
        self.create_advanced_controls(advanced_module.content)
        
        # Analysis Module
        analysis_module = CollapsibleModule(controls_scroll, "📊 Analysis", start_open=False,
                                           fg_color=self.colors['bg'], corner_radius=10)
        analysis_module.pack(fill="x", padx=5, pady=5)
        self.create_analysis_controls(analysis_module.content)
        
        # Recording Module
        recording_module = CollapsibleModule(controls_scroll, "💾 Recording", start_open=False,
                                            fg_color=self.colors['bg'], corner_radius=10)
        recording_module.pack(fill="x", padx=5, pady=5)
        self.create_recording_controls(recording_module.content)
        
        # Actions Module
        actions_module = CollapsibleModule(controls_scroll, "⚙️ Actions", start_open=True,
                                          fg_color=self.colors['bg'], corner_radius=10)
        actions_module.pack(fill="x", padx=5, pady=5)
        self.create_action_controls(actions_module.content)
    
    def update_camera_controls(self):
        """Update camera selection controls after cameras are detected"""
        # Clear placeholder
        for widget in self.camera_controls_content.winfo_children():
            widget.destroy()
        
        if not self.cameras:
            ctk.CTkLabel(
                self.camera_controls_content,
                text="No cameras available",
                font=("Georgia", 11),
                text_color=self.colors['warning']
            ).pack(pady=10)
            return
        
        # Camera dropdown
        camera_options = [f"{cam.name} ({idx})" for idx, cam in self.cameras.items()]
        
        ctk.CTkLabel(
            self.camera_controls_content,
            text="Select Camera:",
            font=("Georgia", 11),
            text_color=self.colors['text_dark']
        ).pack(pady=(5, 2))
        
        self.camera_dropdown = ctk.CTkOptionMenu(
            self.camera_controls_content,
            values=camera_options,
            command=self.on_camera_dropdown_change,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            button_color=self.colors['secondary'],
            button_hover_color=self.colors['accent']
        )
        self.camera_dropdown.pack(pady=5, padx=10, fill="x")
        
        # Set default selection
        if self.active_cameras:
            idx = self.active_cameras[0]
            self.camera_dropdown.set(f"{self.cameras[idx].name} ({idx})")
    
    def on_camera_dropdown_change(self, selection):
        """Handle camera selection from dropdown"""
        # Extract camera index from selection string
        idx = int(selection.split("(")[-1].strip(")"))
        
        if self.view_mode.get() == "single":
            # Close current camera
            for cam_idx in self.active_cameras:
                if cam_idx in self.cameras:
                    self.cameras[cam_idx].release()
            
            # Open selected camera
            self.active_cameras = [idx]
            if idx in self.cameras:
                self.cameras[idx].open()
                self.selected_camera.set(idx)
    
    def create_view_mode_controls(self, parent):
        """Create view mode selection controls"""
        ctk.CTkLabel(
            parent,
            text="Display Mode:",
            font=("Georgia", 11),
            text_color=self.colors['text_dark']
        ).pack(pady=(5, 2))
        
        # Single view button
        ctk.CTkRadioButton(
            parent,
            text="Single Camera",
            variable=self.view_mode,
            value="single",
            command=self.switch_view_mode,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['secondary']
        ).pack(pady=2, padx=10, anchor="w")
        
        # Grid view button
        ctk.CTkRadioButton(
            parent,
            text="Grid View (All Cameras)",
            variable=self.view_mode,
            value="grid",
            command=self.switch_view_mode,
            font=("Georgia", 11),
            fg_color=self.colors['primary'],
            hover_color=self.colors['secondary']
        ).pack(pady=2, padx=10, anchor="w")
    
    def switch_view_mode(self):
        """Switch between single and grid view"""
        if self.view_mode.get() == "single":
            # Show single video label
            self.grid_container.pack_forget()
            self.video_label.pack(expand=True, fill="both", padx=10, pady=10)
            
            # Close all cameras except selected
            selected = self.selected_camera.get()
            for idx in list(self.cameras.keys()):
                if idx != selected:
                    self.cameras[idx].release()
            
            self.active_cameras = [selected]
            if selected in self.cameras:
                self.cameras[selected].open()
        
        else:  # grid mode
            # Hide single video label
            self.video_label.pack_forget()
            
            # Show grid container
            self.grid_container.pack(expand=True, fill="both", padx=10, pady=10)
            
            # Create grid layout
            self.create_camera_grid()
            
            # Open all available cameras
            self.active_cameras = list(self.cameras.keys())
            for idx in self.active_cameras:
                self.cameras[idx].open()
    
    def create_camera_grid(self):
        """Create grid layout for multiple cameras"""
        # Clear existing grid
        for widget in self.grid_container.winfo_children():
            widget.destroy()
        
        self.video_labels.clear()
        
        num_cameras = len(self.cameras)
        if num_cameras == 0:
            return
        
        # Determine grid layout
        if num_cameras == 1:
            rows, cols = 1, 1
        elif num_cameras == 2:
            rows, cols = 1, 2
        elif num_cameras <= 4:
            rows, cols = 2, 2
        else:
            rows, cols = 2, 3
        
        # Configure grid
        for i in range(rows):
            self.grid_container.grid_rowconfigure(i, weight=1)
        for j in range(cols):
            self.grid_container.grid_columnconfigure(j, weight=1)
        
        # Create labels for each camera
        for i, (idx, cam) in enumerate(self.cameras.items()):
            row = i // cols
            col = i % cols
            
            frame = ctk.CTkFrame(self.grid_container, fg_color=self.colors['bg'], corner_radius=10)
            frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            
            # Camera name label
            name_label = ctk.CTkLabel(
                frame,
                text=cam.name,
                font=("Georgia", 11),
                text_color=self.colors['text_dark']
            )
            name_label.pack(pady=(5, 0))
            
            # Video label
            video_label = ctk.CTkLabel(frame, text="Loading...")
            video_label.pack(expand=True, fill="both", padx=5, pady=5)
            
            self.video_labels[idx] = video_label
    
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
            font=("Georgia", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=10, anchor="w")
    
    def create_edge_controls(self, parent):
        """Create edge detection controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Edges",
            variable=self.show_edges,
            font=("Georgia", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=10, anchor="w")
        
        ctk.CTkSwitch(
            parent,
            text="Grayscale",
            variable=self.show_gray,
            font=("Georgia", 11),
            progress_color=self.colors['text_medium']
        ).pack(pady=5, padx=10, anchor="w")
    
    def create_measurement_controls(self, parent):
        """Create measurement controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Contours",
            variable=self.show_contours,
            font=("Georgia", 11),
            progress_color=self.colors['secondary']
        ).pack(pady=5, padx=10, anchor="w")
        
        ctk.CTkSwitch(
            parent,
            text="Measure Width",
            variable=self.measure_width,
            font=("Georgia", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=10, anchor="w")
        
        ctk.CTkSwitch(
            parent,
            text="Show Measurements",
            variable=self.show_measurements,
            font=("Georgia", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=10, anchor="w")
        
        self.measurement_label = ctk.CTkLabel(
            parent,
            text="Width: -- px",
            font=("Georgia", 12, "bold"),
            text_color=self.colors['text_dark']
        )
        self.measurement_label.pack(pady=10)
        
        ctk.CTkSwitch(
            parent,
            text="Kalman Filter (Smooth)",
            variable=self.kalman_enabled,
            font=("Georgia", 10),
            progress_color=self.colors['success']
        ).pack(pady=5, padx=10, anchor="w")
    
    def create_roi_controls(self, parent):
        """Create ROI controls"""
        ctk.CTkSwitch(
            parent,
            text="Enable ROI Selection",
            variable=self.roi_enabled,
            font=("Georgia", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=10, anchor="w")
        
        ctk.CTkLabel(
            parent,
            text="Click and drag on video to select ROI",
            font=("Georgia", 9),
            text_color=self.colors['text_light']
        ).pack(pady=5)
        
        ctk.CTkButton(
            parent,
            text="Clear ROI",
            command=self.clear_roi,
            font=("Georgia", 11),
            fg_color=self.colors['warning'],
            hover_color=self.colors['secondary'],
            width=120
        ).pack(pady=5)
    
    def create_picker_controls(self, parent):
        """Create color picker controls"""
        ctk.CTkSwitch(
            parent,
            text="Color Picker Mode",
            variable=self.color_picker_mode,
            font=("Georgia", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=10, anchor="w")
        
        ctk.CTkLabel(
            parent,
            text="Click on video to pick color\nfor threshold adjustment",
            font=("Georgia", 9),
            text_color=self.colors['text_light']
        ).pack(pady=5)
    
    def create_advanced_controls(self, parent):
        """Create advanced processing controls"""
        ctk.CTkSwitch(
            parent,
            text="Morphological Operations",
            variable=self.morph_enabled,
            font=("Georgia", 11),
            progress_color=self.colors['primary']
        ).pack(pady=5, padx=10, anchor="w")
        
        operations = ["erosion", "dilation", "opening", "closing"]
        
        ctk.CTkLabel(
            parent,
            text="Operation:",
            font=("Georgia", 10),
            text_color=self.colors['text_dark']
        ).pack(pady=(10, 2))
        
        for op in operations:
            ctk.CTkRadioButton(
                parent,
                text=op.capitalize(),
                variable=self.morph_operation,
                value=op,
                font=("Georgia", 10),
                fg_color=self.colors['secondary']
            ).pack(pady=2, padx=20, anchor="w")
        
        self.create_slider(parent, "Kernel Size", self.morph_kernel_size, 1, 21, self.colors['accent'])
    
    def create_analysis_controls(self, parent):
        """Create analysis controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Histogram",
            variable=self.show_histogram,
            font=("Georgia", 11),
            progress_color=self.colors['accent']
        ).pack(pady=5, padx=10, anchor="w")
    
    def create_recording_controls(self, parent):
        """Create recording controls"""
        self.record_button = ctk.CTkButton(
            parent,
            text="⏺ Start Recording",
            command=self.toggle_recording,
            font=("Georgia", 12),
            fg_color=self.colors['warning'],
            hover_color=self.colors['secondary'],
            width=180,
            height=40
        )
        self.record_button.pack(pady=10)
        
        self.record_status = ctk.CTkLabel(
            parent,
            text="Not recording",
            font=("Georgia", 10),
            text_color=self.colors['text_light']
        )
        self.record_status.pack(pady=5)
    
    def create_action_controls(self, parent):
        """Create action buttons"""
        ctk.CTkButton(
            parent,
            text="💾 Save Frame",
            command=self.save_frame,
            font=("Georgia", 12),
            fg_color=self.colors['success'],
            hover_color=self.colors['secondary'],
            width=180,
            height=36
        ).pack(pady=5)
        
        ctk.CTkButton(
            parent,
            text="🔄 Reset Controls",
            command=self.reset_controls,
            font=("Georgia", 12),
            fg_color=self.colors['accent'],
            hover_color=self.colors['secondary'],
            width=180,
            height=36
        ).pack(pady=5)
        
        ctk.CTkButton(
            parent,
            text="❌ Quit",
            command=self.quit_app,
            font=("Georgia", 12),
            fg_color=self.colors['warning'],
            hover_color=self.colors['secondary'],
            width=180,
            height=36
        ).pack(pady=5)
    
    def create_slider(self, parent, label, variable, from_, to, color):
        """Create a labeled slider"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        label_widget = ctk.CTkLabel(
            frame,
            text=label,
            font=("Georgia", 11),
            text_color=self.colors['text_dark']
        )
        label_widget.pack(anchor="w")
        
        slider = ctk.CTkSlider(
            frame,
            from_=from_,
            to=to,
            variable=variable,
            progress_color=color,
            button_color=color,
            button_hover_color=self.colors['secondary']
        )
        slider.pack(fill="x", pady=2)
        
        value_label = ctk.CTkLabel(
            frame,
            textvariable=variable,
            font=("Georgia", 10),
            text_color=self.colors['text_medium']
        )
        value_label.pack(anchor="e")
    
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
            # Start recording
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
            self.record_button.configure(text="⏹ Stop Recording", fg_color=self.colors['primary'])
            self.record_status.configure(
                text=f"Recording: {self.recording_filename}",
                text_color=self.colors['primary']
            )
        else:
            # Stop recording
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            
            self.is_recording.set(False)
            self.record_button.configure(text="⏺ Start Recording", fg_color=self.colors['warning'])
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
    
    def process_frame(self, frame):
        """Apply all processing to frame"""
        # Store original
        self.current_frame = frame.copy()
        
        # Apply ROI if set
        if self.roi_enabled.get() and self.roi_coords:
            x1, y1, x2, y2 = self.roi_coords
            height, width = frame.shape[:2]
            label_width = self.video_label.winfo_width()
            label_height = self.video_label.winfo_height()
            
            if label_width > 0 and label_height > 0:
                fx1 = int((x1 / label_width) * width)
                fy1 = int((y1 / label_height) * height)
                fx2 = int((x2 / label_width) * width)
                fy2 = int((y2 / label_height) * height)
                
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                mask[fy1:fy2, fx1:fx2] = 255
                frame = cv2.bitwise_and(frame, frame, mask=mask)
        
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
            edge_overlay[edges > 0] = [255, 255, 0]
            frame = cv2.addWeighted(original, 0.7, edge_overlay, 0.3, 0)
        
        # Heat map overlay
        if self.show_threshold.get():
            gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            threshold = self.threshold_value.get()
            _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
            
            heat_overlay = original.copy()
            heat_overlay[mask > 0] = cv2.applyColorMap(
                gray[mask > 0].reshape(-1, 1),
                cv2.COLORMAP_HOT
            ).reshape(-1, 3)
            
            frame = cv2.addWeighted(original, 0.6, heat_overlay, 0.4, 0)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(frame, contours, -1, (0, 255, 0), 2)
        
        # Contour detection
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
                self.measurement_label.configure(text=f"Width: {width_measurement} px")
                
                # Draw measurement on frame
                if self.show_measurements.get():
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                    cv2.putText(frame, f"{width_measurement}px", (x, y-10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Draw ROI rectangle
        if self.roi_enabled.get() and self.roi_coords:
            x1, y1, x2, y2 = self.roi_coords
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
        
        # Histogram
        if self.show_histogram.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist_height = 100
            hist_width = 256
            hist_img = np.zeros((hist_height, hist_width, 3), dtype=np.uint8)
            
            cv2.normalize(hist, hist, 0, hist_height, cv2.NORM_MINMAX)
            
            for i in range(256):
                cv2.line(hist_img, (i, hist_height), 
                        (i, hist_height - int(hist[i])),
                        (255, 255, 255), 1)
            
            frame[10:10+hist_height, 10:10+hist_width] = hist_img
        
        return frame
    
    def update_frame(self):
        """Capture and display video"""
        if self.view_mode.get() == "single":
            # Single camera view
            if self.active_cameras and self.active_cameras[0] in self.cameras:
                cam_idx = self.active_cameras[0]
                frame = self.cameras[cam_idx].read()
                
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
                    ctk_image = ctk.CTkImage(light_image=img, dark_image=img,
                                            size=(img.width, img.height))
                    
                    self.current_image = ctk_image
                    self.video_label.configure(image=ctk_image, text="")
        
        else:  # grid mode
            # Multi-camera grid view
            for cam_idx in self.active_cameras:
                if cam_idx in self.cameras and cam_idx in self.video_labels:
                    frame = self.cameras[cam_idx].read()
                    
                    if frame is not None:
                        processed = self.process_frame(frame)
                        rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
                        
                        # Resize for grid
                        h, w = rgb.shape[:2]
                        grid_width = 300
                        scale = grid_width / w
                        new_w = grid_width
                        new_h = int(h * scale)
                        rgb = cv2.resize(rgb, (new_w, new_h))
                        
                        img = Image.fromarray(rgb)
                        ctk_image = ctk.CTkImage(light_image=img, dark_image=img,
                                                size=(img.width, img.height))
                        
                        self.video_labels[cam_idx].configure(image=ctk_image, text="")
        
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
    app = BeautifulOpenCVPanelV4(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()
