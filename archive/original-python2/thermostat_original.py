#!/usr/bin/python
#################################################################
# Green House Control Program									#
# Created by: Robin Pascoe 		with code from several sources	#
#																#
# Version 2017-04-16											#
#			Y  M  D												#
#################################################################

import MySQLdb as mdb
import sys
import time
import datetime
from decimal import *
import logging
import logging.handlers
import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

#########################
# Logging
#########################
LOG_FILENAME = '/home/pi/thermostat.log'

#####################################
FORMAT="%(asctime)-15s %(message)s"
my_logger=logging.getLogger("MyLogger")
my_logger.setLevel(logging.DEBUG)
fh=logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=2048, backupCount=5)
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter(FORMAT))
my_logger.addHandler(fh)
###############################

#Log when program starts up
my_logger.debug("Greenhouse Thermostat started")

#########################
# GPIO Settings
#########################
# Window Reverser
windowreversergpio = 22
# Window
windowgpio = 17
# Roof Window Reverser
roofreversergpio = 9
# Roof Window
roofgpio = 10
# Ventilation Fan
ventfangpio = 5
# AUX Ventilation Fan
auxventfangpio = 11
# Heater
heatergpio = 19
# Circulation Fan
circfangpio = 6

# Unused GPIO Relays
unusedgpio1 = 13
unusedgpio2 = 26
# 27 relay bad
unusedgpio3 = 27


#########################
# Setup GPIO outputs.
#########################
GPIO.setup(windowreversergpio, GPIO.OUT)
GPIO.setup(windowgpio, GPIO.OUT)
GPIO.setup(ventfangpio, GPIO.OUT)
GPIO.setup(auxventfangpio, GPIO.OUT)
GPIO.setup(circfangpio, GPIO.OUT)
GPIO.setup(heatergpio, GPIO.OUT)
GPIO.setup(unusedgpio1, GPIO.OUT)
GPIO.setup(unusedgpio2, GPIO.OUT)
GPIO.setup(unusedgpio3, GPIO.OUT)
GPIO.setup(roofreversergpio, GPIO.OUT)
GPIO.setup(roofgpio, GPIO.OUT)

#########################
# Lets make sure that EVERYTHING is shutoff and closed before we start the schedule.
#########################
GPIO.output(ventfangpio, GPIO.LOW)
GPIO.output(auxventfangpio, GPIO.LOW)
GPIO.output(circfangpio, GPIO.LOW)
GPIO.output(heatergpio, GPIO.LOW)
GPIO.output(unusedgpio1, GPIO.LOW)
GPIO.output(unusedgpio2, GPIO.LOW)
GPIO.output(unusedgpio3, GPIO.LOW)

# print "closing windows"
# Close the windows in case they were left open somehow.
GPIO.output(roofreversergpio, GPIO.LOW)
GPIO.output(windowreversergpio, GPIO.LOW)
GPIO.output(windowgpio, GPIO.HIGH)
time.sleep (20)
GPIO.output(roofgpio, GPIO.HIGH)
time.sleep (20)
GPIO.output(roofgpio, GPIO.LOW)
GPIO.output(windowgpio, GPIO.LOW)

# print "updating database to show off"
##########################
# Update Database to show that everything is OFF
##########################
try:
	con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
	cur = con.cursor()
	cur.execute("UPDATE status SET heater = %s, fan = %s, circfan = %s, window = %s WHERE id = %s",
				(0, 0, 0, 0, 1))
	con.commit()
except mdb.Error, e:
	if con:
		con.rollback()
	print "Error %d: %s" % (e.args[0], e.args[1])
	my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error updating database to show that everything is off")
finally:
	if con:
		con.close()

##########################
# Let's wait another 5 seconds before we get underway.
##########################
time.sleep(5)

##########################
# Read temperatures in from database.
##########################
def getmysqltemps():
	outputvar = ''
	temperatures = []
	timestamps = []
	tempages = []
	try:
		con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse')
		cur = con.cursor()
		query = ("SELECT id, temperature, temperatureF, timestamp FROM currenttemp")
		cur.execute(query)
		data = cur.fetchall()
		for row in data:
			temperatures.append(str(row[1]))
			timestamps.append(str(row[3]))
		timestamp = datetime.datetime.utcnow()
		t1 = str(timestamp)
		for times in timestamps:
			t2 = ''
			t3 = ''
			t2 = str(times)
			t3 = time.mktime(time.strptime(t1, "%Y-%m-%d %H:%M:%S.%f")) - time.mktime(time.strptime(t2, "%Y-%m-%d %H:%M:%S"))
			tempages.append(t3)
		return temperatures, tempages

	except mdb.Error, e:
		if con:
			con.rollback()

		print "Error %d: %s" % (e.args[0], e.args[1])
		my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error getting Temperatures from database")
		sys.exit(1)

	finally:
		if con:
			con.close()


