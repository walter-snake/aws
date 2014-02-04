# The MIT License (MIT)
#
# Copyright (c) 2014 W. Boasson

# Python helper module for awsman.py:
# 1) managing the Arduino based weather station running my 'weather_logger' software. 
# 2) storing data on a http server using my microsds service (php/PostgreSQL/PostGIS).

import re
import httplib,urllib
import sqlite3
import os, sys
import time
import datetime
import xml.dom.minidom
from datetime import datetime
from datetime import timedelta
# Ugly, quick hack to overcome installation issues
try:
  from config import *
except:
  print ""

apiversion = "1.0"
weather_logger_version = "1"
HTTPTIMEOUTERRORTIME=time.time()
HTTPTIMEOUT=15

# If you need to use https: change the HTTPConnection into HTTPSConnection.

# Test microsds
def testMicroSdsConfig():
  try:
    conn = httplib.HTTPConnection(MSDSERVER, 80, timeout=HTTPTIMEOUT)
    conn.request("GET", MSDSERVERPATH + "/measurements.php?Operation=Test")
    r = conn.getresponse()
    status = 0
    if (r.status == 200):
      result = r.read()
      if result.find('ERROR') >= 0:
        print "ERROR MicroSDS service not ready"
        status = -1
      else:
        # test version
        if result == apiversion:
          print "INFO MicroSDS API version: " + result + " -> OK"
          status = 0
        else:
          print "ERROR MicroSDS API version not compatible: " + result + " (this: " + apiversion + ")"
          status = -2
    else:
      print "ERROR MicroSDS service not ready"
      print r.reason
      status = -1
    conn.close()
  except Exception:
    print "ERROR MicroSDS service not reachable"
    status = -3
  return status

# insert a weather station into the database
def insertStation(statuuid, statkey, statname, lat, lon):
  conn = httplib.HTTPConnection(MSDSERVER)
  conn.request("GET", MSDSERVERPATH + "/measurements.php?Operation=AddStation&UUID=" + str(statuuid) + "&Name=" 
    + urllib.quote(statname) + "&Lat=" + str(lat) + "&Lon=" + str(lon) + "&Key=" + str(statkey))
  r = conn.getresponse()
  status = 0
  if (r.status == 200):
    result = r.read()
    if result.find('ERROR') >= 0:
      print "ERROR Station not inserted (server message)"
      status = -1
    else:
      print "INFO Insert station: " + statname + "->" + result
      status = 0
  else:
    print "ERROR Station not inserted"
    print r.reason
    status = -2
  conn.close()
  return status

# delete a weather station and measurements from the database
def deleteStation(statuuid, statkey):
  conn = httplib.HTTPConnection(MSDSERVER)
  conn.request("GET", MSDSERVERPATH + "/measurements.php?Operation=DropStation&UUID=" + str(statuuid) + "&Key=" + str(statkey))
  r = conn.getresponse()
  status = 0
  if (r.status == 200):
    result = r.read()
    if result.find('ERROR') >= 0:
      print "ERROR Station not deleted (server message)"
      status = -1
    else:
      print "INFO Deleted station->" + result 
      status = 0
  else:
    print "ERROR Station not deleted"
    print r.reason
    status = -2
  conn.close()
  return status

# deactive a weather station
def disableStation(statuuid, statkey):
  conn = httplib.HTTPConnection(MSDSERVER)
  conn.request("GET", MSDSERVERPATH + "/measurements.php?Operation=DisableStation&UUID=" + str(statuuid) + "&Key=" + str(statkey))
  r = conn.getresponse()
  if (r.status == 200):
    print "INFO Disable station: " + statuuid + "->" + r.read()
  else:
    print "ERROR Station not deactivated"
    print r.reason
  conn.close()

# activate a weather station
def enableStation(statuuid, statkey):
  conn = httplib.HTTPConnection(MSDSERVER)
  conn.request("GET", MSDSERVERPATH + "/measurements.php?Operation=EnableStation&UUID=" + str(statuuid) + "&Key=" + str(statkey))
  r = conn.getresponse()
  if (r.status == 200):
    print "INFO Enable station: " + statuuid + "->" + r.read()
  else:
    print "ERROR Station not activated"
    print r.reason
  conn.close()

