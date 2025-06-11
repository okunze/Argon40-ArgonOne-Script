#!/usr/bin/python3

#
# This script set fan speed and monitor power button events.
#
# Fan Speed is set by sending 0 to 100 to the MCU (Micro Controller Unit)
# The values will be interpreted as the percentage of fan speed, 100% being maximum
#
# Power button events are sent as a pulse signal to BCM Pin 4 (BOARD P7)
# A pulse width of 20-30ms indicates reboot request (double-tap)
# A pulse width of 40-50ms indicates shutdown request (hold and release after 3 secs)
#
# Additional comments are found in each function below
#
# Standard Deployment/Triggers:
#  * Raspbian, OSMC: Runs as service via /lib/systemd/system/argononed.service
#  * lakka, libreelec: Runs as service via /storage/.config/system.d/argononed.service
#  * recalbox: Runs as service via /etc/init.d/
#

import sys
import os
import time
from threading import Thread
from queue import Queue

sys.path.append("/etc/argon/")
from argonsysinfo import *
from argonregister import *
from argonpowerbutton import *

# Initialize I2C Bus
bus = argonregister_initializebusobj()

OLED_ENABLED=False

if os.path.exists("/etc/argon/argoneonoled.py"):
	import datetime
	from argoneonoled import *
	OLED_ENABLED=True

OLED_CONFIGFILE = "/etc/argoneonoled.conf"
UNIT_CONFIGFILE = "/etc/argonunits.conf"

# This function converts the corresponding fanspeed for the given temperature
# The configuration data is a list of strings in the form "<temperature>=<speed>"

def get_fanspeed(tempval, configlist):
	for curconfig in configlist:
		curpair = curconfig.split("=")
		tempcfg = float(curpair[0])
		fancfg = int(float(curpair[1]))
		if tempval >= tempcfg:
			if fancfg < 1:
				return 0
			elif fancfg < 25:
				return 25
			return fancfg
	return 0

# This function retrieves the fanspeed configuration list from a file, arranged by temperature
# It ignores lines beginning with "#" and checks if the line is a valid temperature-speed pair
# The temperature values are formatted to uniform length, so the lines can be sorted properly

def load_config(fname):
	newconfig = []
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				tempval = 0
				fanval = 0
				try:
					tempval = float(tmppair[0])
					if tempval < 0 or tempval > 100:
						continue
				except:
					continue
				try:
					fanval = int(float(tmppair[1]))
					if fanval < 0 or fanval > 100:
						continue
				except:
					continue
				newconfig.append( "{:5.1f}={}".format(tempval,fanval))
		if len(newconfig) > 0:
			newconfig.sort(reverse=True)
	except:
		return []
	return newconfig

# Load OLED Config file
def load_oledconfig(fname):
	output={}
	screenduration=-1
	screenlist=[]
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				if tmppair[0] == "switchduration":
					output['screenduration']=int(tmppair[1])
				elif tmppair[0] == "screensaver":
					output['screensaver']=int(tmppair[1])
				elif tmppair[0] == "screenlist":
					output['screenlist']=tmppair[1].replace("\"", "").split(" ")
				elif tmppair[0] == "enabled":
					output['enabled']=tmppair[1].replace("\"", "")
	except:
		return {}
	return output

# Load Unit Config file
def load_unitconfig(fname):
	output={"temperature": "C"}
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.strip()
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue
				if tmppair[0] == "temperature":
					output['temperature']=tmppair[1].replace("\"", "")
	except:
		return {}
	return output

def load_fancpuconfig():
	fanconfig = ["65=100", "60=55", "55=30"]
	tmpconfig = load_config("/etc/argononed.conf")
	if len(tmpconfig) > 0:
		fanconfig = tmpconfig
	return fanconfig


def load_fanhddconfig():
	fanhddconfig = ["50=100", "40=55", "30=30"]
	fanhddconfigfile = "/etc/argononed-hdd.conf"

	if os.path.isfile(fanhddconfigfile):
		tmpconfig = load_config(fanhddconfigfile)
		if len(tmpconfig) > 0:
			fanhddconfig = tmpconfig
	else:
		fanhddconfig = []
	return fanhddconfig

