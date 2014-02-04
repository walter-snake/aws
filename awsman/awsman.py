#! /usr/bin/python
# -*- coding: ascii -*-

# we do need a few libraries (pretty standard ones, except for serial, which might have to be installed)
import signal, os, sys, serial,time, uuid, glob, re
import platform
from libawsman import *
from datetime import datetime
from datetime import timedelta

try:
  import config
except:
  "Print starting configuration"

# Purpose of this script:
# 1) Manage the Arduino based weather station running my 'weather_logger' software. 
# 2) Store data on a http server running my microsds service (php/PostgreSQL/PostGIS).
# 3) Manage your stations in the microsds service

####################################################################
# License #########################################################
####################################################################

# The MIT License (MIT)
# 
# Copyright (c) 2014 W. Boasson
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

print ""
print "*********************************************************"
print "* Client for the Arduino weather station and webservice *"
print "* (c) Wouter Boasson 2014                               *"
print "* License: MIT                                          *"
print "*********************************************************"
print ""

####################################################################
# A few Function definitions, most are in libawsman.py #############
####################################################################

# Online, test microsds service ####################################
def testGenerateConfig():
  if not os.path.exists("config.py"):
    MSDSERVER = raw_input("Micro SDS Server: ")
    MSDSERVERPATH = raw_input("Service path:     ")
    SERIALPORT = raw_input("Serial port:      ")
    f = open('config.py','w')
    f.write('MSDSERVER="'+MSDSERVER+"\"\n")
    f.write('MSDSERVERPATH="/'+MSDSERVERPATH.strip("/")+"\"\n")
    f.write('SERIALPORT="'+SERIALPORT+"\"\n")
    f.close()
    print "Configuration written to config.py."
    sys.exit()

# The various online modi, note that streaming and data input are missing here:
# they automatically cache stuff and can be used offline, test-microsds also
# missing: test would otherwise be executed twice
onlinemodi = ['station-insert', 'station-delete'
    , 'station-disable', 'station-enable'
    , 'data-upload', 'cache-purge']

def testMicroSds(mode):
  if (mode in onlinemodi):
    tr = testMicroSdsConfig()
    if tr <> 0:
      sys.exit()

# COM port #######################################################
def getSerialPort(portname):
  ttyport = ""
  if portname == "port:auto" or portname == "port:config":
    if platform.system().startswith('Win') or portname == "port:config":
      ttyport = SERIALPORT
    elif platform.system() == "Darwin":
      ttys = glob.glob("/dev/tty.usbmodem*")
      ttyport = ttys[0]
    elif platform.system() == "Linux":
      ttys = glob.glob("/dev/ttyUSB*")
      ttyport = ttys[0]
    else:
      ttyport = portname
  else:
    ttyport = portname
  print "Using serial port: " + ttyport
  return ttyport

# Help ###########################################################
def printHelp(section):
  f = open('usage.txt','r')
  insection = False
  if section == "":
    for line in f.readlines():
      print line.rstrip()
  else:
    for line in f.readlines():
      if insection and (not (line.startswith("  ") or line.strip() == "")):
         insection = False
      if line.startswith(section):
        insection = True
      if insection:
        print line.rstrip()
  print ""

####################################################################
# Start of script ##################################################
####################################################################

# With no arguments:  
if len(sys.argv) == 1:
  # First, generate config.py
  testGenerateConfig()

  print ""
  print "Usage:         python awsman.py [mode] {parameters}"
  print "Extended help: python awsman.py help {command}"
  print """  Available commands: 
  - help
  - test-microsds
  - test-logger
  - station-insert
  - station-show
  - station-select
  - station-disable
  - station-enable
  - station-config-delete
  - station-delete
  - set-logger
  - streaming
  - streaming-test
  - data-upload
  - data-getlog
  - data-input
  - data-show
  - cache-show
  - cache-purge
  - cache-clear
"""
  print ""
  testMicroSds("test-microsds")
  sys.exit()

