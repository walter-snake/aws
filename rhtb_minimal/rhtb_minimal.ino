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

/* Set up the Arduino -------------------------------------- */
void setup()
{
  // Open serial port
  Serial.begin(9600); 
  Serial.flush();
  
  // Setup sensors
  dht.begin();
  bmp.begin();

  // We need to wait a while after initializing the sensors
  delay(5000);
  }

/* Go into processing loop ---------------------------------- */
void loop()
{
  // T, H data
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  // BP data: get a new sensor event
  float b;
  sensors_event_t event;
  bmp.getEvent(&event);
  if (event.pressure)
    b = event.pressure;
  
  // Stream measured data: send one line
  Serial.print(t);
  Serial.print(",");
  Serial.print(h);
  Serial.print(",");
  Serial.println(b);

  // Wait milliseconds
  delay(5000);
}