# This function is the thread that monitors temperature and sets the fan speed
# The value is fed to get_fanspeed to get the new fan speed
# To prevent unnecessary fluctuations, lowering fan speed is delayed by 30 seconds
#
# Location of config file varies based on OS
#
def temp_check():
	INITIALSPEEDVAL = 200	# ensures fan speed gets set during initialization (e.g. change settings)
	argonregsupport = argonregister_checksupport(bus)

	fanconfig = load_fancpuconfig()
	fanhddconfig = load_fanhddconfig()

	prevspeed=INITIALSPEEDVAL
	while True:
		# Speed based on CPU Temp
		val = argonsysinfo_getcputemp()
		newspeed = get_fanspeed(val, fanconfig)
		# Speed based on HDD Temp
		val = argonsysinfo_getmaxhddtemp()
		tmpspeed = get_fanspeed(val, fanhddconfig)

		# Use faster fan speed
		if tmpspeed > newspeed:
			newspeed = tmpspeed

		if prevspeed == newspeed:
			time.sleep(30)
			continue
		elif newspeed < prevspeed and prevspeed != INITIALSPEEDVAL:
			# Pause 30s before speed reduction to prevent fluctuations
			time.sleep(30)
		prevspeed = newspeed
		try:
			if newspeed > 0:
				# Spin up to prevent issues on older units
				argonregister_setfanspeed(bus, 100, argonregsupport)
				# Set fan speed has sleep
			argonregister_setfanspeed(bus, newspeed, argonregsupport)
			time.sleep(30)
		except IOError:
			time.sleep(60)

