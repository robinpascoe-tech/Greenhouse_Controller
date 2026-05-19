#!/usr/bin/python


############################################################################
# Check Sensors
# Script run by CRON to check sensors and input information into database.
# Author: Robin Pascoe
# Version 1.3
# Last Modified April 29 2016
############################################################################


import MySQLdb as mdb
import sys
from decimal import Decimal
import time
from datetime import datetime

import os
import glob

os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

# Temp Sensor ID's
FrontTempSensor = '28-0315018710ff'
BackTempSensor = '28-04150123f0ff'
PiTempSensor = '28-031515b5faff'
OutsideTempSensor = '28-0215036e59ff'
WoodStoveTempSensor = '28-031504bcbfff'


def getavgtemp( tempsensorid ):
    """Read Temperature from Sensor 6 times drop 2 and average the output"""
    avgtemperatures = []
    temperatures = []
    BadFileReadLoop = 0
    # For Loop - Read Temperature 3 Times.
    for polltime in range(0,3):
        text = ''
        # Check that the CRC check is successful - if not re-read until it is.
        while text.split("\n")[0].find("YES") == -1:
            # Try to open the File, if not found or other error return that sensor is BAD.
            try:
                tfile = open("/sys/bus/w1/devices/"+ tempsensorid +"/w1_slave")
                # Read all of the text in the file.
                text = tfile.read()
                # Close the file now that the text has been read.
                tfile.close()
                BadFileReadLoop += 1
                # If we fail to read the sensor 5 times indicate sensor is bad and exit.
                if BadFileReadLoop > 4:
                    avgtemperatures.insert(0, 85)
                    avgtemperatures.insert(1, 0)
                    return avgtemperatures
                time.sleep(0)
            except IOError as e:
                print "I/O error({0}): {1}".format(e.errno, e.strerror)
                avgtemperatures.insert(0, 85)
                avgtemperatures.insert(1, 0)
                return avgtemperatures
            except:
                print "Unexpected error:", sys.exc_info()[0]
                avgtemperatures.insert(0, 85)
                avgtemperatures.insert(1, 0)
                return avgtemperatures
        # Split the text with new lines (\n) and select the second line.
        secondline = text.split("\n")[1]
        # Split the line into words, referring to the spaces, and select the 10th word (counting from 0).
        temperaturedata = secondline.split(" ")[9]
        # The first two characters are "t=", so get rid of those and convert the temperature from a string to a number.
        temperature = float(temperaturedata[2:])
        # Put the decimal point in the right place and display it.
        temperatures.append(temperature / 1000)
        # Wait before reading sensor again.
        time.sleep(0)
    temperatures = sorted(temperatures)
    # Use below to drop the 1st and 2nd temp readings.
    # del temperatures[6]
    # del temperatures[0]
    # ### Average out the temperature, then return them.
    avgtemperatures.append(sum(temperatures) / float(len(temperatures)))
    # insert 1 into second item in array to indicate that sensor reading is good.
    avgtemperatures.insert(1, 1)
    return avgtemperatures

# Grab each of the temperature readings
FrontTempC = getavgtemp(FrontTempSensor)
BackTempC = getavgtemp(BackTempSensor)
PiTempC = getavgtemp(PiTempSensor)
OutsideTempC = getavgtemp(OutsideTempSensor)
WoodStoveTempC = getavgtemp(WoodStoveTempSensor)
AvgTemps = []
AvgTempC = []

# Convert readings to *F and mask to 2 decimal places.
TWOPLACES = Decimal(10) ** -2       # same as Decimal('0.01')

if FrontTempC[1] == 1:
    FrontTempC = Decimal(FrontTempC[0]).quantize(TWOPLACES)
    FrontTempF = ((FrontTempC*9)/5)+32
    FrontTempF = Decimal(FrontTempF).quantize(TWOPLACES)
    AvgTemps.append(FrontTempC)
    FrontTempError = 1
else:
    FrontTempError = 0

