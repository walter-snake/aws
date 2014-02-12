/*
The MIT License (MIT)

Copyright (c) 2014 W. Boasson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
*/

boolean DEBUG = false; //
int version = 2; // the software version (2: streaming output changed) 

// Inlcude libraries
#include <EEPROM.h> // r/w to eeprom for permanent storage
#include <Wire.h> // serial lib for sensor communication
#include <DHT.h> // DHT sensor lib
#include <Adafruit_Sensor.h> // generic arduino sensor functions
#include <Adafruit_BMP085_U.h> // pressure sensor lib

// Barometer class instantiation
Adafruit_BMP085_Unified bmp = Adafruit_BMP085_Unified(10085);

// DHT class instantiation
#define DHTPIN 4        // pin we're connected to
#define DHTTYPE DHT22   // DHT 22
DHT dht(DHTPIN, DHTTYPE);

// The led
int led = 13;

/* Time ---------------------------------------------------------- */
// Measurement interval/auto stop, command mode
unsigned long defaultMeasurementInterval = 900000; // this is the default, when the measurementinterval was not set differently
unsigned long measurementInterval = 0; // this is the active measurement interval (either default, read from eeprom, or given in streaming setup)
unsigned long measurementTime = 0; // keeps track of the last measurement time
boolean enableMeasurement = true; // measurements allowed, will be set to true after commandtimeout or when issueing stream or cal mode
boolean defaultStreamingMode = true; // streaming mode: does not write to flash, to save the eeprom
boolean streamingMode = true; // streaming mode: does not write to flash, to save the eeprom
boolean calibrationMode = false; // cal mode: maybe not neccessary
unsigned long commandTimeOut = 60000; // set the timeout for command mode (1 minute)
boolean commandMode = true; // when a command is send, it will switch to command mode
boolean bmpPresent = true; // we have to continue measuring without this sensor

// Returns the measurement interval, also sends it to the serial port
unsigned long getMeasurementInterval()
{  
  unsigned long measurementIntervalStored = 0; // milliseconds
  if (EEPROM.read(1) != 0)
  {
  if (EEPROM.read(2) == 0)
    measurementIntervalStored = (unsigned long)(EEPROM.read(1)); // milliseconds
  else if (EEPROM.read(2) == 1)
    measurementIntervalStored = (unsigned long)(EEPROM.read(1)) * 1000; // seconds
  else if (EEPROM.read(2) == 2)
    measurementIntervalStored = (unsigned long)(EEPROM.read(1)) * 60000; // minutes
  else if (EEPROM.read(2) == 3)
    measurementIntervalStored = (unsigned long)(EEPROM.read(1)) * 3600000; // hours
  }
  delay(100);

  if (measurementIntervalStored == 0)
  {
    sendSerialString("Measurement interval set to: " + (String)defaultMeasurementInterval + " milliseconds");
    return defaultMeasurementInterval;
  }
  else
  {
    sendSerialString("Measurement interval set to: " + (String)measurementIntervalStored + " milliseconds");
    return measurementIntervalStored;
  }
}

boolean doMeasurement()
{
  unsigned long m = 0;
  m = millis();
  /* unsigned: also check if measurementInterval < m, otherwise subtraction becomes negative
     with nice and unexpected results (unsigned long) */
  /* measurements must be enabled (set with command or after time out)
     millis - interval >= measurementtime
     special case: commandtimeout elapsed, enabled true, commandmode still true: must be catched,
     otherwise it will either never or immediately start, or perform the first measurement only after the
     measurement interval has expired, plus: it has to stay in command mode unless told to start measuring
    by setting enableMeasurement = true */
  if ((m - measurementInterval >= measurementTime && measurementInterval < m && enableMeasurement && m > commandTimeOut)
        || (enableMeasurement && m > commandTimeOut && commandMode))
  {
    measurementTime = m; // set new (last) measurement time
    return true;
  }
  else return false;
}