# Init stuff ################################################################
# Get the operation mode from the commandline
mode = sys.argv[1]
testMicroSds(mode)

if (mode == "help"):
  if len(sys.argv) == 3:
    printHelp(sys.argv[2]) # a specific section
  else:
    printHelp("")
  sys.exit()

# Test webservice connection
if (mode == "test-microsds"):
  testMicroSdsConfig()
  sys.exit()

# Create the cache db, if neccessary
prepareCacheDb()
prepareConfigDb()

# Station configs
if (mode == "station-show"):
  showStatConfig()
elif (mode == "station-select"):
  if len(sys.argv) < 3:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('station-select')
    sys.exit()
  selectStatConfig(sys.argv[2])
elif (mode == "station-delete"):
  if len(sys.argv) < 3:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('station-delete')
    sys.exit()
  f = open('statconfig.ini','r')
  statuuid = f.readline().strip()
  f.close()
  deleteStatConfig(statuuid, sys.argv[2], "config-server")
elif (mode == "station-config-delete"):
  if len(sys.argv) < 3:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('station-config-delete')
    sys.exit()
  f = open('statconfig.ini','r')
  statuuid = f.readline().strip()
  f.close()
  deleteStatConfig(statuuid, sys.argv[2], "config-only")

# Inserting a new station and create a station config file
if (mode == "station-insert"):
  if len(sys.argv) < 4:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('station-insert')
    sys.exit()
  statname = sys.argv[2]
  lat = sys.argv[3].split(",")[0]
  lon = sys.argv[3].split(",")[1]

  # Generate an uuid
  statuuid = uuid.uuid4()
  statkey = uuid.uuid4()

  # Check if a statid is available: already configured, exit
  #if (os.path.exists('statconfig.ini')):
  #  print "\nStation file already present, exiting."
  #  print "Remove statconfig.ini if you want to add a new station."
  #  sys.exit()
  
  # Print stuff
  print "Station name:       " + str(statname)
  print "Station identifier: " + str(statuuid)
  print "Station location:   lat=" + str(lat) + " (Y), lon=" + str(lon) + " (X)"

  # Is this ok?
  raw_input('Is this ok? ENTER to continue, CTRL-C to abort...')
  
  # Insert the station
  if (insertStation(statuuid, statkey, statname, lat, lon) < 0):
    print "Error inserting station"
  else:
    id = cacheStatConfig(statuuid, statkey, statname, lat, lon)
    selectStatConfig(id)

# All other operations rely on an existing station file.
# At this point, a station file should exist. If not, exit.
if (not os.path.exists('statconfig.ini')):
  print "\nStation file not present, exiting."
  print 'Add a station first, before continuing, using: awsman.py station-insert "station name" lat,lon'
  sys.exit()

# Config ################################################################
# Read config file, we need the information everywhere
# A little basic: just use the order of the information...
f = open('statconfig.ini','r')
statuuid = f.readline().strip()
statkey = f.readline().strip()
statname = f.readline().strip()
statlat = f.readline().strip()
statlon = f.readline().strip()
f.close()

print "\nCurrently active station configuration:"
print "  Station name:       " + str(statname)
print "  Station identifier: " + str(statuuid)
print "  Station latitude:   " + str(statlat)
print "  Station longitude:  " + str(statlon)

# Disable/Enable station ###################################
if (mode == "station-disable"):
  disableStation(statuuid, statkey)

if (mode == "station-enable"):
  enableStation(statuuid, statkey)

# Test logger ########################################
# Set logger options #################################
if (mode == "test-logger"):
  if len(sys.argv) < 3:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('test-logger')
    sys.exit()
  print "\nTest logger connection and version"

  ttyport=getSerialPort(sys.argv[2])
  s = serial.Serial(ttyport, baudrate=9600)
  cmd="03\n"
  s.write(cmd)
  print "Sending command: " + str(cmd).strip()

  line = ""
  while (not line.startswith("# Software version")):
    line = s.readline().strip()
    print line
  # Last line contains version information
  if line.split(" ")[3] == weather_logger_version:
    print "Weather logger version OK."
  else:
    print "WARNING: Weather logger version mismatch, the combination might not work!"
  print ""

