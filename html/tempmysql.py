#!/usr/bin/python
import MySQLdb as mdb
import sys
import time
from datetime import datetime
outputvar=''
		
try:
	con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
	cur = con.cursor()
	query = ("SELECT id, temperature, temperatureF, timestamp FROM currenttemp")
	cur.execute(query)
	data = cur.fetchall ()
	for row in data :
		outputvar += "temp" + str(row[0]) + ":" + str(row[1]) + " tempF" + str(row[0]) + ":" + str(row[2]) + " "
		if row[0] == 1:
			timestamp2 = row[3]
	
except mdb.Error, e:
	if con:
		con.rollback()
		
	print "Error %d: %s" % (e.args[0],e.args[1])
	sys.exit(1)
		
finally:    
	if con:    
		con.close()

timestamp = datetime.utcnow()
t1=str(timestamp)
t2=str(timestamp2)
t3=time.mktime(time.strptime(t1,"%Y-%m-%d %H:%M:%S.%f"))-time.mktime(time.strptime(t2, "%Y-%m-%d %H:%M:%S"))
outputvar += " tempage:" + str(t3)
if t3 >= 60:
	print "Error no temperature Reading in over 60 seconds"
elif t3 < 60:
	print outputvar
else:
	print "An unknown error occurred"