if BackTempC[1] == 1:
    BackTempC = Decimal(BackTempC[0]).quantize(TWOPLACES)
    BackTempF = ((BackTempC*9)/5)+32
    BackTempF = Decimal(BackTempF).quantize(TWOPLACES)
    AvgTemps.append(BackTempC)
    BackTempError = 1
else:
    BackTempError = 0

if PiTempC[1] == 1:
    PiTempC = Decimal(PiTempC[0]).quantize(TWOPLACES)
    PiTempF = ((PiTempC*9)/5)+32
    PiTempF = Decimal(PiTempF).quantize(TWOPLACES)
#    AvgTemps.append(PiTempC)
    PiTempError = 1
else:
    PiTempError = 0

if not AvgTemps:
    AvgTempError = 0
else:
    AvgTemps = sorted(AvgTemps)
    AvgTempC.append(sum(AvgTemps) / int(len(AvgTemps)))
    AvgTempC = Decimal(AvgTempC[0]).quantize(TWOPLACES)
    AvgTempF = ((AvgTempC*9)/5)+32
    AvgTempF = Decimal(AvgTempF).quantize(TWOPLACES)
    AvgTempError = 1

if OutsideTempC[1] == 1:
    OutsideTempC = Decimal(OutsideTempC[0]).quantize(TWOPLACES)
    OutsideTempF = ((OutsideTempC*9)/5)+32
    OutsideTempF = Decimal(OutsideTempF).quantize(TWOPLACES)
    OutsideTempError = 1
else:
    OutsideTempError = 0

if WoodStoveTempC[1] == 1:
    WoodStoveTempC = Decimal(WoodStoveTempC[0]).quantize(TWOPLACES)
    WoodStoveTempF = ((WoodStoveTempC*9)/5)+32
    WoodStoveTempF = Decimal(WoodStoveTempF).quantize(TWOPLACES)
    WoodStoveTempError = 1
else:
    WoodStoveTempError = 0

timestamp = datetime.utcnow()

try:
    con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
    cur = con.cursor()
    if FrontTempError == 1:
        cur.execute("UPDATE currenttemp SET temperature = %s, temperatureF = %s, timestamp = %s WHERE Name = %s",
            (BackTempC, BackTempF, timestamp, "BackTemp"))
        print "Number of rows updated:",  cur.rowcount
    if BackTempError == 1:
        cur.execute("UPDATE currenttemp SET temperature = %s, temperatureF = %s, timestamp = %s WHERE Name = %s",
            (FrontTempC, FrontTempF, timestamp, "FrontTemp"))
        print "Number of rows updated:",  cur.rowcount
    if PiTempError == 1:
        cur.execute("UPDATE currenttemp SET temperature = %s, temperatureF = %s, timestamp = %s WHERE Name = %s",
            (PiTempC, PiTempF, timestamp, "PiTemp"))
        print "Number of rows updated:",  cur.rowcount
    if AvgTempError == 1:
        cur.execute("UPDATE currenttemp SET temperature = %s, temperatureF = %s, timestamp = %s WHERE Name = %s",
            (AvgTempC, AvgTempF, timestamp, "AverageInsideTemp"))
        print "Number of rows updated:",  cur.rowcount
    if OutsideTempError == 1:
        cur.execute("UPDATE currenttemp SET temperature = %s, temperatureF = %s, timestamp = %s WHERE Name = %s",
            (OutsideTempC, OutsideTempF, timestamp, "OutsideTemp"))
        print "Number of rows updated:",  cur.rowcount
    if WoodStoveTempError == 1:
        cur.execute("UPDATE currenttemp SET temperature = %s, temperatureF = %s, timestamp = %s WHERE Name = %s",
            (WoodStoveTempC, WoodStoveTempF, timestamp, "WoodstoveTemp"))
        print "Number of rows updated:",  cur.rowcount
    con.commit()

except mdb.Error, e:
    if con:
        con.rollback()
    print "Error %d: %s" % (e.args[0],e.args[1])
    sys.exit(1)

finally:
    if con:
        con.close()