def shutdownnow():
	#########################
	# Something's gone wrong, let's play it safe and shut everything down.
	#########################
	print"SHUTDOWN NOW!!!! THIS IS NOT A DRILL"
	GPIO.output(ventfangpio, GPIO.LOW)
	GPIO.output(auxventfangpio, GPIO.LOW)
	GPIO.output(circfangpio, GPIO.LOW)
	GPIO.output(heatergpio, GPIO.LOW)
	GPIO.output(unusedgpio1, GPIO.LOW)
	GPIO.output(unusedgpio2, GPIO.LOW)
	GPIO.output(unusedgpio3, GPIO.LOW)
	GPIO.output(roofreversergpio, GPIO.LOW)
	GPIO.output(windowreversergpio, GPIO.LOW)
	GPIO.output(windowgpio, GPIO.HIGH)
	time.sleep (20)
	GPIO.output(roofgpio, GPIO.HIGH)
	time.sleep (20)
	GPIO.output(roofgpio, GPIO.LOW)
	GPIO.output(windowgpio, GPIO.LOW)
	my_logger.debug("Somethings gone wrong SHUTTING EVERYTHING DOWN NOW")
	sys.exit()


def getschedulesettings():
	##########################
	# Read temperature settings from database.
	##########################
	hightemp = []
	lowtemp = []
	hightemprange = []
	lowtemprange = []
	windowtemp = []
	windowtemprange = []
	starttime = []
	endtime = []
	circfan = []
	try:
		con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse')
		cur = con.cursor()
		query = ("SELECT id, hightemp, lowtemp, hightemprange, lowtemprange, windowtemp, windowtemprange, starttime, endtime, circfan FROM settings")
		cur.execute(query)
		data = cur.fetchall()
		for row in data:
			hightemp.append(str(row[1]))
			lowtemp.append(str(row[2]))
			hightemprange.append(str(row[3]))
			lowtemprange.append(str(row[4]))
			windowtemp.append(str(row[5]))
			windowtemprange.append(str(row[6]))
			starttime.append(str(row[7]))
			endtime.append(str(row[8]))
			circfan.append(str(row[9]))
		# Determine what schedule we're running on and populate variables.
		timestamp = time.strftime("%H:%M:%S")
		t1 = str(timestamp)
		t2 = endtime[0]
		# Convert times to datetime format to be able to compare them.
		t1 = datetime.datetime.strptime(t1, "%H:%M:%S").time()
		t2 = datetime.datetime.strptime(t2, "%H:%M:%S").time()
		if t1 < t2:
			return hightemp[0], lowtemp[0], hightemprange[0], lowtemprange[0], windowtemp[0], windowtemprange[0], circfan[0]

		t2 = endtime[1]
		t2 = datetime.datetime.strptime(t2, "%H:%M:%S").time()
		if t1 < t2:
			return hightemp[1], lowtemp[1], hightemprange[1], lowtemprange[1], windowtemp[1], windowtemprange[1], \
				   circfan[1]

		t2 = endtime[2]
		t2 = datetime.datetime.strptime(t2, "%H:%M:%S").time()
		if t1 < t2:
			return hightemp[2], lowtemp[2], hightemprange[2], lowtemprange[2], windowtemp[2], windowtemprange[2], \
				   circfan[2]

		t2 = endtime[3]
		t2 = datetime.datetime.strptime(t2, "%H:%M:%S").time()
		if t1 < t2:
			return hightemp[3], lowtemp[3], hightemprange[3], lowtemprange[3], windowtemp[3], windowtemprange[3], \
				   circfan[3]

	except mdb.Error, e:
		if con:
			con.rollback()

		print "Error %d: %s" % (e.args[0], e.args[1])
		my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error getting temperature settings from database.")
		sys.exit(1)

	finally:
		if con:
			con.close()

