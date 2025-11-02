"""
PID Motor Controller for Furnace
Communicates with Arduino via Serial to control molten zone size

Install: pip3 install simple-pid pyserial --break-system-packages
"""

import serial
import time
from simple_pid import PID


class FurnaceMotorController:
    """Controls furnace temperature via motor-adjusted knob using PID"""
    
    def __init__(self, serial_port='/dev/ttyUSB0', baudrate=115200, 
                 steps_per_degree=50, timeout=2):
        """
        Initialize motor controller
        
        Args:
            serial_port: Arduino serial port (COM3 on Windows, /dev/ttyUSB0 on Pi)
            baudrate: Serial communication speed
            steps_per_degree: How many motor steps = 1 degree temp change
                             (depends on your pulley ratio and furnace knob)
            timeout: Serial timeout in seconds
        """
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.steps_per_degree = steps_per_degree
        self.timeout = timeout
        self.arduino = None
        self.connected = False
        
    def connect(self):
        """Connect to Arduino"""
        try:
            self.arduino = serial.Serial(
                self.serial_port, 
                self.baudrate, 
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for Arduino to reset
            
            # Read READY message
            response = self.arduino.readline().decode('utf-8').strip()
            if response == "READY":
                self.connected = True
                print(f"✅ Connected to Arduino on {self.serial_port}")
                return True
            else:
                print(f"❌ Unexpected response: {response}")
                return False
                
        except serial.SerialException as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Arduino"""
        if self.arduino and self.arduino.is_open:
            self.disable_motor()
            self.arduino.close()
            self.connected = False
            print("🔌 Disconnected from Arduino")
    
    def send_command(self, command):
        """Send command to Arduino and wait for response"""
        if not self.connected:
            print("❌ Not connected to Arduino")
            return None
            
        try:
            # Send command
            self.arduino.write(f"{command}\n".encode('utf-8'))
            
            # Read response
            response = self.arduino.readline().decode('utf-8').strip()
            return response
            
        except Exception as e:
            print(f"❌ Communication error: {e}")
            return None
    
    def move_steps(self, steps):
        """
        Move motor by specified steps
        
        Args:
            steps: Number of steps (positive = clockwise, negative = counterclockwise)
        
        Returns:
            bool: True if successful
        """
        response = self.send_command(f"MOVE {int(steps)}")
        return response == "OK"
    
    def adjust_temperature(self, degrees):
        """
        Adjust temperature by specified degrees
        
        Args:
            degrees: Temperature change in degrees (positive = increase, negative = decrease)
        
        Returns:
            bool: True if successful
        """
        steps = int(degrees * self.steps_per_degree)
        return self.move_steps(steps)
    
    def emergency_stop(self):
        """Emergency stop motor"""
        response = self.send_command("STOP")
        return response in ["OK", "STOPPED"]
    
    def zero_position(self):
        """Reset position counter to zero"""
        response = self.send_command("ZERO")
        return response == "OK"
    
    def get_position(self):
        """Get current motor position"""
        response = self.send_command("POS?")
        if response and response.startswith("POS "):
            try:
                return int(response.split()[1])
            except:
                return None
        return None
    
    def enable_motor(self):
        """Enable motor (hold position)"""
        response = self.send_command("ENABLE")
        return response == "OK"
    
    def disable_motor(self):
        """Disable motor (free to turn)"""
        response = self.send_command("DISABLE")
        return response == "OK"


class MoltenZonePIDController:
    """PID controller for maintaining molten zone size"""
    
    def __init__(self, motor_controller, target_size_mm=5.0, 
                 Kp=1.0, Ki=0.1, Kd=0.05):
        """
        Initialize PID controller
        
        Args:
            motor_controller: FurnaceMotorController instance
            target_size_mm: Desired molten zone size in millimeters
            Kp, Ki, Kd: PID tuning parameters (start conservative, tune later)
        """
        self.motor = motor_controller
        self.target_size = target_size_mm
        
        # Create PID controller
        # output_limits prevents crazy corrections
        self.pid = PID(
            Kp, Ki, Kd,
            setpoint=target_size_mm,
            output_limits=(-100, 100)  # Max ±100 steps per correction
        )
        
        self.enabled = False
        self.last_measurement = None
        self.correction_history = []
        
    def set_target(self, target_mm):
        """Change target molten zone size"""
        self.target_size = target_mm
        self.pid.setpoint = target_mm
        print(f"🎯 Target set to {target_mm} mm")
    
    def enable(self):
        """Enable PID control"""
        self.enabled = True
        self.pid.reset()  # Reset integral term
        self.motor.enable_motor()
        print("✅ PID control enabled")
    
    def disable(self):
        """Disable PID control"""
        self.enabled = False
        self.motor.disable_motor()
        print("⏸️ PID control disabled")
    
    def update(self, measured_size_mm):
        """
        Update PID controller with new measurement
        
        Args:
            measured_size_mm: Current molten zone size from camera
        
        Returns:
            dict: Control info (steps_moved, error, etc.)
        """
        if not self.enabled:
            return {'enabled': False}
        
        self.last_measurement = measured_size_mm
        
        # Calculate error
        error = self.target_size - measured_size_mm
        
        # Get PID output (desired steps)
        correction_steps = self.pid(measured_size_mm)
        
        # Apply correction
        success = self.motor.move_steps(int(correction_steps))
        
        # Track history
        control_info = {
            'enabled': True,
            'target': self.target_size,
            'measured': measured_size_mm,
            'error': error,
            'correction_steps': int(correction_steps),
            'success': success,
            'timestamp': time.time()
        }
        
        self.correction_history.append(control_info)
        
        # Keep only last 100 corrections
        if len(self.correction_history) > 100:
            self.correction_history.pop(0)
        
        return control_info
    
    def get_status(self):
        """Get current PID status"""
        return {
            'enabled': self.enabled,
            'target': self.target_size,
            'last_measurement': self.last_measurement,
            'Kp': self.pid.Kp,
            'Ki': self.pid.Ki,
            'Kd': self.pid.Kd,
            'motor_position': self.motor.get_position()
        }
    
    def tune(self, Kp=None, Ki=None, Kd=None):
        """Adjust PID tuning parameters on the fly"""
        if Kp is not None:
            self.pid.Kp = Kp
        if Ki is not None:
            self.pid.Ki = Ki
        if Kd is not None:
            self.pid.Kd = Kd
        print(f"🔧 PID tuned: Kp={self.pid.Kp}, Ki={self.pid.Ki}, Kd={self.pid.Kd}")


# Example usage
if __name__ == "__main__":
    # Initialize motor controller
    motor = FurnaceMotorController(
        serial_port='/dev/ttyUSB0',  # Change to 'COM3' on Windows
        steps_per_degree=50  # Adjust based on your pulley ratio
    )
    
    # Connect to Arduino
    if not motor.connect():
        print("Failed to connect to Arduino")
        exit(1)
    
    # Create PID controller
    pid_controller = MoltenZonePIDController(
        motor_controller=motor,
        target_size_mm=5.0,  # Target 5mm molten zone
        Kp=1.0,
        Ki=0.1,
        Kd=0.05
    )
    
    # Enable PID
    pid_controller.enable()
    
    # Simulation of measurement loop
    print("\n🔥 Starting furnace control simulation...")
    print("(In real app, measurements come from OpenCV)\n")
    
    try:
        # Simulate measurements
        simulated_measurements = [6.2, 5.8, 5.5, 5.3, 5.1, 5.0, 4.9, 5.0, 5.1]
        
        for measured_size in simulated_measurements:
            print(f"📏 Measured: {measured_size} mm")
            
            # Update PID
            result = pid_controller.update(measured_size)
            
            if result['success']:
                print(f"   Error: {result['error']:.2f} mm")
                print(f"   Correction: {result['correction_steps']} steps")
                print(f"   {'🔥 Heating up' if result['correction_steps'] > 0 else '❄️ Cooling down'}")
            else:
                print("   ❌ Failed to move motor")
            
            print()
            time.sleep(2)  # Wait 2 seconds between adjustments
    
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping...")
    
    finally:
        # Cleanup
        pid_controller.disable()
        motor.disconnect()
        print("✅ Shutdown complete")