// Just to give a hint that a measurement was be performed
void fastBlink(int n)
{
  for (int i = 1; i <= n; i++)
  {
    if (enableMeasurement)
    {
      digitalWrite(led, HIGH);
      delay(75);
      digitalWrite(led, LOW);
      delay(75);
    }
    else
    {
      digitalWrite(led, LOW);
      delay(75);
      digitalWrite(led, HIGH);
      delay(75);
    }
  }
}

// Read/sets the startup mode from flash
void getStartupMode()
{
    if (EEPROM.read(3) == 0)
    {
        streamingMode = defaultStreamingMode;
        sendSerialString("Start-up mode set to system default: streaming = " + (String)defaultStreamingMode);
    }
    else if (EEPROM.read(3) == 1)
    {
        streamingMode = true;
        sendSerialString("Start-up mode set to: streaming");
    }
    else if (EEPROM.read(3) == 2)
    {
        streamingMode = false;
        sendSerialString("Start-up mode set to: logger");
    }
}


/* Data encoding/decoding for storage, download --------------------------------------- */
// A few global vars, for range mapping (storage capacity!)
float TMIN = -24.0; // produces an effective range of -24 -> +40 in combination with the scale factor
float TSCALE = 4.0; // scales temps, in 0.25 steps
float HSCALE = 2.0; // produces an effective range of 0-100, in 0.5 steps
int BAROMIN = 900; // produces an effective range of 900-1154 millibar
// Encoding for storage
int encodeT(float T)
{
  return round((T - TMIN) * TSCALE);
}

int encodeH(float H)
{
  return round(H * HSCALE);
}

int encodeB(int B)
{
  return B - BAROMIN;
}

// Decoding for reading back
float decodeT(int T)
{
  return (T / TSCALE) + TMIN;
}

float decodeH(int H)
{
  return H / HSCALE;
}

int decodeB(int B)
{
  return B + BAROMIN;
}

// Send the measured data
void sendData()
{
  static char dtostrfbuffer[15];
  unsigned int n;
  unsigned int pos;
  n = EEPROM.read(0);
  
  // wait a little while, for client software to prepare if not multithreaded (which my basic script is not)
  delay(100);
  
  // Output the data (Number of Records, values)
  digitalWrite(led, LOW); // led off (download happens in command mode when the is on)
  Serial.println("#DATA");
  Serial.println("#NR:" + (String)n);
  Serial.println("#INTERVAL_MILLISECONDS:" + (String)measurementInterval);
  Serial.println("#METADATA:record number, temperature, relative humidity, barometric pressure");
  Serial.println("#COLUMNS:rn,temp,humid,baro");
  for (int i = 0; i < n; i++)
  {
    pos = i * 3;
    Serial.print((String)i);
    dtostrf(decodeT(EEPROM.read(pos + 13)), 5, 2, dtostrfbuffer);
    Serial.print("," + (String)dtostrfbuffer);
    dtostrf(decodeH(EEPROM.read(pos + 14)), 5, 1, dtostrfbuffer);
    Serial.print("," + (String)dtostrfbuffer);
    Serial.println("," + (String)decodeB(EEPROM.read(pos + 15)));
  }    
  Serial.println("#END");
  digitalWrite(led, HIGH); // led on
}

// Stream measured data: send one line
void sendDataLine(float t, float h, float b)
{
      Serial.print("^"); // start with a start of data marker (SOD)
      Serial.print(millis());
      Serial.print(",");
      Serial.print(t);
      Serial.print(",");
      Serial.print(h);
      Serial.print(",");
      Serial.print(b);
      Serial.println("$"); // last one including EOD marker ($) and LF
}

// Set the counter to zero measurements (byte 0: at maximum 254 measurements)
// Do not really clear data (overwrite): EEPROM write ability is limited.
void resetData()
{
  EEPROM.write(0, 0);
}