# Set logger options #################################
if (mode == "set-logger"):
  if len(sys.argv) < 5:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('set-logger')
    sys.exit()
  print "\nSet logger options"
  option = sys.argv[3]

  ttyport=getSerialPort(sys.argv[2])
  s = serial.Serial(ttyport, baudrate=9600)
  cmd="00\n"
  s.write(cmd)

  if (option == "interval"):
    interval = sys.argv[4]
    arg = sys.argv[5]
    if arg == "default":
      unitenum = 0;
    elif arg == "millis":
      unitenum = 0;
    elif arg == "sec":
      unitenum = 1;
    elif arg == "min":
      unitenum = 2;
    elif arg == "hour":
      unitenum = 3;
    print "Measurement interval: " + str(interval) + " [" + arg + "]"
    cmd="21 {0}\n".format(str(interval))
    s.write(cmd)
    print "Sending command: " + str(cmd).strip()
    cmd="22 {0}\n".format(str(unitenum))
    s.write(cmd)
    print "Sending command: " + str(cmd).strip()

  if (option == "startup"):
    arg = sys.argv[4]
    if arg == "default":
      startupenum = 0
    elif arg == "streaming":
      startupenum = 1
    elif arg == "logger":
      startupenum = 2
    print "Start-up mode: " + option
    cmd="23 {0}\n".format(str(startupenum))
    s.write(cmd)
    print "Sending command: " + str(cmd).strip()

  c = 0
  while (c < 2):
    line = s.readline().strip()
    print line
    c+=1
  print ""

# Exit here when dealing with station stuff
if (mode.startswith("station-")):
  sys.exit()

# Deal with cached measurements
# Show the cache or purge it
if (mode == "cache-show"):
  showCache()
elif (mode == "cache-clear"):
  clearCache()

# Online mode: streaming ################################################################
# Receive streaming data (listen to output of arduino)
# and upload to the server
# -test mode: do not upload to the server 
# It will also every 10 measurements try to purge the cache
if (mode == "streaming" or mode == "streaming-test"):
  if len(sys.argv) < 3:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('streaming')
    sys.exit()
  cachewait = 600 # wait 10 minutes before trying to empty the cache
  cachetimer = time.time() # this many seconds of measurements before trying to purge the error cache
  purgeCache(statuuid, statkey) # empty cache
  print "\nStreaming measurement mode"
  if (len(sys.argv) == 4):
    interval = sys.argv[3]
    print "Measurement interval [sec]: " + str(interval)
  else:
    interval = 0;
    print "Measurement interval:             using preset value"

  ttyport=getSerialPort(sys.argv[2])
  s = serial.Serial(ttyport, baudrate=9600)
  if (interval == 0):
    cmd="20\n"
  else:
    cmd="20 {0}\n".format(str(int(interval) * 1000))
  print "Sending command: " + str(cmd)
  s.write(cmd)
  print "Waiting for data..."
  while True:
    line = s.readline()
    millis = float(line.split(",")[0])
    temp = float(line.split(",")[1])
    humid = float(line.split(",")[2])
    baro = line.split(",")[3].strip()
    clocktime = datetime.now()
    mtime = clocktime.strftime("%Y%m%dT%H%M%S")
    sys.stdout.write("%(c)s,%(m)s,%(t)s,%(h)s,%(b)s\n" % {'c':mtime, 'm':millis, 't':temp, 'h':humid, 'b':baro})
    # Upload to the server (only when not in test mode)
    if mode == "streaming":
      insertMeasurement(statuuid, statkey, mtime, "temp", str(temp), False)
      insertMeasurement(statuuid, statkey, mtime, "humid", str(humid), False)
      insertMeasurement(statuuid, statkey, mtime, "baro", str(baro), False)
    # Try to upload the cache (when not in test mode)
    if mode == "streaming" and ((time.time() - cachetimer) >= cachewait):
      purgeCache(statuuid, statkey) # empty cache
      cachetimer = time.time() # reset counter

