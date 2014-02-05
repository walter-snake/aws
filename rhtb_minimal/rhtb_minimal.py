#!/usr/bin/env python

# Minimal receiver for Arduino data
# -*- coding: ascii -*-

# we do need a few libraries (pretty standard ones, except for serial, which might have to be installed)
import sys
import serial
from datetime import datetime

# Serial port
serial_port = sys.argv[1]

# Start listening and throw data to screen
s = serial.Serial(serial_port, baudrate=9600)
while True:
  received = s.readline().strip()
  print datetime.now().strftime("%Y%m%dT%H%M%S")+","+received

