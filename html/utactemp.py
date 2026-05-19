#!/usr/bin/python
import urllib2 #import python library which does http requests
import xml.dom.minidom as mdom #imports xml parser called minidom
import MySQLdb as mdb
import sys
from decimal import Decimal
import time
from datetime import datetime

count=0
while (count==0):
	
	base_url = 'http://192.168.2.200:5051/index.xml'
	#downloads data from xml file
	
	try:
		response = urllib2.urlopen(base_url)
	except urllib2.HTTPError, err:
		if err.code == 404:
			print "Page not found!"
		elif err.code == 403:
			print "Access denied!"
		else:
			print "something happened! Error code", err.code
	except urllib2.URLError, err:
		print "some other error happened:", err.reason
		
	data = response.read()
	response.close()
	dom = mdom.parseString(data)
	xmlTag = dom.getElementsByTagName('temp0')[0].toxml()
	xmlData = xmlTag.replace('<temp0>', '').replace('</temp0>', '')
	print xmlData
	
	TWOPLACES = Decimal(10) ** -2       # same as Decimal('0.01')
	tempc=Decimal(xmlData)
	tempf=((tempc*9)/5)+32
	tempf=Decimal(tempf).quantize(TWOPLACES)
	timestamp = datetime.utcnow()
		
	try:
		con = mdb.connect('localhost', 'root', 'change_this_password', 'greenhouse');
		cur = con.cursor()
		cur.execute("UPDATE currenttemp SET temperature = %s, temperatureF = %s, timestamp = %s WHERE id = %s",
			(tempc, tempf, timestamp, "1"))
	
		con.commit()
		print "Number of rows updated:",  cur.rowcount
	
	except mdb.Error, e:
	
		if con:
			con.rollback()
			
		print "Error %d: %s" % (e.args[0],e.args[1])
		sys.exit(1)
		
	finally:    
				
		if con:    
			con.close()
	time.sleep( 30 )
