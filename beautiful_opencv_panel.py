"""
Beautiful OpenCV Control Panel
A modern, pretty GUI for playing with OpenCV image processing

Features:
- Live webcam feed
- Smooth rounded controls with pastel colors
- Real-time image processing
- Perfect for learning OpenCV and testing germanium zone detection
"""

import cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np

# Set appearance mode and color theme
ctk.set_appearance_mode("light")  # Light mode with pastels
ctk.set_default_color_theme("blue")

class BeautifulOpenCVPanel:
    def __init__(self, window):
        self.window = window
        self.window.title("OpenCV Vision Lab 🔬")
        self.window.geometry("900x750")
        
        # Pastel color scheme
        self.colors = {
            'bg': '#F8F9FA',
            'card': '#FFFFFF',
            'primary': '#A8C5E3',  # Soft blue
            'secondary': '#E8B4D4',  # Soft pink
            'accent': '#B8E8D4',  # Soft mint
            'text': '#2C3E50',
            'success': '#A8E6CF',  # Soft green
            'warning': '#FFD3B6'  # Soft peach
        }
        
        # Open webcam
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error: Could not open webcam")
            self.window.destroy()
            return
        
        # Control variables
        self.brightness = ctk.IntVar(value=0)
        self.contrast = ctk.DoubleVar(value=1.0)
        self.blur_amount = ctk.IntVar(value=1)
        self.show_edges = ctk.BooleanVar(value=False)
        self.show_gray = ctk.BooleanVar(value=False)
        self.show_threshold = ctk.BooleanVar(value=False)
        self.threshold_value = ctk.IntVar(value=127)
        
        # Create GUI
        self.create_widgets()
        
        # Start video loop
        self.update_frame()
    
    def create_widgets(self):
        # Main container with padding
        main_frame = ctk.CTkFrame(self.window, fg_color=self.colors['bg'])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title = ctk.CTkLabel(
            main_frame, 
            text="🎥 OpenCV Vision Lab",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=self.colors['text']
        )
        title.pack(pady=(0, 20))
        
        # Video display area (card style)
        video_card = ctk.CTkFrame(main_frame, fg_color=self.colors['card'], corner_radius=15)
        video_card.pack(pady=10, padx=10, fill="both", expand=True)
        
        self.video_label = ctk.CTkLabel(video_card, text="")
        self.video_label.pack(padx=15, pady=15)
        
        # Controls container
        controls_container = ctk.CTkFrame(main_frame, fg_color=self.colors['bg'])
        controls_container.pack(fill="both", expand=False, pady=10)
        
        # Left column - Sliders
        left_column = ctk.CTkFrame(controls_container, fg_color=self.colors['card'], corner_radius=15)
        left_column.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(
            left_column, 
            text="✨ Adjustments",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors['text']
        ).pack(pady=(15, 10))
        
        # Brightness
        self.create_slider_control(
            left_column, 
            "☀️ Brightness", 
            self.brightness, 
            -100, 100, 
            self.colors['warning']
        )
        
        # Contrast
        self.create_slider_control(
            left_column, 
            "🎨 Contrast", 
            self.contrast, 
            0.5, 3.0, 
            self.colors['secondary']
        )
        
        # Blur
        self.create_slider_control(
            left_column, 
            "🌫️ Blur", 
            self.blur_amount, 
            1, 31, 
            self.colors['accent']
        )
        
        # Threshold (important one!)
        self.create_slider_control(
            left_column, 
            "🔥 Threshold (Bright Zone Detector!)", 
            self.threshold_value, 
            0, 255, 
            self.colors['primary']
        )
        
        # Right column - Display modes
        right_column = ctk.CTkFrame(controls_container, fg_color=self.colors['card'], corner_radius=15)
        right_column.pack(side="left", fill="both", expand=True)
        
        ctk.CTkLabel(
            right_column, 
            text="👁️ Display Modes",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors['text']
        ).pack(pady=(15, 10))
        
        # Mode switches
        self.grayscale_switch = ctk.CTkSwitch(
            right_column,
            text="Grayscale",
            variable=self.show_gray,
            font=ctk.CTkFont(size=14),
            progress_color=self.colors['primary']
        )
        self.grayscale_switch.pack(pady=10, padx=20)
        
        self.edges_switch = ctk.CTkSwitch(
            right_column,
            text="Edge Detection",
            variable=self.show_edges,
            font=ctk.CTkFont(size=14),
            progress_color=self.colors['secondary']
        )
        self.edges_switch.pack(pady=10, padx=20)
        
        self.threshold_switch = ctk.CTkSwitch(
            right_column,
            text="Threshold Mode",
            variable=self.show_threshold,
            font=ctk.CTkFont(size=14),
            progress_color=self.colors['accent']
        )
        self.threshold_switch.pack(pady=10, padx=20)
        
        # Info box
        info_frame = ctk.CTkFrame(right_column, fg_color=self.colors['success'], corner_radius=10)
        info_frame.pack(pady=20, padx=15, fill="x")
        
        info_text = (
            "💡 Tip: Use Threshold Mode to isolate\n"
            "bright regions - perfect for detecting\n"
            "your molten germanium zone!"
        )
        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            text_color=self.colors['text'],
            justify="left"
        ).pack(pady=10, padx=10)
        
        # Buttons frame
        button_frame = ctk.CTkFrame(main_frame, fg_color=self.colors['bg'])
        button_frame.pack(fill="x", pady=10)
        
        reset_button = ctk.CTkButton(
            button_frame,
            text="↺ Reset All",
            command=self.reset_controls,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.colors['warning'],
            hover_color=self.colors['secondary'],
            height=40,
            corner_radius=10
        )
        reset_button.pack(side="left", expand=True, padx=5)
        
        quit_button = ctk.CTkButton(
            button_frame,
            text="✖ Quit",
            command=self.quit_app,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self.colors['secondary'],
            hover_color=self.colors['warning'],
            height=40,
            corner_radius=10
        )
        quit_button.pack(side="right", expand=True, padx=5)
    
    def create_slider_control(self, parent, label_text, variable, from_, to, color):
        """Create a pretty slider with label and value display"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(pady=10, padx=20, fill="x")
        
        # Label
        label = ctk.CTkLabel(
            frame,
            text=label_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.colors['text']
        )
        label.pack(anchor="w", pady=(0, 5))
        
        # Slider and value display frame
        slider_frame = ctk.CTkFrame(frame, fg_color="transparent")
        slider_frame.pack(fill="x")
        
        slider = ctk.CTkSlider(
            slider_frame,
            from_=from_,
            to=to,
            variable=variable,
            progress_color=color,
            button_color=color,
            button_hover_color=self.colors['primary']
        )
        slider.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        # Value display
        if isinstance(variable, ctk.DoubleVar):
            value_text = f"{variable.get():.2f}"
        else:
            value_text = str(variable.get())
        
        value_label = ctk.CTkLabel(
            slider_frame,
            text=value_text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=color,
            width=50
        )
        value_label.pack(side="right")
        
        # Update value label when slider moves
        def update_value(*args):
            if isinstance(variable, ctk.DoubleVar):
                value_label.configure(text=f"{variable.get():.2f}")
            else:
                value_label.configure(text=str(variable.get()))
        
        variable.trace_add('write', update_value)
    
    def reset_controls(self):
        """Reset all controls to default values"""
        self.brightness.set(0)
        self.contrast.set(1.0)
        self.blur_amount.set(1)
        self.threshold_value.set(127)
        self.show_edges.set(False)
        self.show_gray.set(False)
        self.show_threshold.set(False)
    
    def process_frame(self, frame):
        """Apply all selected processing to the frame"""
        
        # Apply brightness and contrast
        brightness = self.brightness.get()
        contrast = self.contrast.get()
        frame = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)
        
        # Apply blur (make sure it's odd number)
        blur = self.blur_amount.get()
        if blur > 1:
            if blur % 2 == 0:  # Make it odd
                blur += 1
            frame = cv2.GaussianBlur(frame, (blur, blur), 0)
        
        # Convert to grayscale if any special mode is selected
        if self.show_gray.get() or self.show_edges.get() or self.show_threshold.get():
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Show threshold (isolate bright regions)
            if self.show_threshold.get():
                threshold = self.threshold_value.get()
                _, frame = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
                # Convert back to BGR for display
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            
            # Show edges
            elif self.show_edges.get():
                edges = cv2.Canny(gray, 50, 150)
                frame = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            
            # Show grayscale
            else:
                frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        
        return frame
    
    def update_frame(self):
        """Capture and display video frame"""
        ret, frame = self.cap.read()
        
        if ret:
            # Process the frame
            processed_frame = self.process_frame(frame)
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            
            # Resize for display
            display_width = 640
            height, width = rgb_frame.shape[:2]
            if width > display_width:
                scale = display_width / width
                new_width = display_width
                new_height = int(height * scale)
                rgb_frame = cv2.resize(rgb_frame, (new_width, new_height))
            
            # Convert to PhotoImage
            img = Image.fromarray(rgb_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            
            # Update label
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)
        
        # Schedule next update (30 FPS)
        self.window.after(33, self.update_frame)
    
    def quit_app(self):
        """Clean up and close"""
        self.cap.release()
        self.window.destroy()

# Create and run the application
if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    app = BeautifulOpenCVPanel(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()
