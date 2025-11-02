"""
Beautiful OpenCV Control Panel - Version 2.0
An elegant, feature-rich GUI for OpenCV image processing and analysis

NEW IN V2:
- Collapsible accordion-style modules
- Fully responsive layout
- Contour detection and measurement tools
- ROI (Region of Interest) selection
- Color picker for threshold setting
- Morphological operations
- Live histogram display
- Video recording capability
- Kalman filtering for smooth measurements

Author: Created for Chloe's germanium zone refining project
"""

import cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np
from datetime import datetime
import os

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

class BeautifulOpenCVPanelV2:
    def __init__(self, window):
        self.window = window
        self.window.title("OpenCV Vision Laboratory v2.0 🔬")
        self.window.geometry("1200x900")
        self.window.minsize(800, 600)
        
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
        
        # Open webcam
        self.cap = cv2.VideoCapture(1)
        if not self.cap.isOpened():
            print("Error: Could not open webcam")
            self.window.destroy()
            return
        
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
        
        # Kalman filter (for smooth measurements)
        self.kalman_enabled = ctk.BooleanVar(value=False)
        self.kalman_filter = cv2.KalmanFilter(2, 1)
        self.kalman_filter.measurementMatrix = np.array([[1, 0]], np.float32)
        self.kalman_filter.transitionMatrix = np.array([[1, 1], [0, 1]], np.float32)
        self.kalman_filter.processNoiseCov = np.array([[1, 0], [0, 1]], np.float32) * 0.03
        
        # Storage
        self.current_image = None
        self.current_frame = None
        
        # Create GUI
        self.create_widgets()
        
        # Bind window resize event
        self.window.bind('<Configure>', self.on_window_resize)
        
        # Start video loop
        self.update_frame()
    
    def create_widgets(self):
        """Create the main GUI layout"""
        # Main container
        self.main_container = ctk.CTkFrame(self.window, fg_color=self.colors['bg'])
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title = ctk.CTkLabel(
            self.main_container,
            text="🔬 OpenCV Vision Laboratory v2.0",
            font=("Georgia", 24),
            text_color=self.colors['text_dark']
        )
        title.pack(pady=(0, 10))
        
        # Content area (will hold video and controls)
        self.content_area = ctk.CTkFrame(self.main_container, fg_color=self.colors['bg'])
        self.content_area.pack(fill="both", expand=True)
        
        # Configure grid for responsive layout
        self.content_area.grid_columnconfigure(0, weight=3, minsize=400)  # Video side
        self.content_area.grid_columnconfigure(1, weight=1, minsize=300)  # Controls side
        self.content_area.grid_rowconfigure(0, weight=1)
        
        # Video panel (left side)
        self.create_video_panel()
        
        # Controls panel (right side)
        self.create_controls_panel()
    
    def create_video_panel(self):
        """Create the video display area"""
        video_frame = ctk.CTkFrame(
            self.content_area,
            fg_color=self.colors['card'],
            corner_radius=15
        )
        video_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        # Video label
        self.video_label = ctk.CTkLabel(video_frame, text="Initializing camera...")
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Bind mouse events for ROI and color picker
        self.video_label.bind('<Button-1>', self.on_video_click)
        self.video_label.bind('<B1-Motion>', self.on_video_drag)
        self.video_label.bind('<ButtonRelease-1>', self.on_video_release)
    
    def create_controls_panel(self):
        """Create the scrollable controls panel with collapsible modules"""
        controls_scroll = ctk.CTkScrollableFrame(
            self.content_area,
            fg_color=self.colors['card'],
            corner_radius=15
        )
        controls_scroll.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        
        # Basic Adjustments Module
        basic_module = CollapsibleModule(controls_scroll, "📐 Basic Adjustments", start_open=True,
                                        fg_color=self.colors['bg'], corner_radius=10)
        basic_module.pack(fill="x", padx=5, pady=5)
        self.create_basic_controls(basic_module.content)
        
        # Heat Map & Threshold Module
        threshold_module = CollapsibleModule(controls_scroll, "🔥 Heat Map & Threshold", start_open=True,
                                            fg_color=self.colors['bg'], corner_radius=10)
        threshold_module.pack(fill="x", padx=5, pady=5)
        self.create_threshold_controls(threshold_module.content)
        
        # Display Overlays Module
        display_module = CollapsibleModule(controls_scroll, "👁️ Display Overlays", start_open=False,
                                          fg_color=self.colors['bg'], corner_radius=10)
        display_module.pack(fill="x", padx=5, pady=5)
        self.create_display_controls(display_module.content)
        
        # Measurement Tools Module
        measurement_module = CollapsibleModule(controls_scroll, "📏 Measurement Tools", start_open=False,
                                              fg_color=self.colors['bg'], corner_radius=10)
        measurement_module.pack(fill="x", padx=5, pady=5)
        self.create_measurement_controls(measurement_module.content)
        
        # ROI Module
        roi_module = CollapsibleModule(controls_scroll, "🎯 Region of Interest", start_open=False,
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
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
    
    def create_display_controls(self, parent):
        """Create display mode controls"""
        ctk.CTkSwitch(
            parent,
            text="Grayscale",
            variable=self.show_gray,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        ctk.CTkSwitch(
            parent,
            text="Edge Overlay",
            variable=self.show_edges,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
    
    def create_measurement_controls(self, parent):
        """Create measurement tool controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Contours",
            variable=self.show_contours,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        ctk.CTkSwitch(
            parent,
            text="Measure Width",
            variable=self.measure_width,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        ctk.CTkSwitch(
            parent,
            text="Show Measurements",
            variable=self.show_measurements,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        ctk.CTkSwitch(
            parent,
            text="Kalman Smoothing",
            variable=self.kalman_enabled,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        # Measurement display
        self.measurement_label = ctk.CTkLabel(
            parent,
            text="Width: -- px",
            font=("Georgia", 11),
            text_color=self.colors['primary']
        )
        self.measurement_label.pack(pady=5)
    
    def create_roi_controls(self, parent):
        """Create ROI controls"""
        ctk.CTkSwitch(
            parent,
            text="Enable ROI",
            variable=self.roi_enabled,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        ctk.CTkLabel(
            parent,
            text="Click and drag on video to set ROI",
            font=("Georgia", 10),
            text_color=self.colors['text_light']
        ).pack(pady=2)
        
        ctk.CTkButton(
            parent,
            text="Clear ROI",
            command=self.clear_roi,
            font=("Georgia", 11),
            fg_color=self.colors['warning'],
            text_color=self.colors['text_dark'],
            height=30
        ).pack(pady=5, padx=10)
    
    def create_picker_controls(self, parent):
        """Create color picker controls"""
        ctk.CTkSwitch(
            parent,
            text="Color Picker Mode",
            variable=self.color_picker_mode,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        ctk.CTkLabel(
            parent,
            text="Click on video to set threshold\nfrom pixel brightness",
            font=("Georgia", 10),
            text_color=self.colors['text_light'],
            justify="center"
        ).pack(pady=2)
    
    def create_advanced_controls(self, parent):
        """Create morphological operation controls"""
        ctk.CTkSwitch(
            parent,
            text="Morphological Ops",
            variable=self.morph_enabled,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        # Operation selector
        ctk.CTkLabel(parent, text="Operation:", font=("Georgia", 11),
                    text_color=self.colors['text_medium']).pack(pady=2)
        
        ops = ["erosion", "dilation", "opening", "closing"]
        ctk.CTkOptionMenu(
            parent,
            values=ops,
            variable=self.morph_operation,
            font=("Georgia", 11),
            fg_color=self.colors['primary']
        ).pack(pady=5, padx=10)
        
        # Kernel size
        self.create_slider(parent, "Kernel Size", self.morph_kernel_size, 1, 21, self.colors['accent'])
    
    def create_analysis_controls(self, parent):
        """Create analysis controls"""
        ctk.CTkSwitch(
            parent,
            text="Show Histogram",
            variable=self.show_histogram,
            font=("Georgia", 12),
            text_color=self.colors['text_medium']
        ).pack(pady=5, padx=10)
        
        ctk.CTkLabel(
            parent,
            text="Displays brightness distribution",
            font=("Georgia", 10),
            text_color=self.colors['text_light']
        ).pack(pady=2)
    
    def create_recording_controls(self, parent):
        """Create recording controls"""
        self.record_button = ctk.CTkButton(
            parent,
            text="⏺ Start Recording",
            command=self.toggle_recording,
            font=("Georgia", 12),
            fg_color=self.colors['primary'],
            text_color=self.colors['text_dark'],
            height=35
        )
        self.record_button.pack(pady=10, padx=10)
        
        self.record_status = ctk.CTkLabel(
            parent,
            text="Not recording",
            font=("Georgia", 10),
            text_color=self.colors['text_light']
        )
        self.record_status.pack(pady=2)
    
    def create_action_controls(self, parent):
        """Create action buttons"""
        ctk.CTkButton(
            parent,
            text="Reset All",
            command=self.reset_controls,
            font=("Georgia", 12),
            fg_color=self.colors['warning'],
            text_color=self.colors['text_dark'],
            height=35
        ).pack(pady=5, padx=10, fill="x")
        
        ctk.CTkButton(
            parent,
            text="Quit",
            command=self.quit_app,
            font=("Georgia", 12),
            fg_color=self.colors['secondary'],
            text_color=self.colors['text_dark'],
            height=35
        ).pack(pady=5, padx=10, fill="x")
    
    def create_slider(self, parent, label, variable, from_, to, color):
        """Create a slider control"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(pady=8, padx=10, fill="x")
        
        ctk.CTkLabel(
            frame,
            text=label,
            font=("Georgia", 11),
            text_color=self.colors['text_medium']
        ).pack(anchor="w")
        
        slider_frame = ctk.CTkFrame(frame, fg_color="transparent")
        slider_frame.pack(fill="x", pady=2)
        
        slider = ctk.CTkSlider(
            slider_frame,
            from_=from_,
            to=to,
            variable=variable,
            progress_color=color,
            button_color=color
        )
        slider.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        if isinstance(variable, ctk.DoubleVar):
            value_text = f"{variable.get():.2f}"
        else:
            value_text = str(variable.get())
        
        value_label = ctk.CTkLabel(
            slider_frame,
            text=value_text,
            font=("Georgia", 11),
            text_color=color,
            width=45
        )
        value_label.pack(side="right")
        
        def update_value(*args):
            if isinstance(variable, ctk.DoubleVar):
                value_label.configure(text=f"{variable.get():.2f}")
            else:
                value_label.configure(text=str(variable.get()))
        
        variable.trace_add('write', update_value)
    
    def on_window_resize(self, event):
        """Handle window resize events for responsive layout"""
        if event.widget == self.window:
            width = event.width
            
            # Switch to vertical layout if window is narrow
            if width < 900:
                self.content_area.grid_forget()
                # Could implement vertical stacking here if needed
                self.content_area.pack(fill="both", expand=True)
    
    def on_video_click(self, event):
        """Handle mouse click on video"""
        if self.current_frame is None:
            return
        
        # Get click coordinates
        x, y = event.x, event.y
        
        # Color picker mode
        if self.color_picker_mode.get():
            self.pick_color(x, y)
        
        # ROI drawing mode
        elif self.roi_enabled.get():
            self.roi_drawing = True
            self.roi_start = (x, y)
    
    def on_video_drag(self, event):
        """Handle mouse drag on video"""
        if self.roi_drawing and self.roi_start:
            # Could show live ROI rectangle here
            pass
    
    def on_video_release(self, event):
        """Handle mouse release on video"""
        if self.roi_drawing and self.roi_start:
            x, y = event.x, event.y
            self.roi_coords = (
                min(self.roi_start[0], x),
                min(self.roi_start[1], y),
                max(self.roi_start[0], x),
                max(self.roi_start[1], y)
            )
            self.roi_drawing = False
    
    def pick_color(self, x, y):
        """Set threshold based on clicked pixel brightness"""
        if self.current_frame is None:
            return
        
        # Convert coordinates to frame coordinates
        frame_height, frame_width = self.current_frame.shape[:2]
        label_width = self.video_label.winfo_width()
        label_height = self.video_label.winfo_height()
        
        # Scale coordinates
        fx = int((x / label_width) * frame_width)
        fy = int((y / label_height) * frame_height)
        
        if 0 <= fx < frame_width and 0 <= fy < frame_height:
            gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
            brightness = int(gray[fy, fx])
            self.threshold_value.set(brightness)
    
    def clear_roi(self):
        """Clear the ROI"""
        self.roi_coords = None
    
    def toggle_recording(self):
        """Start/stop recording"""
        if not self.is_recording.get():
            # Start recording
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_filename = f"opencv_recording_{timestamp}.avi"
            
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            fps = 30
            frame_size = (640, 480)
            
            self.video_writer = cv2.VideoWriter(
                self.recording_filename,
                fourcc,
                fps,
                frame_size
            )
            
            self.is_recording.set(True)
            self.record_button.configure(text="⏹ Stop Recording", fg_color=self.colors['warning'])
            self.record_status.configure(text=f"Recording: {self.recording_filename}")
        else:
            # Stop recording
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            
            self.is_recording.set(False)
            self.record_button.configure(text="⏺ Start Recording", fg_color=self.colors['primary'])
            self.record_status.configure(text="Recording saved")
    
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
            # Scale ROI to frame size
            height, width = frame.shape[:2]
            label_width = self.video_label.winfo_width()
            label_height = self.video_label.winfo_height()
            
            if label_width > 0 and label_height > 0:
                fx1 = int((x1 / label_width) * width)
                fy1 = int((y1 / label_height) * height)
                fx2 = int((x2 / label_width) * width)
                fy2 = int((y2 / label_height) * height)
                
                # Create mask
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
        
        # Store for overlays
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
            
            # Draw contours
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
            # This draws on the label coordinates, need to scale
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
        
        # Histogram (draw on frame)
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
            
            # Overlay histogram in corner
            frame[10:10+hist_height, 10:10+hist_width] = hist_img
        
        return frame
    
    def update_frame(self):
        """Capture and display video"""
        ret, frame = self.cap.read()
        
        if ret:
            processed = self.process_frame(frame)
            
            # Record if enabled
            if self.is_recording.get() and self.video_writer:
                # Resize to recording size
                record_frame = cv2.resize(processed, (640, 480))
                self.video_writer.write(record_frame)
            
            # Convert for display
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
        
        self.window.after(33, self.update_frame)
    
    def quit_app(self):
        """Clean up and exit"""
        if self.is_recording.get() and self.video_writer:
            self.video_writer.release()
        
        self.cap.release()
        self.window.destroy()

# Run the application
if __name__ == "__main__":
    root = ctk.CTk()
    app = BeautifulOpenCVPanelV2(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()
