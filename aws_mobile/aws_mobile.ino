// Test code for Adafruit GPS modules using MTK3329/MTK3339 driver
//
// This code shows how to listen to the GPS module in an interrupt
// which allows the program to have more 'freedom' - just parse
// when a new NMEA sentence is available! Then access data when
// desired.
//
// Tested and works great with the Adafruit Ultimate GPS module
// using MTK33x9 chipset
//    ------> http://www.adafruit.com/products/746
// Pick one up today at the Adafruit electronics shop 
// and help support open source hardware & software! -ada

//This code is intended for use with Arduino Leonardo and other ATmega32U4-based Arduinos

#include <Wire.h> // serial lib for sensor communication
#include <Adafruit_GPS.h>
#include <SoftwareSerial.h>
#include <DHT.h> // DHT sensor lib
#include <Adafruit_Sensor.h> // generic arduino sensor functions
#include <Adafruit_BMP085_U.h> // pressure sensor lib

// Connect the GPS Power pin to 5V
// Connect the GPS Ground pin to ground
// If using software serial (sketch example default):
//   Connect the GPS TX (transmit) pin to Digital 8
//   Connect the GPS RX (receive) pin to Digital 7
// If using hardware serial:
//   Connect the GPS TX (transmit) pin to Arduino RX1 (Digital 0)
//   Connect the GPS RX (receive) pin to matching TX1 (Digital 1)

// If using software serial, keep these lines enabled
// (you can change the pin numbers to match your wiring):
//SoftwareSerial mySerial(8, 7);
//Adafruit_GPS GPS(&mySerial);
 
// If using hardware serial, comment
// out the above two lines and enable these two lines instead:
Adafruit_GPS GPS(&Serial1);
HardwareSerial mySerial = Serial1;

// Set GPSECHO to 'false' to turn off echoing the GPS data to the Serial console
// Set to 'true' if you want to debug and listen to the raw GPS sentences
#define GPSECHO  false

// Set the measurement interval
unsigned long measurementInterval = 5000;
boolean bmpPresent = true;

// Barometer class instantiation
Adafruit_BMP085_Unified bmp = Adafruit_BMP085_Unified(10085);

// DHT class instantiation
#define DHTPIN 4        // pin we're connected to
#define DHTTYPE DHT22   // DHT 22
DHT dht(DHTPIN, DHTTYPE);

// The led
int led = 13;

void sendSerialString(String s)
{
  Serial.println("# " + s);
}

void setup()  
{
  // connect at 115200 so we can read the GPS fast enough and echo without dropping chars
  // also spit it out
  Serial.begin(115200);
  Serial.flush();
  
  // Before spitting out data: wait a little while.
  delay(5000);
  sendSerialString("Arduino Weather Station Mobile");

  // 9600 NMEA is the default baud rate for Adafruit MTK GPS's- some use 4800
  GPS.begin(9600);
  
  // uncomment this line to turn on RMC (recommended minimum) and GGA (fix data) including altitude
  GPS.sendCommand(PMTK_SET_NMEA_OUTPUT_RMCGGA);
  // uncomment this line to turn on only the "minimum recommended" data
  //GPS.sendCommand(PMTK_SET_NMEA_OUTPUT_RMCONLY);
  // For parsing data, we don't suggest using anything but either RMC only or RMC+GGA since
  // the parser doesn't care about other sentences at this time
  
  // Set the update rate
  GPS.sendCommand(PMTK_SET_NMEA_UPDATE_1HZ);   // 1 Hz update rate
  // For the parsing code to work nicely and have time to sort thru the data, and
  // print it out we don't suggest using anything higher than 1 Hz

  // Request updates on antenna status, comment out to keep quiet
  GPS.sendCommand(PGCMD_ANTENNA);

  // Setup sensors
  dht.begin();
  if(!bmp.begin()) // start sensor Barometric P
  {
    /* There was a problem detecting the BMP085 ... check your connections */
    sendSerialString("WARNING no BMP085/180 detected");
    bmpPresent = false;
  }
  else
  {
    sendSerialString("INFO BMP085/180 detected");
  }

  // We need to wait a while after initializing the sensors
  delay(2000);
  
  // Light off, only turn on when GPS fixed,.
  digitalWrite(led, LOW);

  // Ask for firmware version
  //mySerial.println(PMTK_Q_RELEASE);
  sendSerialString(PMTK_Q_RELEASE);
}

uint32_t timer = millis();
void loop()                     // run over and over again
{
  char c = GPS.read();
  // if you want to debug, this is a good time to do it!
  if ((c) && (GPSECHO))
    Serial.write(c); 
  
  // if a sentence is received, we can check the checksum, parse it...
  if (GPS.newNMEAreceived()) {
    // a tricky thing here is if we print the NMEA sentence, or data
    // we end up not listening and catching other sentences! 
    // so be very wary if using OUTPUT_ALLDATA and trytng to print out data
    //Serial.println(GPS.lastNMEA());   // this also sets the newNMEAreceived() flag to false
  
    if (!GPS.parse(GPS.lastNMEA()))   // this also sets the newNMEAreceived() flag to false
      return;  // we can fail to parse a sentence in which case we should just wait for another
  }

  // if millis() or timer wraps around, we'll just reset it
  if (timer > millis())  timer = millis();

  // every measurementInterval millis, spit out data
  if (millis() - timer > measurementInterval) { 
    timer = millis(); // reset the timer

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
      b = 0;

    // Output
    // GPS fixed:
    // sat-datetime,t,h,b,lat,lon,alt,speed,angle,sat
    // else
    // sat-datetime,t,h,b,,,,,,sat
    Serial.print(GPS.day, DEC); Serial.print('/');
    Serial.print(GPS.month, DEC); Serial.print("/");
    Serial.print(GPS.year, DEC); Serial.print(" ");
    Serial.print(GPS.hour, DEC); Serial.print(':');
    Serial.print(GPS.minute, DEC); Serial.print(':');
    Serial.print(GPS.seconds, DEC); Serial.print(',');
    Serial.print(t, 1); Serial.print(',');
    Serial.print(h, 1); Serial.print(',');
    Serial.print(b, 1); Serial.print(',');
    if (GPS.fix) {
      digitalWrite(led, HIGH);
      Serial.print(GPS.latitude, 4); Serial.print(GPS.lat); Serial.print(',');
      Serial.print(GPS.longitude, 4); Serial.print(GPS.lon); Serial.print(',');
      Serial.print(GPS.altitude); Serial.print(',');
      Serial.print(GPS.speed * 1.852); Serial.print(',');
      Serial.print(GPS.angle); Serial.print(',');
      Serial.println((int)GPS.satellites);
    }
    else
    {
      digitalWrite(led, LOW);
      Serial.print(",,,,,");
      Serial.println((int)GPS.satellites);
    }
  }
}

