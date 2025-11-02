# Complete Furnace PID Control Setup Guide

## Overview

Your system consists of:
1. **Raspberry Pi** - Runs camera + OpenCV + PID calculations
2. **Arduino** - Controls stepper motor in real-time
3. **TB6600 Stepper Driver** - Powers the NEMA 17 motor
4. **NEMA 17 Stepper Motor** - Physically turns the furnace knob
5. **Camera (C920x)** - Monitors molten zone size

## Installation Steps

### 1. Raspberry Pi Setup

```bash
# Install system packages
sudo apt update
sudo apt install -y python3-opencv python3-pil python3-tk scrot xclip

# Install Python packages
pip3 install customtkinter numpy simple-pid pyserial --break-system-packages
pip3 install tkinterdnd2 --break-system-packages  # Optional
```

### 2. Arduino Setup

1. Install Arduino IDE on your PC
2. Open `furnace_motor_control.ino`
3. Connect Arduino to PC via USB
4. Select board: Tools → Board → Arduino Uno (or your board)
5. Select port: Tools → Port → (your Arduino port)
6. Click Upload (→ button)

### 3. Hardware Wiring

#### TB6600 to Arduino
```
TB6600 Pin    →  Arduino Pin
---------------------------
PUL+          →  Pin 9
PUL-          →  GND
DIR+          →  Pin 8  
DIR-          →  GND
ENA+          →  Pin 10
ENA-          →  GND
```

#### TB6600 to Motor
```
TB6600 Motor Pins  →  NEMA 17 Wires
-----------------------------------
A+                 →  Red (or Black)
A-                 →  Green (or Green)
B+                 →  Blue (or Red)
B-                 →  Yellow (or Blue)

Note: Wire colors vary by manufacturer. 
Check your motor's datasheet or test with multimeter.
Coil A = one pair, Coil B = other pair
```

#### TB6600 Power
```
TB6600 Power Pins  →  24V Supply
---------------------------------
VCC (+)            →  24V+ (red)
GND (-)            →  24V- (black)
```

#### TB6600 DIP Switch Settings (Microstepping)

For 1/16 microstepping (3200 steps/revolution):
```
S1: ON
S2: ON  
S3: OFF

Current limit (S4-S6): Set according to your motor
For typical NEMA 17 (1.5-2A): 
S4: OFF
S5: ON
S6: OFF
```

### 4. Motor to Furnace Coupling

**Option A: Belt/Pulley System (Recommended)**
- Mount motor near furnace
- Use timing belt and pulleys
- Allows gear ratio adjustment
- Less stress on motor shaft

**Option B: Direct Coupling**
- Use shaft coupler (5mm to 6mm or appropriate sizes)
- Mount motor rigidly to furnace
- Requires precise alignment

**Calculate Steps Per Degree:**
```
If pulley ratio is 3:1 (motor turns 3x for 1x knob rotation):
- Motor: 3200 steps/rev (with 1/16 microstepping)
- Knob: say 10 degrees = 1°C temp change
- Steps per degree = (3200 * 3) / (360 / 10) = 267 steps per °C

Adjust these values in the software!
```

## Software Configuration

### In beautiful_opencv_v10_PID.py

1. **Set Arduino Port:**
   - Windows: `COM3` (check Device Manager)
   - Pi: `/dev/ttyUSB0` or `/dev/ttyACM0`

2. **Set Steps Per Degree:**
   - Based on your pulley ratio calculation above
   - Start conservative (e.g., 50) and tune

3. **PID Tuning (Start Here):**
   - Kp = 1.0 (proportional gain)
   - Ki = 0.1 (integral gain)
   - Kd = 0.05 (derivative gain)

## Usage Workflow

### Step 1: Test Arduino Connection (Without Pi)

1. Connect Arduino to PC
2. Open Arduino IDE Serial Monitor (115200 baud)
3. Type: `MOVE 200` and press Enter
4. Motor should turn ~1/16 revolution (200 steps)
5. Type: `MOVE -200` to reverse
6. Type: `POS?` to check position
7. Type: `STOP` for emergency stop

### Step 2: Connect Hardware to Pi

1. Disconnect Arduino from PC
2. Connect Arduino to Raspberry Pi via USB
3. Power on TB6600 (24V supply)
4. Check Arduino port: `ls /dev/ttyUSB*` or `ls /dev/ttyACM*`

### Step 3: Run OpenCV Application

```bash
cd /path/to/scripts
python3 beautiful_opencv_v10_PID.py
```

### Step 4: Calibrate Camera

1. Load image or start camera
2. Set pixels per mm (use known reference object)
3. Enable HSV color filter
4. Adjust sliders to detect molten zone
5. Enable measurement
6. Verify zone size readings

### Step 5: Connect PID Controller

