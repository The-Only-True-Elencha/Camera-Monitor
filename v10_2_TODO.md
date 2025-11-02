# OpenCV Vision Lab v10.2 - Development Plan

## What Went Wrong in v10.1
- Forgot the two-window GUI entirely
- Grid mode implementation broke view switching  
- Hot pink everywhere (user hates it)

## v10.2 Requirements (In Priority Order)

### 1. TWO-WINDOW DESIGN ⭐⭐⭐ (CRITICAL)
**Main Window (Feed):**
- Video display (maximized, resizable, can fullscreen)
- Measurement display below video
- Minimal UI (just title, status, quit button)
- Should be able to go fullscreen without controls blocking

**Control Window (Floating):**
- All control panels in a separate Toplevel window
- Can be moved anywhere on screen
- Can be minimized without hiding feed
- Closing control window also closes app

**Implementation:**
- Main app inherits from ctk.CTk (feed window)
- Create `self.control_window = Toplevel()` in __init__
- Split `setup_ui()` into `setup_feed_window()` and `setup_control_window()`
- Both windows reference same `self` (shared state)

### 2. SOFT PINK/LAVENDER PALETTE WITH BLACK TEXT ⭐⭐
**New Color Scheme:**
```python
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
```

**Key:** Soft pastels that are saturated enough to look good, with BLACK text for readability.

### 3. WORKING GRID MODE ⭐⭐
**Current Problem:** Grid mode causes freeze, then breaks single camera view too.

**Fix:**
```python
elif self.view_mode.get() == "grid" and len(self.active_cameras) > 0 and should_update:
    try:  # ADD ERROR HANDLING
        grid_frames = []
        
        for cam_idx in self.active_cameras[:4]:
            if cam_idx in self.cameras:
                frame = self.cameras[cam_idx].read()
                if frame is not None:
                    # Don't process - just resize for grid
                    # Processing in grid is too slow!
                    grid_frames.append(frame)
        
        if grid_frames:
            # Make all frames same size first
            h, w = grid_frames[0].shape[:2]
            target_size = (w//2, h//2)  # Quarter size for grid
            resized = [cv2.resize(f, target_size) for f in grid_frames]
            
            # Arrange in grid
            if len(resized) == 1:
                final = resized[0]
            elif len(resized) == 2:
                final = np.hstack(resized)
            elif len(resized) == 3:
                top = np.hstack(resized[:2])
                bot = resized[2]
                # Pad bottom to match width
                if bot.shape[1] < top.shape[1]:
                    pad = np.zeros((bot.shape[0], top.shape[1] - bot.shape[1], 3), dtype=np.uint8)
                    bot = np.hstack([bot, pad])
                final = np.vstack([top, bot])
            else:  # 4
                top = np.hstack(resized[:2])
                bot = np.hstack(resized[2:4])
                final = np.vstack([top, bot])
            
            # Display (convert to RGB, create CTkImage, etc.)
            # ... rest of display code
            
    except Exception as e:
        print(f"Grid mode error: {e}")
        # Don't crash - just skip this frame
        pass
```

### 4. AUTO-CAPTURE MODE ⭐
(Same as v10.1 - this part was good)

### 5. IMPROVED CAMERA DETECTION ⭐
(Same as v10.1 - this part was good)

### 6. BETTER ZOOM
(Same as v10.1 - LANCZOS4 interpolation)

## Code Structure for Two-Window Design

```python
class BeautifulOpenCVPanelV10_2(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Feed window setup
        self.title("Vision Laboratory v10.2 - Feed")
        self.geometry("1200x900")
        
        # ... all the variables ...
        
        # Setup both windows
        self.setup_feed_window()
        self.setup_control_window()
        
        self.detect_cameras()
        
        # Start update loop
        self.update_frame()
    
    def setup_feed_window(self):
        """Setup the main feed window (self)"""
        # Title
        # Video display
        # Measurement display
        # Minimal controls (quit button)
    
    def setup_control_window(self):
        """Setup the floating control panel"""
        self.control_window = Toplevel(self)
        self.control_window.title("Vision Laboratory v10.2 - Controls")
        self.control_window.geometry("450x800")
        
        # Make it float on top
        self.control_window.attributes('-topmost', True)
        
        # Closing controls also closes app
        self.control_window.protocol("WM_DELETE_WINDOW", self.quit_app)
        
        # Scrollable frame for all controls
        control_scroll = ctk.CTkScrollableFrame(self.control_window, ...)
        control_scroll.pack(fill="both", expand=True)
        
        # Add all the control modules
        self.setup_auto_capture_controls(control_scroll)
        self.setup_camera_controls(control_scroll)
        # ... etc ...
```

## Testing Checklist for v10.2

- [ ] Feed window opens
- [ ] Control window opens separately
- [ ] Can move control window around
- [ ] Can resize feed window
- [ ] Feed window can go fullscreen (F11)
- [ ] Single camera works
- [ ] Grid mode with 2 cameras works
- [ ] Grid mode with 3 cameras works  
- [ ] Grid mode with 4 cameras works
- [ ] Switch from grid to single - still works
- [ ] Switch from single to grid - still works
- [ ] Auto-capture saves to correct location
- [ ] Colors are soft pink/lavender with black text (NOT HOT PINK!)
- [ ] Everything is readable
- [ ] Detect cameras button works
- [ ] All other features from v10.0 still work

## Notes
- Two-window design is a MAJOR rewrite
- Need to test thoroughly before giving to user
- Grid mode needs error handling so it doesn't crash
- Make sure view mode switching is robust
- User really hates hot pink - use soft pastels!