def getoverridesettings():
	##########################
	# Read override settings from database.
	##########################
	windowoverride = []
	windowoverrideexpire = []
	ventfanoverride = []
	ventfanoverrideexpire = []
	windowoverride1 = 0
	ventfanoverride1 = 0
	try:
		con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse')
		cur = con.cursor()
		query = ("SELECT id, windowoverride, windowexpire, fanoverride, fanexpire FROM overrides")
		cur.execute(query)
		data = cur.fetchall()
		for row in data:
			windowoverride.append(str(row[1]))
			windowoverrideexpire.append(str(row[2]))
			ventfanoverride.append(str(row[3]))
			ventfanoverrideexpire.append(str(row[4]))
		# Determine what schedule we're running on and populate variables.
		timestamp = datetime.datetime.utcnow()
		t1 = str(timestamp)
		t2 = str(windowoverrideexpire[0])
		t3 = str(ventfanoverrideexpire[0])
		# Convert times to datetime format to be able to compare them.
		t12 = time.mktime(time.strptime(t1, "%Y-%m-%d %H:%M:%S.%f")) 
		t22 = time.mktime(time.strptime(t2, "%Y-%m-%d %H:%M:%S"))
		t32 = time.mktime(time.strptime(t3, "%Y-%m-%d %H:%M:%S"))
		if int(windowoverride[0]) == 1:
			if t12 < t22:
				windowoverride1 = 1
			else:
				windowoverride1 = 0
		else:
			windowoverride1 = 0
		
		if int(ventfanoverride[0]) == 1:
			if t12 < t32:
				ventfanoverride1 = 1
			else:
				ventfanoverride1 = 0
		else:
			ventfanoverride1 = 0
			
		return windowoverride1, ventfanoverride1
		
	except mdb.Error, e:
		if con:
			con.rollback()

		print "Error %d: %s" % (e.args[0], e.args[1])
		my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error getting override settings from database")
		sys.exit(1)

	finally:
		if con:
			con.close()	

def ventilationfan(workingtemp1, hightemp1, hightemprange1, ventfangpio1, auxventfangpio1, ventfanoverride3):
	##########################
	# Control Ventilation Fans.
	##########################
	halfrange = Decimal(hightemprange1) / 2
	workingtemp1 = Decimal(workingtemp1)
	hightemp1 = Decimal(hightemp1)
	highcut1 = hightemp1 - halfrange
	lowcut1 = hightemp1 + halfrange
	if ventfanoverride3 == 0:
		if workingtemp1 <= highcut1:
			# Fan OFF
			GPIO.output(ventfangpio1, GPIO.LOW)
			GPIO.output(auxventfangpio1, GPIO.LOW)
			# Update fan status in database
			try:
				con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
				cur = con.cursor()
				cur.execute("UPDATE status SET fan = %s WHERE id = %s",
							(0, 1))
				con.commit()
			except mdb.Error, e:
				if con:
					con.rollback()
				print "Error %d: %s" % (e.args[0], e.args[1])
				my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting ventilation fan to off in database.")
			finally:
				if con:
					con.close()
		elif workingtemp1 >= lowcut1:
			# Fan On
			GPIO.output(ventfangpio1, GPIO.HIGH)
			time.sleep(1)
			GPIO.output(auxventfangpio1, GPIO.HIGH)
			# Update fan status in database.
			try:
				con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
				cur = con.cursor()
				cur.execute("UPDATE status SET fan = %s WHERE id = %s",
						(1, 1))
				con.commit()
			except mdb.Error, e:
				if con:
					con.rollback()
				print "Error %d: %s" % (e.args[0], e.args[1])
				my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting ventilation fan to on in database")
			finally:
				if con:
					con.close()
	elif ventfanoverride3 == 1:
		# Fan On
		GPIO.output(ventfangpio1, GPIO.HIGH)
		time.sleep(1)
		GPIO.output(auxventfangpio1, GPIO.HIGH)
		# Update fan status in database.
		try:
			con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
			cur = con.cursor()
			cur.execute("UPDATE status SET fan = %s WHERE id = %s",
					(1, 1))
			con.commit()
		except mdb.Error, e:
			if con:
				con.rollback()
			print "Error %d: %s" % (e.args[0], e.args[1])
			my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting ventilation fan to on in database")
		finally:
			if con:
				con.close()		

