/*
 * Furnace Motor Control - Arduino Sketch
 * Controls NEMA 17 stepper via TB6600 driver
 * Receives commands from Raspberry Pi via Serial
 * 
 * Wiring TB6600 to Arduino:
 * TB6600 PUL+ -> Arduino Pin 9 (step pulse)
 * TB6600 PUL- -> Arduino GND
 * TB6600 DIR+ -> Arduino Pin 8 (direction)
 * TB6600 DIR- -> Arduino GND
 * TB6600 ENA+ -> Arduino Pin 10 (enable, optional)
 * TB6600 ENA- -> Arduino GND
 * 
 * TB6600 Motor connections (A+, A-, B+, B-) go to motor
 * TB6600 Power: 12-24V supply
 * 
 * Serial Protocol:
 * Pi sends: "MOVE 500\n" - move 500 steps clockwise
 * Pi sends: "MOVE -500\n" - move 500 steps counterclockwise
 * Pi sends: "STOP\n" - emergency stop
 * Pi sends: "ZERO\n" - reset position counter to zero
 * Pi sends: "POS?\n" - query current position
 * 
 * Arduino responds: "OK\n" or "POS 1500\n" or "ERROR\n"
 */

// Pin definitions
const int STEP_PIN = 9;   // PUL+ on TB6600
const int DIR_PIN = 8;    // DIR+ on TB6600
const int ENABLE_PIN = 10; // ENA+ on TB6600 (optional, can tie ENA+ to 5V if not used)

// Motor configuration
const int STEPS_PER_REV = 200;  // NEMA 17 standard
const int MICROSTEPS = 16;      // Set on TB6600 DIP switches (see manual)
const int TOTAL_STEPS_PER_REV = STEPS_PER_REV * MICROSTEPS;  // 3200 for 1/16

// Speed settings
const int STEP_DELAY_US = 500;  // Microseconds between steps (adjust for speed)
                                 // 500us = 2000 steps/sec = decent speed
                                 // Lower = faster, but too low causes missed steps

// Position tracking
long currentPosition = 0;
bool motorEnabled = false;

// Serial buffer
String inputString = "";
bool stringComplete = false;

void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  
  // Initialize pins
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  pinMode(ENABLE_PIN, OUTPUT);
  
  // Disable motor initially
  digitalWrite(ENABLE_PIN, HIGH);  // HIGH = disabled on TB6600
  digitalWrite(STEP_PIN, LOW);
  digitalWrite(DIR_PIN, LOW);
  
  // Reserve space for serial input
  inputString.reserve(64);
  
  Serial.println("READY");
}

void loop() {
  // Check for serial commands
  if (stringComplete) {
    processCommand(inputString);
    inputString = "";
    stringComplete = false;
  }
}

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }
}

void processCommand(String cmd) {
  cmd.trim();
  
  if (cmd.startsWith("MOVE ")) {
    // Extract number of steps
    long steps = cmd.substring(5).toInt();
    moveMotor(steps);
    Serial.println("OK");
    
  } else if (cmd == "STOP") {
    // Emergency stop
    disableMotor();
    Serial.println("OK");
    
  } else if (cmd == "ZERO") {
    // Reset position counter
    currentPosition = 0;
    Serial.println("OK");
    
  } else if (cmd == "POS?") {
    // Query current position
    Serial.print("POS ");
    Serial.println(currentPosition);
    
  } else if (cmd == "ENABLE") {
    // Enable motor holding
    enableMotor();
    Serial.println("OK");
    
  } else if (cmd == "DISABLE") {
    // Disable motor (free spin)
    disableMotor();
    Serial.println("OK");
    
  } else {
    Serial.println("ERROR");
  }
}

void enableMotor() {
  digitalWrite(ENABLE_PIN, LOW);  // LOW = enabled on TB6600
  motorEnabled = true;
  delay(10);  // Small delay for driver to engage
}

void disableMotor() {
  digitalWrite(ENABLE_PIN, HIGH);  // HIGH = disabled on TB6600
  motorEnabled = false;
}

void moveMotor(long steps) {
  if (steps == 0) return;
  
  // Enable motor
  enableMotor();
  
  // Set direction
  if (steps > 0) {
    digitalWrite(DIR_PIN, HIGH);  // Clockwise
  } else {
    digitalWrite(DIR_PIN, LOW);   // Counterclockwise
    steps = -steps;  // Make positive for loop
  }
  
  // Small delay after direction change
  delayMicroseconds(10);
  
  // Step the motor
  for (long i = 0; i < steps; i++) {
    digitalWrite(STEP_PIN, HIGH);
    delayMicroseconds(STEP_DELAY_US);
    digitalWrite(STEP_PIN, LOW);
    delayMicroseconds(STEP_DELAY_US);
    
    // Update position
    if (digitalRead(DIR_PIN) == HIGH) {
      currentPosition++;
    } else {
      currentPosition--;
    }
    
    // Check for emergency stop during move
    if (Serial.available() > 0) {
      String emergency = Serial.readStringUntil('\n');
      if (emergency == "STOP") {
        disableMotor();
        Serial.println("STOPPED");
        return;
      }
    }
  }
  
  // Keep motor enabled to hold position
  // (you can disable after move if you want to save power/heat)
}

/*
 * TB6600 DIP Switch Settings for Microstepping:
 * 
 * S1  S2  S3  | Microsteps
 * ----------------------
 * ON  ON  ON  | 1    (200 steps/rev)
 * OFF ON  ON  | 2    (400 steps/rev)
 * ON  OFF ON  | 4    (800 steps/rev)
 * OFF OFF ON  | 8    (1600 steps/rev)
 * ON  ON  OFF | 16   (3200 steps/rev) <- RECOMMENDED
 * OFF ON  OFF | 32   (6400 steps/rev)
 * 
 * S4, S5, S6 control current limit - see TB6600 manual for your motor
 * 
 * Typical NEMA 17 pancake: Set to 1.5A or 2.0A
 */