#
# This function is the thread that updates OLED
#
def display_loop(readq):
	weekdaynamelist = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
	monthlist = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	oledscreenwidth = oled_getmaxX()

	fontwdSml = 6	# Maps to 6x8
	fontwdReg = 8	# Maps to 8x16
	stdleftoffset = 54

	temperature="C"
	tmpconfig=load_unitconfig(UNIT_CONFIGFILE)
	if "temperature" in tmpconfig:
		temperature = tmpconfig["temperature"]

	screensavermode = False
	screensaversec = 120
	screensaverctr = 0

	screenenabled = ["clock", "ip"]
	prevscreen = ""
	curscreen = ""
	screenid = 0
	screenjogtime = 0
	screenjogflag = 0	# start with screenid 0
	cpuusagelist = []
	curlist = []

	tmpconfig=load_oledconfig(OLED_CONFIGFILE)

	if "screensaver" in tmpconfig:
		screensaversec = tmpconfig["screensaver"]
	if "screenduration" in tmpconfig:
		screenjogtime = tmpconfig["screenduration"]
	if "screenlist" in tmpconfig:
		screenenabled = tmpconfig["screenlist"]

	if "enabled" in tmpconfig:
		if tmpconfig["enabled"] == "N":
			screenenabled = []

	while len(screenenabled) > 0:
		if len(curlist) == 0 and screenjogflag == 1:
			# Reset Screen Saver
			screensavermode = False
			screensaverctr = 0

			# Update screen info
			screenid = screenid + screenjogflag
			if screenid >= len(screenenabled):
				screenid = 0
		prevscreen = curscreen
		curscreen = screenenabled[screenid]

		if screenjogtime == 0:
			# Resets jogflag (if switched manually)
			screenjogflag = 0
		else:
			screenjogflag = 1

		needsUpdate = False
		if curscreen == "cpu":
			# CPU Usage
			if len(curlist) == 0:
				try:
					if len(cpuusagelist) == 0:
						cpuusagelist = argonsysinfo_listcpuusage()
					curlist = cpuusagelist
				except:
					curlist = []
			if len(curlist) > 0:
				oled_loadbg("bgcpu")

				# Display List
				yoffset = 0
				tmpmax = 4
				while tmpmax > 0 and len(curlist) > 0:
					curline = ""
					tmpitem = curlist.pop(0)
					curline = tmpitem["title"]+": "+str(tmpitem["value"])+"%"
					oled_writetext(curline, stdleftoffset, yoffset, fontwdSml)
					oled_drawfilledrectangle(stdleftoffset, yoffset+12, int((oledscreenwidth-stdleftoffset-4)*tmpitem["value"]/100), 2)
					tmpmax = tmpmax - 1
					yoffset = yoffset + 16

				needsUpdate = True
			else:
				# Next page due to error/no data
				screenjogflag = 1
		elif curscreen == "storage":
			# Storage Info
			if len(curlist) == 0:
				try:
					tmpobj = argonsysinfo_listhddusage()
					for curdev in tmpobj:
						curlist.append({"title": curdev, "value": argonsysinfo_kbstr(tmpobj[curdev]['total']), "usage": int(100*tmpobj[curdev]['used']/tmpobj[curdev]['total']) })
					#curlist = argonsysinfo_liststoragetotal()
				except:
					curlist = []
			if len(curlist) > 0:
				oled_loadbg("bgstorage")

				yoffset = 16
				tmpmax = 3
				while tmpmax > 0 and len(curlist) > 0:
					tmpitem = curlist.pop(0)
					# Right column first, safer to overwrite white space
					oled_writetextaligned(tmpitem["value"], 77, yoffset, oledscreenwidth-77, 2, fontwdSml)
					oled_writetextaligned(str(tmpitem["usage"])+"%", 50, yoffset, 74-50, 2, fontwdSml)
					tmpname = tmpitem["title"]
					if len(tmpname) > 8:
						tmpname = tmpname[0:8]
					oled_writetext(tmpname, 0, yoffset, fontwdSml)

					tmpmax = tmpmax - 1
					yoffset = yoffset + 16
				needsUpdate = True
			else:
				# Next page due to error/no data
				screenjogflag = 1

		elif curscreen == "raid":
			# Raid Info
			if len(curlist) == 0:
				try:
					tmpobj = argonsysinfo_listraid()
					curlist = tmpobj['raidlist']
				except:
					curlist = []
			if len(curlist) > 0:
				oled_loadbg("bgraid")
				tmpitem = curlist.pop(0)
				oled_writetextaligned(tmpitem["title"], 0, 0, stdleftoffset, 1, fontwdSml)
				oled_writetextaligned(tmpitem["value"], 0, 8, stdleftoffset, 1, fontwdSml)
				oled_writetextaligned(argonsysinfo_kbstr(tmpitem["info"]["size"]), 0, 56, stdleftoffset, 1, fontwdSml)

				if len(tmpitem['info']['state']) > 0:
					oled_writetext( tmpitem['info']['state'], stdleftoffset, 8, fontwdSml )

				if len(tmpitem['info']['rebuildstat']) > 0:
					oled_writetext("Rebuild:" + tmpitem['info']['rebuildstat'], stdleftoffset, 16, fontwdSml)

				# TODO: May need to use different method for each raid type (i.e. check raidlist['raidlist'][raidctr]['value'])
				#oled_writetext("Used:"+str(int(100*tmpitem["info"]["used"]/tmpitem["info"]["size"]))+"%", stdleftoffset, 24, fontwdSml)


				oled_writetext("Active:"+str(int(tmpitem["info"]["active"]))+"/"+str(int(tmpitem["info"]["devices"])), stdleftoffset, 32, fontwdSml)
				oled_writetext("Working:"+str(int(tmpitem["info"]["working"]))+"/"+str(int(tmpitem["info"]["devices"])), stdleftoffset, 40, fontwdSml)
				oled_writetext("Failed:"+str(int(tmpitem["info"]["failed"]))+"/"+str(int(tmpitem["info"]["devices"])), stdleftoffset, 48, fontwdSml)
				needsUpdate = True
			else:
				# Next page due to error/no data
				screenjogflag = 1

		elif curscreen == "ram":
			# RAM
			try:
				oled_loadbg("bgram")
				tmpraminfo = argonsysinfo_getram()
				oled_writetextaligned(tmpraminfo[0], stdleftoffset, 8, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				oled_writetextaligned("of", stdleftoffset, 24, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				oled_writetextaligned(tmpraminfo[1], stdleftoffset, 40, oledscreenwidth-stdleftoffset, 1, fontwdReg)
				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1
		elif curscreen == "temp":
			# Temp
			try:
				oled_loadbg("bgtemp")
				hddtempctr = 0
				maxcval = 0
				mincval = 200


				# Get min/max of hdd temp
				hddtempobj = argonsysinfo_gethddtemp()
				for curdev in hddtempobj:
					if hddtempobj[curdev] < mincval:
						mincval = hddtempobj[curdev]
					if hddtempobj[curdev] > maxcval:
						maxcval = hddtempobj[curdev]
					hddtempctr = hddtempctr + 1

				cpucval = argonsysinfo_getcputemp()
				if hddtempctr > 0:
					alltempobj = {"cpu": cpucval,"hdd min": mincval, "hdd max": maxcval}
					# Update max C val to CPU Temp if necessary
					if maxcval < cpucval:
						maxcval = cpucval

					displayrowht = 8
					displayrow = 8
					for curdev in alltempobj:
						if temperature == "C":
							# Celsius
							tmpstr = str(alltempobj[curdev])
							if len(tmpstr) > 4:
								tmpstr = tmpstr[0:4]
						else:
							# Fahrenheit
							tmpstr = str(32+9*(alltempobj[curdev])/5)
							if len(tmpstr) > 5:
								tmpstr = tmpstr[0:5]
						if len(curdev) <= 3:
							oled_writetext(curdev.upper()+": "+ tmpstr+ chr(167) +temperature, stdleftoffset, displayrow, fontwdSml)

						else:
							oled_writetext(curdev.upper()+":", stdleftoffset, displayrow, fontwdSml)

							oled_writetext("     "+ tmpstr+ chr(167) +temperature, stdleftoffset, displayrow+displayrowht, fontwdSml)
						displayrow = displayrow + displayrowht*2
				else:
					maxcval = cpucval
					if temperature == "C":
						# Celsius
						tmpstr = str(cpucval)
						if len(tmpstr) > 4:
							tmpstr = tmpstr[0:4]
					else:
						# Fahrenheit
						tmpstr = str(32+9*(cpucval)/5)
						if len(tmpstr) > 5:
							tmpstr = tmpstr[0:5]

					oled_writetextaligned(tmpstr+ chr(167) +temperature, stdleftoffset, 24, oledscreenwidth-stdleftoffset, 1, fontwdReg)

				# Temperature Bar: 40C is min, 80C is max
				maxht = 21
				barht = int(maxht*(maxcval-40)/40)
				if barht > maxht:
					barht = maxht
				elif barht < 1:
					barht = 1
				oled_drawfilledrectangle(24, 20+(maxht-barht), 3, barht, 2)


				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1
		elif curscreen == "ip":
			# IP Address
			try:
				oled_loadbg("bgip")
				oled_writetextaligned(argonsysinfo_getip(), 0, 8, oledscreenwidth, 1, fontwdReg)
				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1
		elif curscreen == "logo1v5":
			# Logo
			try:
				oled_loadbg("logo1v5")
				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1
		else:
			try:
				oled_loadbg("bgtime")
				# Date and Time HH:MM
				curtime = datetime.datetime.now()

				# Month/Day
				outstr = str(curtime.day).strip()
				if len(outstr) < 2:
					outstr = " "+outstr
				outstr = monthlist[curtime.month-1]+outstr
				oled_writetextaligned(outstr, stdleftoffset, 8, oledscreenwidth-stdleftoffset, 1, fontwdReg)

				# Day of Week
				oled_writetextaligned(weekdaynamelist[curtime.weekday()], stdleftoffset, 24, oledscreenwidth-stdleftoffset, 1, fontwdReg)

				# Time
				outstr = str(curtime.minute).strip()
				if len(outstr) < 2:
					outstr = "0"+outstr
				outstr = str(curtime.hour)+":"+outstr
				if len(outstr) < 5:
					outstr = "0"+outstr
				oled_writetextaligned(outstr, stdleftoffset, 40, oledscreenwidth-stdleftoffset, 1, fontwdReg)

				needsUpdate = True
			except:
				needsUpdate = False
				# Next page due to error/no data
				screenjogflag = 1

		if needsUpdate == True:
			if screensavermode == False:
				# Update screen if not screen saver mode
				oled_power(True)
				oled_flushimage(prevscreen != curscreen)
				oled_reset()

			timeoutcounter = 0
			while timeoutcounter<screenjogtime or screenjogtime == 0:
				qdata = ""
				if readq.empty() == False:
					qdata = readq.get()

				if qdata == "OLEDSWITCH":
					# Trigger screen switch
					screenjogflag = 1
					# Reset Screen Saver
					screensavermode = False
					screensaverctr = 0

					break
				elif qdata == "OLEDSTOP":
					# End OLED Thread
					display_defaultimg()
					return
				else:
					screensaverctr = screensaverctr + 1
					if screensaversec <= screensaverctr and screensavermode == False:
						screensavermode = True
						oled_fill(0)
						oled_reset()
						oled_power(False)

					if timeoutcounter == 0:
						# Use 1 sec sleep get CPU usage
						cpuusagelist = argonsysinfo_listcpuusage(1)
					else:
						time.sleep(1)

					timeoutcounter = timeoutcounter + 1
					if timeoutcounter >= 60 and screensavermode == False:
						# Refresh data every minute, unless screensaver got triggered
						screenjogflag = 0
						break
	display_defaultimg()

def display_defaultimg():
	# Load default image
	#oled_power(True)
	#oled_loadbg("bgdefault")
	#oled_flushimage()
	oled_fill(0)
	oled_reset()

if len(sys.argv) > 1:
	cmd = sys.argv[1].upper()
	if cmd == "SHUTDOWN":
		# Signal poweroff
		argonregister_signalpoweroff(bus)

	elif cmd == "FANOFF":
		# Turn off fan
		argonregister_setfanspeed(bus,0)

		if OLED_ENABLED == True:
			display_defaultimg()

	elif cmd == "SERVICE":
		# Starts the power button and temperature monitor threads
		try:
			ipcq = Queue()
			if len(sys.argv) > 2:
				cmd = sys.argv[2].upper()
			if cmd == "OLEDSWITCH":
				t1 = Thread(target = argonpowerbutton_monitorswitch, args =(ipcq, ))
			else:
				t1 = Thread(target = argonpowerbutton_monitor, args =(ipcq, ))

			t2 = Thread(target = temp_check)
			if OLED_ENABLED == True:
				t3 = Thread(target = display_loop, args =(ipcq, ))

			t1.start()
			t2.start()
			if OLED_ENABLED == True:
				t3.start()

			ipcq.join()
		except Exception:
			sys.exit(1)