def heater(workingtemp1, lowtemp1, lowtemprange1, heatergpio1):
	##########################
	# Control Heater.
	##########################
	halfrange = Decimal(lowtemprange1) / 2
	workingtemp1 = Decimal(workingtemp1)
	lowtemp1 = Decimal(lowtemp1)
	highcut1 = lowtemp1 - halfrange
	lowcut1 = lowtemp1 + halfrange
	if workingtemp1 >= lowcut1:
		# heater OFF
		GPIO.output(heatergpio1, GPIO.LOW)
		try:
			con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
			cur = con.cursor()
			cur.execute("UPDATE status SET heater = %s WHERE id = %s",
						(0, 1))
			con.commit()
		except mdb.Error, e:
			if con:
				con.rollback()
			print "Error %d: %s" % (e.args[0], e.args[1])
			my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting heater to off in database")
		finally:
			if con:
				con.close()

	elif workingtemp1 <= highcut1:
		# heater On
		GPIO.output(heatergpio1, GPIO.HIGH)
		try:
			con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
			cur = con.cursor()
			cur.execute("UPDATE status SET heater = %s WHERE id = %s",
						(1, 1))
			con.commit()
		except mdb.Error, e:
			if con:
				con.rollback()
			print "Error %d: %s" % (e.args[0], e.args[1])
			my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting heater to on in database")
		finally:
			if con:
				con.close()


def circulationfan(circfan1, circfangpio1):
	##########################
	# Control Circulation Fan.
	##########################
	if int(circfan1) == 0:
		# Circ Fan OFF
		GPIO.output(circfangpio1, GPIO.LOW)
		try:
			con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
			cur = con.cursor()
			cur.execute("UPDATE status SET circfan = %s WHERE id = %s",
						(0, 1))
			con.commit()
		except mdb.Error, e:
			if con:
				con.rollback()
			print "Error %d: %s" % (e.args[0], e.args[1])
			my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting circulation fan to off in database")
		finally:
			if con:
				con.close()

	elif int(circfan1) == 1:
		# Circ Fan On
		GPIO.output(circfangpio1, GPIO.HIGH)
		try:
			con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
			cur = con.cursor()
			cur.execute("UPDATE status SET circfan = %s WHERE id = %s",
						(1, 1))
			con.commit()
		except mdb.Error, e:
			if con:
				con.rollback()
			print "Error %d: %s" % (e.args[0], e.args[1])
			my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting circulation fan to on in database")
		finally:
			if con:
				con.close()

	else:
		# Circ Fan OFF
		# If something is wrong with the variable lets play it safe and shut off the fan.
		GPIO.output(circfangpio1, GPIO.LOW)
		try:
			con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
			cur = con.cursor()
			cur.execute("UPDATE status SET circfan = %s WHERE id = %s",
						(0, 1))
			con.commit()
		except mdb.Error, e:
			if con:
				con.rollback()
			print "Error %d: %s" % (e.args[0], e.args[1])
			my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting circulation fan to off in database")
		finally:
			if con:
				con.close()