# Offline mode: download/upload ################################################################
# Upload to the server
if (mode == "data-show"):
  print "\nShow measurement data from unprocessed downloaded data files"
  print ""
  # get all filenames of data to upload, from the data dir
  # Process data and upload (do it the slow way, for now, sample by sample).
  files = glob.glob("data" + os.path.sep + "*.awd")
  for f in files:
    if os.path.exists(f + ".done"):
      print "Skipping (already uploaded): " + f
    else:
      mydata = convertDataLogToList(f)
      if len(mydata) == 0:
        print "Empty dataset, not even trying to show:\n  - the file might be corrupt, repair it or throw it away."
      else:
        printDataList(f, mydata)
  print ""

# use this for bulk data
if (mode == "data-upload"):
  print "\nUpload measurement data from file to webserver"
  # Get all filenames of data to upload, from the data dir, only active station (from statconfig)
  # Process data and upload (do it the slow way, for now, sample by sample).
  # VERY IMPORTANT!!! filter to obtain only those files that belong to the active station
  #                   (otherwise you will upload data to the wrong station, also needs the key
  #                    of the currently selected station)
  files = glob.glob("data" + os.path.sep + statuuid.strip() + "_*.awd")
  nfiles = 0
  tempfile = "data" + os.path.sep + "upload-temp.xml"
  print "\nData files found: " + str(len(files))
  for f in files:
    if os.path.exists(f + ".done"):
      print "Skipping (already uploaded): " + f
    else:
      mydata = convertDataLogToList(f)
      if len(mydata) == 0:
        print "Empty dataset, not even trying to show:\n  - the file might be corrupt, repair it or throw it away."
      else:
        nfiles += 1
        # this is where the job's done
        xml = dataListToXml(statuuid, mydata)
        uploadXml(xml, statkey)
        l = open(f + ".done", 'w')
        l.write(datetime.now().strftime("%Y%m%dT%H%M%S"))
        l.close()
  print ""
  print "Files uploaded: " + str(nfiles)
  print ""

  # Also purge the cache
  purgeCache(statuuid, statkey)
  
# undocumented, old, slow
if (mode == "data-upload-single"):
  print "\nUpload measurement data from file to webserver"
  # Get all filenames of data to upload, from the data dir, only active station (from statconfig)
  # Process data and upload (do it the slow way, for now, sample by sample).
  files = glob.glob("data" + os.path.sep + statuuid.strip() + "_*.awd")
  nfiles = 0
  print "\nData files found: " + str(len(files))
  for f in files:
    if os.path.exists(f + ".done"):
      print "Skipping (already uploaded): " + f
    else:
      mydata = convertDataLogToList(f)
      if len(mydata) == 0:
        print "Empty dataset, not even trying to show:\n  - the file might be corrupt, repair it or throw it away."
      else:
        nfiles += 1
        uploadDataList(statuuid, statkey, f, mydata)
        l = open(f + ".done", 'w')
        l.write(datetime.now().strftime("%Y%m%dT%H%M%S"))
        l.close()
  print "Files uploaded: " + str(nfiles)
  print ""