1. In "PID Furnace Control" panel:
2. Set Arduino Port (e.g., `/dev/ttyUSB0`)
3. Click "Connect to Arduino"
4. Wait for "✅ Arduino connected"
5. If failed, check:
   - Port name correct?
   - Arduino has sketch uploaded?
   - USB cable working?

### Step 6: Configure PID

1. **Target Zone Size:** Set desired molten zone (e.g., 5.0 mm)
2. **Control Zone:** Select which zone to control (Zone 1, 2, 3, or 4)
3. **Steps/°C:** Enter your calculated value
4. **PID Values:** Start with defaults (Kp=1.0, Ki=0.1, Kd=0.05)

### Step 7: Enable PID Control

1. Check "✅ Enable PID Control"
2. Watch measurements
3. Motor should adjust automatically to maintain target

### Step 8: Tune PID (If Needed)

**Symptoms:**
- **Oscillating:** Zone size bounces up/down → Lower Kp, increase Kd
- **Slow response:** Takes forever to reach target → Increase Kp
- **Steady error:** Never quite reaches target → Increase Ki
- **Overshoots:** Goes past target then corrects → Lower Kp, increase Kd

**Tuning Process:**
1. Start with Ki=0, Kd=0
2. Increase Kp until system responds quickly but oscillates slightly
3. Increase Kd to dampen oscillations
4. Add small Ki to eliminate steady-state error
5. Click "Apply Tuning" after changes

## Troubleshooting

### Arduino Won't Connect
```bash
# Check if Arduino is detected
lsusb
ls -l /dev/ttyUSB* /dev/ttyACM*

# Add user to dialout group (for serial port access)
sudo usermod -a -G dialout $USER
# Log out and back in

# Test with screen (Ctrl-A then K to exit)
screen /dev/ttyUSB0 115200
```

### Motor Not Moving
1. Check TB6600 power LED (green)
2. Check DIP switches set correctly
3. Test with Serial Monitor (send `MOVE 100`)
4. Check wiring: PUL+/DIR+ to Arduino pins
5. Verify motor wires connected (A+/A-/B+/B-)

### Motor Moves Wrong Direction
- In Arduino sketch, swap `HIGH`/`LOW` in DIR_PIN logic, OR
- Swap A+ with A- wires on TB6600

### PID Goes Crazy
1. Emergency stop: Uncheck "Enable PID Control"
2. Or in Arduino Serial Monitor: type `STOP`
3. Lower Kp gain
4. Check "Steps/°C" is correct
5. Verify target zone size is realistic

### Molten Zone Detection Issues
1. Adjust HSV color filter sliders
2. Increase closing iterations (bridge coil gaps)
3. Adjust contour filters (area, aspect ratio)
4. Use ROI to limit detection area
5. Check lighting/camera exposure

## Safety Notes

⚠️ **IMPORTANT SAFETY:**
- Monitor first few PID cycles manually
- Keep emergency stop ready (uncheck PID enable)
- Don't leave unattended until thoroughly tested
- Furnace can overheat if PID malfunctions
- Have manual override ready (turn knob by hand)

## Advanced: Multiple Zones

If you want to control multiple zones with separate motors:
1. Use multiple Arduinos (one per zone)
2. Connect each to different USB ports
3. Create separate PID controller instances
4. Assign each to different zone number

## Performance Tips

**For smooth operation:**
- Use "1 fps" or "3 fps" capture mode (reduces CPU load)
- Close other programs on Pi
- Consider overclocking Pi 4/5 for better performance
- Use good quality USB cables for Arduino connection
- Shield motor wires to reduce EMI

## Files You Need

```
📁 Your Project Folder
├── beautiful_opencv_v10_PID.py          # Main application
├── furnace_pid_controller.py           # PID controller library
├── furnace_motor_control.ino           # Arduino sketch
└── PI_SETUP.md                          # Pi installation guide
```

## Quick Start Checklist

- [ ] Arduino sketch uploaded
- [ ] Hardware wired correctly
- [ ] TB6600 DIP switches set
- [ ] Motor coupled to furnace knob
- [ ] Pi packages installed
- [ ] Camera working
- [ ] HSV filter tuned for molten zone
- [ ] Calibration set (pixels per mm)
- [ ] Arduino connected in software
- [ ] PID target and zone selected
- [ ] Steps/°C calculated and entered
- [ ] PID enabled and monitoring
- [ ] Tuning adjusted if needed

## Support

If something's not working:
1. Test each component separately (camera → Arduino → motor → PID)
2. Check wiring with multimeter
3. Verify Arduino Serial Monitor shows READY on boot
4. Confirm OpenCV can detect molten zones
5. Test motor moves with manual commands first

Good luck with your germanium refining! 🔥✨