def window(workingtemp1, windowtemp1, windowtemprange1, windowgpio1, windowreversergpio1, roofgpio1, roofreversergpio1, windowoverride3):
	##########################
	# Control Windows both Roof and back.
	##########################
	# Window Subroutine .....
	halfrange = Decimal(windowtemprange1) / 2
	workingtemp1 = Decimal(workingtemp1)
	windowtemp1 = Decimal(windowtemp1)
	highcut1 = windowtemp1 - halfrange
	lowcut1 = windowtemp1 + halfrange
	# Because it's dangerous to try and open the window a second time, let's make sure we know where it's at.
	try:
		con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse')
		cur = con.cursor()
		query = ("SELECT id, window FROM status")
		cur.execute(query)
		row = cur.fetchone()
		windowstatus = int(row[1])

	except mdb.Error, e:
		if con:
			con.rollback()
		print "Error %d: %s" % (e.args[0], e.args[1])
		my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error checking window status in database")

	finally:
		if con:
			con.close()
			
	if windowoverride3 == 0:
		if workingtemp1 <= highcut1:
			# Windows Need to be closed.
			if windowstatus == 1:
				GPIO.output(windowreversergpio1, GPIO.LOW)
				GPIO.output(roofreversergpio1, GPIO.LOW)
				time.sleep(0.5)
				GPIO.output(windowgpio1, GPIO.HIGH)
				time.sleep(24)
				GPIO.output(roofgpio1, GPIO.HIGH)
				time.sleep(16)
				GPIO.output(windowgpio1, GPIO.LOW)
				GPIO.output(roofgpio1, GPIO.LOW)
				try:
					con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
					cur = con.cursor()
					cur.execute("UPDATE status SET window = %s WHERE id = %s",
							(0, 1))
					con.commit()
				except mdb.Error, e:
					if con:
						con.rollback()
					print "Error %d: %s" % (e.args[0], e.args[1])
					my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting window to closed in database")
				finally:
					if con:
						con.close()

		elif workingtemp1 >= lowcut1:
			# Windows Need to be opened.
			if windowstatus == 0:
				# Because of how sensitive roof window is, let's play it safe and open 1 at a time.
				# Let's open the back window first
				GPIO.output(windowreversergpio1, GPIO.HIGH)
				time.sleep(0.5)
				GPIO.output(windowgpio1, GPIO.HIGH)
				time.sleep(35)
				GPIO.output(windowgpio1, GPIO.LOW)
				GPIO.output(windowreversergpio1, GPIO.LOW)
				# Now let's open the roof window
				GPIO.output(roofreversergpio1, GPIO.HIGH)
				time.sleep(0.5)
				GPIO.output(roofgpio1, GPIO.HIGH)
				time.sleep(14)
				GPIO.output(roofgpio1, GPIO.LOW)
				GPIO.output(roofreversergpio1, GPIO.LOW)
				try:
					con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
					cur = con.cursor()
					cur.execute("UPDATE status SET window = %s WHERE id = %s",
							(1, 1))
					con.commit()
				except mdb.Error, e:
					if con:
						con.rollback()
					print "Error %d: %s" % (e.args[0], e.args[1])
					my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting window to open database")
				finally:
					if con:
						con.close()
	elif windowoverride3 == 1:
		# Window Override Active, need to open window
		if windowstatus == 0:
			# Because of how sensitive roof window is, let's play it safe and open 1 at a time.
			# Let's open the back window first
			GPIO.output(windowreversergpio1, GPIO.HIGH)
			time.sleep(0.5)
			GPIO.output(windowgpio1, GPIO.HIGH)
			time.sleep(35)
			GPIO.output(windowgpio1, GPIO.LOW)
			GPIO.output(windowreversergpio1, GPIO.LOW)
			# Now let's open the roof window
			GPIO.output(roofreversergpio1, GPIO.HIGH)
			time.sleep(0.5)
			GPIO.output(roofgpio1, GPIO.HIGH)
			time.sleep(14)
			GPIO.output(roofgpio1, GPIO.LOW)
			GPIO.output(roofreversergpio1, GPIO.LOW)
			try:
				con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
				cur = con.cursor()
				cur.execute("UPDATE status SET window = %s WHERE id = %s",
						(1, 1))
				con.commit()
			except mdb.Error, e:
				if con:
					con.rollback()
				print "Error %d: %s" % (e.args[0], e.args[1])
				my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Error setting window to open in database")
			finally:
				if con:
					con.close()

##########################
# Thermostat Control Loop
##########################
while True:
	# print "thermostat loop run"
	# Get Temperatures and ages from database
	temperatures1, tempages1 = getmysqltemps()
	# Get override status
	windowoverride2, ventfanoverride2 = getoverridesettings()
	# id 4 = avg temp.  ### Check Avg Temp age, if it's too old check Front temp age!
	# If both are stale SHUT DOWN NOW!!!
	if tempages1[4] > 60:
		if tempages1[1] < 60:
			workingtemp = temperatures1[1]
			# my_logger.debug("tempage 1-1 <60")
			goodtemp = 1
		else:
			goodtemp = 0
	elif tempages1[4] <= 60:
		workingtemp = temperatures1[4]
		goodtemp = 1
		# my_logger.debug("temp age 1-4 < 60")
	else:
		# print "avg temp age unknown error"
		# my_logger.debug("Unknown temperature age")
		my_logger.debug("Error %d: %s" % (e.args[0], e.args[1]) + " Something went wrong checking average temperature age in database.")
		shutdownnow()
	# print "good temp ="
	# print goodtemp
	if goodtemp == 1:
		hightemp, lowtemp, hightemprange, lowtemprange, windowtemp, windowtemprange, circfan = getschedulesettings()
		# print "High Temp:", hightemp, "Low Temp", lowtemp, "High Range", hightemprange, "Low Range", lowtemprange, "Window Temp", windowtemp, "Window Temp Range", windowtemprange, "Circulation Fan", circfan
		ventilationfan(workingtemp, hightemp, hightemprange, ventfangpio, auxventfangpio, ventfanoverride2)
		heater(workingtemp, lowtemp, lowtemprange, heatergpio)
		circulationfan(circfan, circfangpio)
		window(workingtemp, windowtemp, windowtemprange, windowgpio, windowreversergpio, roofgpio, roofreversergpio, windowoverride2)

	time.sleep(20)
	