# insert a measurement into the database
def insertMeasurement(statuuid, statkey, measurementtime, param, value, fromcache):
  # a bit ugly, simulate an httperror in case connection cannot be made
  httpstatus = 0
  # Reset http timeout time after a certain amount of time
  global HTTPTIMEOUTERRORTIME
  global HTTPTIMEOUT
  if time.time() - HTTPTIMEOUTERRORTIME >= 30: # just reset the timeout, when old enough
    HTTPTIMEOUT=15
  try:
    conn = httplib.HTTPConnection(MSDSERVER, 80, timeout=HTTPTIMEOUT)
    conn.request("GET", MSDSERVERPATH + "/measurements.php?Operation=InsertMeasurement&UUID=" + str(statuuid).strip() + "&Key=" + str(statkey).strip() + "&MeasuredProperty=" + param.strip() + "&MeasuredValue=" + str(value).strip() + "&MeasurementTime=" + measurementtime.strip())
    r = conn.getresponse()
    httpstatus = r.status
  except:
    httpstatus = 0 # this is sort of true: timeout/no response
    # to prevent cache uploads from stalling everything, make sure it breaks out fast in case of a timeout
    if HTTPTIMEOUT > 0: # only set timeouterrortime at the first occurence of a timeout
      HTTPTIMEOUTERRORTIME = time.time()
    HTTPTIMEOUT=0 # in case of an error, effectively disable sending (for so many seconds: 30)

  state = 1
  if (httpstatus == 200):
    result = r.read()
    print "INFO " + param + " " + str(value) + "->" + result
    if result.find('ERROR') >= 0:
      if not fromcache:
        cacheMeasurement(statuuid.strip(), measurementtime.strip(), param.strip(), str(value).strip())
      print "ERROR Detected an error, I will cache your measurement: "
      state = 1
    else:
      state = 0
  else:
    if not fromcache:
      cacheMeasurement(statuuid.strip(), measurementtime.strip(), param.strip(), str(value).strip())
    print "ERROR Measurement not inserted, I cached it."
    if not httpstatus == 0:
      print r.reason
    state = 1

  conn.close()
  return state

# prepare upload cache db
def prepareCacheDb():
  localDb = "data" + os.path.sep + "upload-cache.sqlite"
  if (not os.path.exists("data")):
    os.makedirs("data")
  if (not os.path.exists(localDb)):
    conn = sqlite3.connect(localDb)
    c = conn.cursor()
    c.execute("""CREATE TABLE measurement_cache (station_uuid text, measurement_time text, param text, mvalue text)""")
    conn.commit()
    conn.close()
    print "-> Cache created\n"

# clear cache (simply delete the db)
def clearCache():
  localDb = "data" + os.path.sep + "upload-cache.sqlite"
  os.remove(localDb)
  print "-> Cache dropped\n"
  prepareCacheDb()

# insert a measurement into the upload cache
def cacheMeasurement(statuuid, measurementtime, param, value):
  localDb = "data" + os.path.sep + "upload-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  c.execute('INSERT INTO measurement_cache VALUES (?,?,?,?)', [statuuid, measurementtime, param, value])
  conn.commit()
  conn.close()

# Try to purge the cache, upload data (one by one, delete if successful, commit)
def purgeCache(statuuid, statkey):
  print "\n-> Checking cache, trying to resend records, if needed and possible."
  localDb = "data" + os.path.sep + "upload-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  sql = "SELECT rowid, station_uuid, measurement_time, param, mvalue FROM measurement_cache WHERE station_uuid = ?;"
  c.execute(sql, [statuuid])
  l = c.fetchall()
  for row in l:
    result = insertMeasurement(row[1], statkey, row[2], row[3], row[4], True)
    if result == 0:
      sql = "DELETE FROM measurement_cache WHERE rowid = ?;"
      c.execute(sql , [row[0], ])
      conn.commit()
  conn.close()
  print "-> Cache processed.\n" 

# Show the cache contents
def showCache():
  print "\n-> Cache contents (raw data)"
  localDb = "data" + os.path.sep + "upload-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  sql = "SELECT rowid, station_uuid, measurement_time, param, mvalue FROM measurement_cache;"
  c.execute(sql)
  l = c.fetchall()
  print "rowid, station_uuid, measurement_time, param, mvalue"
  for row in l:
    print row
  conn.close()
  print ""

