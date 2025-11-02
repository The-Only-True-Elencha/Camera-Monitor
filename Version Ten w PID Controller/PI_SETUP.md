# Raspberry Pi Setup Guide for OpenCV Vision Lab v9

## Prerequisites for Pi

### 1. Install Required System Packages
```bash
sudo apt update
sudo apt install -y python3-opencv python3-pil python3-tk scrot xclip
```

### 2. Install Python Packages
```bash
pip3 install customtkinter numpy --break-system-packages
pip3 install tkinterdnd2 --break-system-packages  # Optional, for drag-and-drop
```

### 3. Camera Permissions
Make sure your user is in the video group:
```bash
sudo usermod -a -G video $USER
```
Then log out and back in.

### 4. Test Camera
```bash
# List available cameras
v4l2-ctl --list-devices

# Test camera 0
ffplay /dev/video0
```

## Running the Application

```bash
python3 beautiful_opencv_v9.py
```

## Performance Tips for Pi

1. **Lower Resolution**: If slow, reduce display_width in code (line ~1972) from 900 to 640
2. **Use 1fps Mode**: Select "1 fps" capture mode to reduce processing load
3. **Disable Heavy Features**: 
   - Turn off histogram overlay when not needed
   - Use simpler morphological operations
   - Reduce closing iterations

## Troubleshooting

### Camera Not Detected
- Check `ls /dev/video*` - you should see video devices
- Try `sudo chmod 666 /dev/video0` temporarily to test permissions
- Check `dmesg | grep video` for kernel messages

### Screenshot to Clipboard Fails
- Install required tools: `sudo apt install scrot xclip`
- Make sure you're running in X11 (not headless)
- For headless Pi, screenshots won't work (no clipboard)

### Slow Performance
- Use "1 fps" or "1 per 5 sec" capture mode
- Reduce video display size
- Consider overclocking your Pi (carefully!)
- Use Pi 4 or Pi 5 for best performance

### CustomTkinter Looks Bad
- Try: `export GDK_SCALE=1` before running
- Install better fonts: `sudo apt install fonts-liberation`

## Camera Focus for C920x on Pi

The Logitech C920x focus can be controlled via v4l2:

```bash
# Disable autofocus
v4l2-ctl -d /dev/video0 -c focus_automatic_continuous=0

# Set focus (0-255, experiment to find best value)
v4l2-ctl -d /dev/video0 -c focus_absolute=50
```

You can add these commands to a startup script or run them before launching the app.

## Headless Operation

If you want to run on Pi without monitor:
1. Use VNC or X11 forwarding
2. Screenshot to clipboard won't work headless
3. Consider saving frames instead (Frame Grab still works)

## Performance Comparison

- **Pi 5**: Smooth at 1080p with 1fps capture
- **Pi 4**: Good at 720p with 1fps capture  
- **Pi 3**: Works at 480p with 1 per 5sec capture
- **Pi Zero**: Not recommended (too slow)

## Notes

- DirectShow (Windows) is replaced with V4L2 (Linux) automatically
- All OpenCV processing works identically on Pi
- HSV color filtering is CPU-intensive - use sparingly on older Pi models