// Create dummy data (e.g. for testing)
void createDummyData(int n)
{
  int t;
  int h;
  int b;
  for (int i = 0; i < n; i++)
  {
    t = random(-24, 40);
    h = random(70, 100);
    b = random(900, 1154);
    Serial.println((String)millis() + "," + (String)t + "," + (String)h + "," +  (String)b);
    
    // Not in streaming mode: store data
    if (!streamingMode)
      storeData(t, h, b);
  }
}

/* Store the measured values, automatically
   adds to the 'file' */
void storeData(float t, float h, int b)
{
  /* Get the position (and reset, if turned over). */
  if (EEPROM.read(0) == 254)
    resetData();

  unsigned int pos = EEPROM.read(0) * 3;
  EEPROM.write(pos + 13, encodeT(t));
  EEPROM.write(pos + 14, encodeH(h));
  EEPROM.write(pos + 15, encodeB(b));
  
  /* Sort of transactional: only when all three values are written
     set the number of records (old NR + 1. */
  EEPROM.write(0, EEPROM.read(0) + 1);
}

// Serial command stuff ----------------------------------
#define INLENGTH 200
#define INTERMINATOR 10
char serInString[INLENGTH+1];
int serIn;
int serInIndx = 0;
int serLastIndx = 0;
String cmdParam;

void readSerialString() {
    int sb;   
    if(Serial.available()) { 
       while (Serial.available() && serInIndx < INLENGTH ){ 
          sb = Serial.read();   
          if (sb != INTERMINATOR) {          
            serInString[serInIndx] = sb;
            serInIndx++;
          }
          else 
          {
            break;
          }
       }
       
       setSerialStringParam();
    }
}

void setSerialStringParam() {
  int serOutIndx = 0;
  String s;
  
  for(serOutIndx=3; serOutIndx < serInIndx; serOutIndx++)
  {
    s+=serInString[serOutIndx];
  }
  if (DEBUG) Serial.println("Param: " + s);

  cmdParam = s;  
}

void clearSerialString() {
  serIn = 0;
  serInIndx  = 0;
  serLastIndx  = 0;
}

void sendSerialString(String s)
{
  Serial.println("# " + s);
}

void printSerialString() {
  int serOutIndx = 0;
  int intPosition = 0;
  
  if( serInIndx > 0) {       
    if (DEBUG) {
      Serial.print("Received: "); 
    }
    
    for(serOutIndx=0; serOutIndx < serInIndx; serOutIndx++) {
      if (DEBUG)  Serial.print( serInString[serOutIndx] );
      intPosition++;
    }
    if (DEBUG) Serial.println();
  }
}