# convert a datalog to a list
def convertDataLogToList(filename):
  # Converts a datalog file to a list, with measurement times included
  data = []
  datarows = 0
  f = open(filename, 'r')
  minterval = 0
  downtime = datetime.strptime("19000101T000000", "%Y%m%dT%H%M%S")
  print "Reading data file: " + filename
  for line in f:
    if line.startswith("#") == False:
      datarows += 1
      index = int(line.split(",")[0])
      temp = float(line.split(",")[1])
      humid = float(line.split(",")[2])
      baro = line.split(",")[3].strip()
      mtime = (starttime + timedelta(seconds=(minterval * index))).strftime("%Y%m%dT%H%M%S")
      data.append(dict([('index' , index), ('mtime' , mtime), ('temp' , temp), ('humid' , humid), ('baro' , baro)]))
      # sys.stdout.write("| %(i)-3s| %(t)-5s | %(h)-5s | %(b)-4s | %(d)s\n" % {'i':index, 't':temp, 'h':humid, 'b':baro, 'd':mtime})
    if line.startswith("#DOWNLOADTIME"):
      downtime = datetime.strptime(line.split(":")[1].strip(), "%Y%m%dT%H%M%S")
    if line.startswith("#STARTTIME"):
      starttime = datetime.strptime(line.split(":")[1].strip(), "%Y%m%dT%H%M%S")
    if line.startswith("#INTERVAL_MILLISECONDS"):
      minterval = int(line.split(":")[1])/1000 # make it seconds
  if (minterval == 0):
    print "Invalid file, header incomplete."
    return []
  else:
    print "Downloaded:                " + str(downtime.strftime("%Y%d%dT%H%M%S"))
    print "Number of rows:            " + str(datarows)
    print "Start time:                " + str(starttime.strftime("%Y%d%dT%H%M%S"))
    print "Measurement interval [s]:  " + str(minterval)
    print ""
    return data

# Prints  a datalist in a human readable format
def printDataList(listname, mydata):
  datarows = 0
  print "Data listing: " + listname
  sys.stdout.write("| %(i)-5s | %(d)-15s | %(t)-5s | %(h)-5s | %(b)-4s |\n" % {'i':'index', 'd':'mtime', 't':'temp', 'h':'humid', 'b':'baro'})
  print "--------------------------------------------------"
  for line in mydata:
    datarows += 1
    index = str(line['index']) 
    temp = str(line['temp']) 
    humid = str(line['humid']) 
    baro = str(line['baro']) 
    mtime = str(line['mtime']) 
    sys.stdout.write("| %(i)-5s | %(d)-15s | %(t)-5s | %(h)-5s | %(b)-4s |\n" % {'i':index, 'd':mtime, 't':temp, 'h':humid, 'b':baro})
  print "Number of rows: " + str(datarows)
  print ""

# Bulk upload a datalist, one by one (slow, not in use anymore, but functioning)
def uploadDataList(statuuid, statkey, listname, mydata):
  datarows = 0
  errors = 0
  print "Uploading data: " + listname
  for line in mydata:
    datarows += 1
    index = str(line['index']) 
    temp = str(line['temp']) 
    humid = str(line['humid']) 
    baro = str(line['baro']) 
    mtime = str(line['mtime'])

    print str(mtime)
    sys.stdout.write("  ")
    errors += insertMeasurement(statuuid, statkey, mtime, 'temp', temp, False)
    sys.stdout.write("  ")
    errors += insertMeasurement(statuuid, statkey, mtime, 'humid', humid, False)
    sys.stdout.write("  ")
    errors += insertMeasurement(statuuid, statkey, mtime, 'baro', baro, False)
  print "Number of records processed: " + str(datarows) + " (" + str(datarows * 3) + " measured values)"
  print "Number of errors during upload: " + str(errors) + " (cached, prepared for upload)"
  print ""

# Translate a datalist to xml, returns compacted XML string
def dataListToXml(statuuid, mydata):
  print "Converting to XML..."
  xml_doc = xml.dom.minidom.Document()
  el_log = xml_doc.createElementNS("http://www.boaedificat.eu/arduino/datalogger", "log")
  xml_doc.appendChild(el_log)
  for d in mydata:
    for s in ['temp', 'humid', 'baro']:
      el_sample = xml_doc.createElement("sample")
      el_sample.setAttribute("statuuid", statuuid)
      el_sample.setAttribute("mtime", d['mtime'])
      el_log.appendChild(el_sample)
      addDataNodeXml(xml_doc, el_sample, 'param', s)
      addDataNodeXml(xml_doc, el_sample, 'value', d[s])
  x = xml_doc.toxml() # very compact
  xml_doc.unlink()
  return x

# Add one datanode to the xml
def addDataNodeXml(xmldoc, xmlel, param, value):
  tempChild = xmldoc.createElement(param)
  xmlel.appendChild(tempChild)
  nodeText = xmldoc.createTextNode(str(value))
  tempChild.appendChild(nodeText)

# Pretty prints an xml string, need to parse it first
def prettyPrintXml(xmlstring):
  xml_doc = xml.dom.minidom.parseString(xmlstring)
  x = xml_doc.toprettyxml(indent = '  ')
  xml_doc.unlink()
  text_re = re.compile('>\n\s+([^<>\s].*?)\n\s+</', re.DOTALL)    
  prettyXml = text_re.sub('>\g<1></', x)
  return prettyXml