# Download from the Arduino
if (mode == "data-getlog"):
  print "\nGet the measurement log from the Arduino"
  if len(sys.argv) < 4:
    print "* ERROR Missing commandline arguments *\n"
    printHelp('data-getlog')
    sys.exit()
  
  timepat = re.compile('^(19|20)\d\d(0[1-9]|1[012])(0[1-9]|[12][0-9]|3[01])T(0[0-9]|1[0-9]|2[0-3])(0[0-9]|[1-5][0-9])(0[0-9]|[1-5][0-9])$')
  if not (timepat.match(sys.argv[3])):
    print "Time pattern not correct."
    sys.exit()

  #filename = "data" + os.path.sep + statuuid.strip() + "_" + datetime.now().strftime("%Y%m%dT%H%M%S") + ".awd"
  filename = "data" + os.path.sep + statuuid.strip() + "_" + sys.argv[3] + ".awd"
  if os.path.exists(filename):
    print "\nFile already exists, remove it manually if you want to download again to this file:"
    print filename
    sys.exit()
  print "WARNING: after a successfull download the memory is cleared!!!\n"

  starttime = datetime.strptime(sys.argv[3].strip(), "%Y%m%dT%H%M%S")
  print "Start time:         " + str(starttime).strip()
  print "Download to file:   " + str(filename).strip()

  # open file for writing
  f = open(filename, 'w')
  f.write("#DOWNLOADTIME:" + datetime.now().strftime("%Y%m%dT%H%M%S") + "\n")
  f.write("#STARTTIME:" + starttime.strftime("%Y%m%dT%H%M%S") + "\n")

  ttyport=getSerialPort(sys.argv[2])
  s = serial.Serial(ttyport, baudrate=9600)
  cmd="11\n"
  print "Sending Command: " + str(cmd)
  s.write(cmd)
  print "Waiting for data..."
  EOF = False
  rowcount = 2 # check total number of downloaded rows against stored to file, file contains two extra one rows:
  # starttime, downloadtime added
  datarowcount = 0 # check total number of downloaded datarows with the NR variable in the header
  while EOF != True:
    line = s.readline().rstrip()
    f.write(line + "\n")
    if line.startswith("#") == False:
      datarowcount -= 1 # should be zero at the end :-)
    if line.startswith("#NR"):
      datarowcount = int(line.split(":")[1])
      print "Data rows expected: " + str(datarowcount)
    if line == "#END":
      EOF = True
    rowcount += 1
  
  f.close()
  
  print "Compare expected data row count with received"
  if datarowcount == 0:
    print "OK"
  else:
    print "ERROR Expected data row count and received mismatch"
    sys.exit()    

  print "Compare received row count with saved"
  f = open(filename, 'r')
  while f.readline():
    rowcount -= 1 # we can count down now :-)
  f.close()

  if rowcount == 0: # count up and down again
    print "OK"
    print "Clearing memory"
    # And now clear mem
    cmd="10\n"
    s.write(cmd)
    print "Memory cleared, you can't download this data anymore!"
    print "You should check your download using: awsman.py data-show"
    print "Upload your data: awsman.py data-upload"
  else:
    print "ERROR Downloaded and saved row count mismatch"

# Manual input mode ################################################################
# For testing, or other means of data collection.
if (mode == "data-input"):
  print "\nManually insert and upload data to the server"
  print "Time format: YYYYMMDDTHHMMSS"
  print "Example: 20140120T132145 (mind the T between date and time part)"
  print ""
  print "Press CTRL-C to exit"
  print ""
  # do purge the cache
  purgeCache(statuuid, statkey)
  while (True):
    mtime = raw_input("Measurement time          : ")
    timepat = re.compile('^(19|20)\d\d(0[1-9]|1[012])(0[1-9]|[12][0-9]|3[01])T(0[0-9]|1[0-9]|2[0-3])(0[0-9]|[1-5][0-9])(0[0-9]|[1-5][0-9])$')
    valpat = re.compile('^[+-]?[0-9]\d*\.?\d*$')
    if not timepat.match(mtime):
      print "DateTime pattern incorrect, check it."
    else:
      temp = raw_input("Temperature [deg C]       : ")
      humid = raw_input("Humidity [%]              : ")
      baro = raw_input("Barometric pressure [hPa] : ")
      if not (valpat.match(temp) and valpat.match(humid) and valpat.match(baro)):
        print "Value input not valid (always include a dot)"
      else:
        insertMeasurement(statuuid, statkey, mtime, "temp", str(temp), False)
        insertMeasurement(statuuid, statkey, mtime, "humid", str(humid), False)
        insertMeasurement(statuuid, statkey, mtime, "baro", str(baro), False)
    print ""

sys.exit()