// Commandline options
void processCommandLine()
{
  // Process commandline options
  if( serInIndx > 1) { 
    int command = (serInString[0] - '0') * 10 + (serInString[1] - '0');
    printSerialString();
    fastBlink(1);
    
    // Do not measuring after the first command issued
    // Enter commandMode (it will not exit automatically from commandMode
    enableMeasurement = false;
    commandMode = true;
    switch(command) {
      case 0: // Stop debug mode (need to send 00 for this command)
        if (DEBUG) sendSerialString("DEBUG OFF");
        DEBUG = false;
        break;
      case 1: // Start debug mode (need to send 01 for this command)
        DEBUG = true;
        sendSerialString("DEBUG ON");
        break;
      case 2: // Start clock calibration mode (need to send 02 for this command)
        DEBUG = true;
        if (DEBUG) sendSerialString("Calibration mode, interval: " + cmdParam + " milliseconds");
        measurementInterval = cmdParam.toInt();
        sendSerialString("Calibration mode");
        enableMeasurement = true;
        calibrationMode = true;
        streamingMode = true;
        commandTimeOut = millis() + 1000; // make sure it starts soon sending data
        break;
      case 3: // Start debug mode (need to send 03 for this command)
        sendSerialString("Arduino based weather data collector and logger.");
        sendSerialString("Copyright (c) 2014 W. Boasson");
        sendSerialString("Serial connection established");
        sendSerialString("Software version: " + (String)version);
        break;
      case 10: // Clear the data
        if (DEBUG) sendSerialString("Clear the data");
        resetData();
        break;
      case 11: // Send the data
        if (DEBUG) sendSerialString("Send the data");
        sendData();  
        break;
      case 12: // Insert dummy data
        if (DEBUG) sendSerialString("Insert dummy data: " + cmdParam + " records");
        createDummyData(cmdParam.toInt());
        break;
      case 20: // Go into streaming measurement mode
        if (DEBUG) sendSerialString("Streaming measurement data, interval: " + cmdParam + " milliseconds");
        if (cmdParam != "")
          measurementInterval = cmdParam.toInt();
        // In this case, turn on the measurement mode
        enableMeasurement = true;
        // Prevent writing to eeprom
        streamingMode = true;
        commandTimeOut = millis() + 1000; // make sure it starts soon sending data
        break;
      case 21: // Set measurement interval
        if (DEBUG) sendSerialString("Set measurement interval to: " + cmdParam);
        EEPROM.write(1,cmdParam.toInt());
        measurementInterval = getMeasurementInterval();
        break;
      case 22: // Set measurement interval units
        if (DEBUG) sendSerialString("Set measurement units to: " + cmdParam);
        EEPROM.write(2,cmdParam.toInt());
        measurementInterval = getMeasurementInterval();
        break;
      case 23: // Set startup mode
        sendSerialString("Setting start-up mode to: " + cmdParam);
        EEPROM.write(3,cmdParam.toInt());
        getStartupMode();
        break;
      default:  // Don't know what to do
        sendSerialString("Unknown command code: " + (String)command);
        break;
    }
  }
}

/* Set up the Arduino -------------------------------------- */
void setup()
{
  pinMode(led, OUTPUT);
  
  Serial.begin(9600); 
  Serial.flush();
  
  fastBlink(20); // Inform user that setup routine has started and Serial port is active
  delay(5000); // gives the time to open the monitor and catch any output (just for debugging)
  
  // Setup sensors
  dht.begin();
  if(!bmp.begin()) // start sensor Barometric P
  {
    /* There was a problem detecting the BMP085 ... check your connections */
    sendSerialString("WARNING no BMP085 detected");
    bmpPresent = false;
  }
  else
  {
    sendSerialString("INFO BMP085 detected");
  }

  // We need to wait a while after initializing the sensors
  delay(2000);
  digitalWrite(led, HIGH);
  
  // Get the measurement time interval, read from memory or use default
  measurementInterval = getMeasurementInterval();
  
  // startup mode
  getStartupMode();
  
  // Send the ready signal
  sendSerialString("READY");
}

/* Go into processing loop ---------------------------------- */
void loop()
{
  delay(20);

  // Process commandline as long as we're in the commandTimeOut
  if (millis() < commandTimeOut || commandMode)
  {
    // Get ze commandline options
    readSerialString();
    processCommandLine();
  }
  else if (millis() > commandTimeOut && !commandMode)
    enableMeasurement = true;
  

  // Only perform a measurement when allowed
  if (doMeasurement())
  {
    // Turn off the light
    digitalWrite(led, LOW);
        
    // T, H data
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    
    // BP data: get a new sensor event, only if sensor present (we might need the software with only the dht present)
    float b;
    if (bmpPresent)
    {
      sensors_event_t event;
      bmp.getEvent(&event);
      if (event.pressure)
        b = event.pressure;
    }
    else
      b = 900;
    
    // Not in streamingmode: store the data
    if (!streamingMode)
    {
      storeData(t, h, b);
    }
    else // Stream results
    {
      if (calibrationMode)
      {
        Serial.print((String)measurementInterval);
        Serial.print(",");
        Serial.println(millis());
      }
      else
        sendDataLine(t, h, b);
    }
    
    // Blink for the measurement
    fastBlink(2);

    // at this point, always set commandMode to false
    commandMode = false;
  }
  
  // Clear the commandline
  clearSerialString();
}