# Upload XML file to the server
def uploadXmlFile(xmlfile, statkey):
  print "Uploading XML to server..."
  conn = httplib.HTTPConnection(MSDSERVER)
  headers = {"Content-type" : "application/xml", "Accept" : "text/plain"}
  conn.request("POST", MSDSERVERPATH + "/measurements.php?Operation=InsertAsXml&Key=" + str(statkey) , open(xmlfile,'r'), headers)
  r = conn.getresponse()
  if (r.status == 200):
    print r.read()
  else:
    print "ERROR while uploading"
  print ""

# Upload XML string to the server
def uploadXml(xml, statkey):
  print "Uploading XML to server..."
  conn = httplib.HTTPConnection(MSDSERVER)
  headers = {"Content-type" : "application/xml", "Accept" : "text/plain"}
  conn.request("POST", MSDSERVERPATH + "/measurements.php?Operation=InsertAsXml&Key=" + str(statkey) , xml, headers)
  r = conn.getresponse()
  if (r.status == 200):
    print r.read()
  else:
    print "ERROR while uploading"
  print ""

# prepare config cache db
def prepareConfigDb():
  localDb = "config-cache.sqlite"
  if (not os.path.exists(localDb)):
    conn = sqlite3.connect(localDb)
    c = conn.cursor()
    c.execute("""CREATE TABLE station_cache (station_uuid text, station_key text, station_name text, lat real, lon real)""")
    conn.commit()
    conn.close()
    print "-> Config database created\n"

# add station config 
def cacheStatConfig(statuuid, statkey, statname, lat, lon):
  localDb = "config-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  c.execute('INSERT INTO station_cache VALUES (?,?,?,?,?)', [str(statuuid), str(statkey), str(statname), float(lat), float(lon)])
  sql = "SELECT MAX(rowid) FROM station_cache;"
  c.execute(sql)
  l = c.fetchone()
  conn.commit()
  conn.close()
  return l[0]

# Try to purge the cache, upload data (one by one, delete if successful, commit)
def showStatConfig():
  localDb = "config-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  sql = "SELECT rowid, station_uuid, station_key, station_name, lat, lon FROM station_cache;"
  c.execute(sql)
  l = c.fetchall()
  for row in l:
    print row
  conn.close()

def selectStatConfig(id):
  print "Activate station configuration"
  localDb = "config-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  sql = "SELECT rowid, station_uuid, station_key, station_name, lat, lon FROM station_cache WHERE rowid = ?;"
  c.execute(sql, [id,])
  l = c.fetchone()

  # Write the file
  f = open('statconfig.ini','w')
  f.write(l[1] + "\n")
  f.write(l[2] + "\n")
  f.write(l[3] + "\n")
  f.write(str(l[4]) + "\n")
  f.write(str(l[5]) + "\n")
  f.close()

def deleteStatConfig(activestatuuid, id, mode):
  print "Delete station and data from server."
  localDb = "config-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  sql = "SELECT rowid, station_uuid, station_key, station_name, lat, lon FROM station_cache WHERE rowid = ?;"
  c.execute(sql, [id,])
  l = c.fetchone()
  statuuid = l[1]
  statkey = l[2]
  statname = l[3]
  conn.commit()
  conn.close()

  if activestatuuid == statuuid:
    print ""
    print "WARNING: You are about to delete the currently ACTIVE station!"
    print ""

  if mode == 'config-server':
    print "Do you really want to delete the station from the server, including all measurements?"
    print "WARNING: YOU WILL NOT BE ABLE TO MANAGE THE STATION (" + str(statname) + ") ANYMORE!"
    print "WARNING: ALL DATA FOR THIS STATION (" + str(statname) + ") WILL BE LOST!"
    drop = raw_input("Enter the name of the station to continue: ")
    if drop == statname:
      print "Asking server to remove station and associated data..."
      if deleteStation(statuuid, statkey) == 0:
        dropLocalStatConfig(id)
  elif mode == 'config-only':
    print "Do you really want to delete the station configuration?"
    print "WARNING: YOU WILL NOT BE ABLE TO MANAGE THE STATION (" + str(statname) + ") ANYMORE!"
    drop = raw_input("Enter the name of the station to continue: ")
    if drop == statname:
      dropLocalStatConfig(id)

  if activestatuuid == statuuid and drop == statname:
    os.remove('statconfig.ini')
    print "INFO: The station configuration file has been removed!"

def dropLocalStatConfig(id):
  localDb = "config-cache.sqlite"
  conn = sqlite3.connect(localDb)
  c = conn.cursor()
  sql = "DELETE FROM station_cache WHERE rowid = ?;"
  c.execute(sql, [id,])
  print "Station removed from local config database."
  conn.commit()
  conn.close()
