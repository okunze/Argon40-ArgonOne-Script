#!/usr/bin/python3

#
# This script monitor battery via ic2 and keyboard events.
#
# Additional comments are found in each function below
#
#

import sys
import os
import time

from threading import Thread
from queue import Queue

sys.path.append("/etc/argon/")
from argonregister import *
from argonpowerbutton import *

# Initialize I2C Bus
bus = argonregister_initializebusobj()

# Constants
ADDR_BATTERY = 0x64

UPS_LOGFILE="/dev/shm/upslog.txt"


###################
# Utilty Functions
###################

# Debug Logger
def debuglog(typestr, logstr):
	try:
		DEBUGFILE="/dev/shm/argononeupdebuglog.txt"
		tmpstrpadding = "                      "

		with open(DEBUGFILE, "a") as txt_file:
			txt_file.write("["+time.asctime(time.localtime(time.time()))+"] "+typestr.upper()+" "+logstr.strip().replace("\n","\n"+tmpstrpadding)+"\n")
	except:
		pass


# System Notifcation
def notifymessage(message, iscritical):
	if not isinstance(message, str) or len(message.strip()) == 0:
		return

	wftype="notify"
	if iscritical:
		wftype="critical"
	os.system("export SUDO_UID=1000; wfpanelctl "+wftype+" \""+message+"\"")
	os.system("export DISPLAY=:0.0; lxpanelctl notify \""+message+"\"")


#############
# Battery
#############
REG_CONTROL = 0x08
REG_SOCALERT = 0x0b
REG_PROFILE = 0x10
REG_ICSTATE = 0xA7



def battery_restart():
	# Set to active mode
	try:
		maxretry = 3
		while maxretry > 0:
			maxretry = maxretry - 1

			# Restart
			bus.write_byte_data(ADDR_BATTERY, REG_CONTROL, 0x30)
			time.sleep(0.5)
			# Activate
			bus.write_byte_data(ADDR_BATTERY, REG_CONTROL, 0x00)
			time.sleep(0.5)

			# Wait for Ready Status
			maxwaitsecs = 5
			while maxwaitsecs > 0:
				tmpval = bus.read_byte_data(ADDR_BATTERY, REG_ICSTATE)
				if (tmpval&0x0C) != 0:
					debuglog("battery-activate", "Activated Successfully")
					return 0
				time.sleep(1)
				maxwaitsecs = maxwaitsecs - 1


		debuglog("battery-activate", "Failed to activate")
		return 2
	except Exception as e:
		try:
			debuglog("battery-activateerror", str(e))
		except:
			debuglog("battery-activateerror", "Activation Failed")
	return 1


def battery_getstatus(restartifnotactive):
	try:
		tmpval = bus.read_byte_data(ADDR_BATTERY, REG_CONTROL)
		if tmpval != 0:
			if restartifnotactive == True:
				tmpval = battery_restart()

			if tmpval != 0:
				debuglog("battery-status", "Inactive "+str(tmpval))
				return 2

		tmpval = bus.read_byte_data(ADDR_BATTERY, REG_SOCALERT)
		if (tmpval&0x80) == 0:
			debuglog("battery-status", "Profile not ready "+str(tmpval))
			return 3

		# OK
		#debuglog("battery-status", "OK")
		return 0
	except Exception as e:
		try:
			debuglog("battery-status-error", str(e))
		except:
			debuglog("battery-status-error", "Battery Status Failed")

	return 1

def battery_checkupdateprofile():
	try:
		REG_GPIOCONFIG = 0x0A

		PROFILE_DATALIST = [0x32,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xA8,0xAA,0xBE,0xC6,0xB8,0xAE,0xC2,0x98,0x82,0xFF,0xFF,0xCA,0x98,0x75,0x63,0x55,0x4E,0x4C,0x49,0x98,0x88,0xDC,0x34,0xDB,0xD3,0xD4,0xD3,0xD0,0xCE,0xCB,0xBB,0xE7,0xA2,0xC2,0xC4,0xAE,0x96,0x89,0x80,0x74,0x67,0x63,0x71,0x8E,0x9F,0x85,0x6F,0x3B,0x20,0x00,0xAB,0x10,0xFF,0xB0,0x73,0x00,0x00,0x00,0x64,0x08,0xD3,0x77,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xFA]

		PROFILE_LEN = len(PROFILE_DATALIST)

		# Try to compare profile if battery is active
		tmpidx = 0

		tmpval = battery_getstatus(True)
		if tmpval == 0:
			# Status OK, check profile
			tmpidx = 0
			while tmpidx < PROFILE_LEN:
				tmpval = bus.read_byte_data(ADDR_BATTERY, REG_PROFILE+tmpidx)
				if tmpval != PROFILE_DATALIST[tmpidx]:
					debuglog("battery-profile-error", "Mismatch")
					break
				tmpidx = tmpidx + 1

			if tmpidx == PROFILE_LEN:
				# Matched
				return 0
		else:
			debuglog("battery-profile", "Status Error "+str(tmpval)+", will attempt to update")

		# needs update
		debuglog("battery-profile", "Updating...")

		# Device Sleep state

		# Restart
		bus.write_byte_data(ADDR_BATTERY, REG_CONTROL, 0x30)
		time.sleep(0.5)
		# Sleep
		bus.write_byte_data(ADDR_BATTERY, REG_CONTROL, 0xF0)
		time.sleep(0.5)

		# Write Profile
		tmpidx = 0
		while tmpidx < PROFILE_LEN:
			bus.write_byte_data(ADDR_BATTERY, REG_PROFILE+tmpidx, PROFILE_DATALIST[tmpidx])
			tmpidx = tmpidx + 1

		debuglog("battery-profile", "Profile Updated,Restarting...")

		# Set Update Flag
		bus.write_byte_data(ADDR_BATTERY, REG_SOCALERT, 0x80)
		time.sleep(0.5)

		# Close Interrupts
		bus.write_byte_data(ADDR_BATTERY, REG_GPIOCONFIG, 0)
		time.sleep(0.5)

		# Restart Battery
		tmpval = battery_restart()
		if tmpval == 0:
			debuglog("battery-profile", "Update Completed")
			return 0

		debuglog("battery-profile", "Unable to restart")
		return 3
	except Exception as e:
		try:
			debuglog("battery-profile-error", str(e))
		except:
			debuglog("battery-profile-error", "Battery Profile Check/Update Failed")

	return 1



def battery_getpercent():
	# State of Charge (SOC)
	try:
		SOC_HIGH_REG = 0x04

		socpercent = bus.read_byte_data(ADDR_BATTERY, SOC_HIGH_REG)
		if socpercent > 100:
			return 100
		elif socpercent > 0:
			return socpercent

		# Support Fraction percent
		#SOC_LOW_REG = 0x05
		#soc_low = bus.read_byte_data(ADDR_BATTERY, SOC_LOW_REG)
		#socpercentfloat = socpercent + (soc_low / 256.0)
		#if socpercentfloat > 100.0:
		#	return 100.0
		#elif socpercentfloat > 0.0:
		#	return socpercentfloat

	except Exception as e:
		try:
			debuglog("battery-percenterror", str(e))
		except:
			debuglog("battery-percenterror", "Read Battery Failed")

	return -1


def battery_isplugged():
	# State of Charge (SOC)
	try:
		CURRENT_HIGH_REG = 0x0E

		current_high = bus.read_byte_data(ADDR_BATTERY, CURRENT_HIGH_REG)

		if (current_high & 0x80) > 0:
			return 1

		#CURRENT_LOW_REG = 0x0F
		#R_SENSE = 10.0
		#current_low = bus.read_byte_data(ADDR_BATTERY, CURRENT_LOW_REG)
		#raw_current = int.from_bytes([current_high, current_low], byteorder='big', signed=True)
		#current = (52.4 * raw_current) / (32768 * R_SENSE)

		return 0
	except Exception as e:
		try:
			debuglog("battery-chargingerror", str(e))
		except:
			debuglog("battery-chargingerror", "Read Charging Failed")

	return -1

def battery_loadlogdata():
	# status, version, time, schedule
	outobj = {}
	try:
		fp = open(UPS_LOGFILE, "r")
		logdata = fp.read()
		alllines = logdata.split("\n")
		ctr = 0
		while ctr < len(alllines):
			tmpval = alllines[ctr].strip()
			curinfo = tmpval.split(":")
			if len(curinfo) > 1:
				tmpattrib = curinfo[0].lower().split(" ")
				# The rest are assumed to be value
				outobj[tmpattrib[0]] = tmpval[(len(curinfo[0])+1):].strip()
			ctr = ctr + 1
	except OSError:
		pass

	return outobj

def battery_check(readq):
	CMDSTARTBYTE=0xfe
	CMDCONTROLBYTECOUNT=3
	CHECKSTATUSLOOPFREQ=50

	CMDsendrequest = [ 0xfe, 0, 0, 0xfe, 0xfe, 0, 0, 0xfe, 0, 0, 0]

	lastcmdtime=""
	loopCtr = CHECKSTATUSLOOPFREQ
	sendcmdid = -1

	debuglog("battery", "Starting")

	updatedesktopicon("Argon ONE UP", "/etc/argon/argon40.png")

	maxretry = 5
	while maxretry > 0:
		try:
			if battery_checkupdateprofile() == 0:
				break
		except Exception as mainerr:
			try:
				debuglog("battery-mainerror", str(mainerr))
			except:
				debuglog("battery-mainerror", "Error")
		# Give time before retry
		time.sleep(10)
		maxretry = maxretry - 1

	while maxretry > 0: # Outer loop; maxretry never decrements so infinite
		qdata = ""
		if readq.empty() == False:
			qdata = readq.get()

		if battery_getstatus(True) != 0:
			# Give time before retry
			time.sleep(3)
			continue

		prevnotifymsg = ""
		previconfile = ""
		statusstr = ""

		shutdowntriggered=False
		needsupdate=False
		device_battery=0
		device_charging=0

		while True: # Command loop
			try:
				if sendcmdid < 0:
					cmddatastr = ""

					if cmddatastr == "":
						if loopCtr >= CHECKSTATUSLOOPFREQ:
							# Check Battery Status
							sendcmdid = 0
							loopCtr = 0
						else:
							loopCtr = loopCtr + 1
							if (loopCtr&1) == 0:
								sendcmdid = 0	# Check Battery Status

				if sendcmdid == 0:
					tmp_battery = battery_getpercent()
					tmp_charging = battery_isplugged()

					if tmp_charging < 0 or tmp_battery < 0:
						# communication error, retain old value
						tmp_charging = device_charging
						tmp_battery = device_battery

					if tmp_charging != device_charging or tmp_battery!=device_battery:
						device_battery=tmp_battery
						device_charging=tmp_charging
						tmpiconfile = "/etc/argon/ups/"
						needsupdate=True
						curnotifymsg = ""
						curnotifycritical = False

						if device_battery>99:
							# Prevents switching issue
							statusstr = "Charged"
							curnotifymsg = statusstr
							tmpiconfile = tmpiconfile+"charge_"+str(device_battery)
						elif device_charging == 0:
							statusstr = "Charging"
							curnotifymsg = statusstr
							tmpiconfile = tmpiconfile+"charge_"+str(device_battery)
						else:
							statusstr = "Battery"
							tmpiconfile = tmpiconfile+"discharge_"+str(device_battery)

							if device_battery > 50:
								curnotifymsg="Battery Mode"
							elif device_battery > 20:
								curnotifymsg="50%% Battery"
							elif device_battery > 10:
								curnotifymsg="20%% Battery"
							elif device_battery > 5:
								#curnotifymsg="Low Battery"
								curnotifymsg="Low Battery: The device may power off automatically soon."
								curnotifycritical=True
							else:
								curnotifymsg="CRITICAL BATTERY: Shutting Down in 1 minute"
								curnotifycritical=True

						tmpiconfile = tmpiconfile + ".png"
						statusstr = statusstr + " " + str(device_battery)+"%"

						# Add/update desktop icons too; add check to minimize write
						if previconfile != tmpiconfile:
							updatedesktopicon(statusstr, tmpiconfile)
						previconfile = tmpiconfile

						# Send notification if necessary
						if prevnotifymsg != curnotifymsg:
							notifymessage(curnotifymsg, curnotifycritical)
							if shutdowntriggered==False and device_battery <= 5 and device_charging != 0:
								shutdowntriggered=True
								os.system("shutdown +1 """+curnotifymsg+".""")
								debuglog("battery-shutdown", "Shutdown in 1 minute")

						if shutdowntriggered==True and (device_charging == 0 or device_battery>=10):
							shutdowntriggered=False
							os.system("shutdown -c ""Charging, shutdown cancelled.""")
							debuglog("battery-shutdown", "Abort")

						prevnotifymsg = curnotifymsg


					sendcmdid=-1

				if needsupdate==True:
					# Log File
					otherstr = ""
					with open(UPS_LOGFILE, "w") as txt_file:
						txt_file.write("Status as of: "+time.asctime(time.localtime(time.time()))+"\n  Power:"+statusstr+"\n"+otherstr)

					needsupdate=False

			except Exception as e:
				try:
					debuglog("battery-error", str(e))
				except:
					debuglog("battery-error", "Error")
				break
		time.sleep(3)

def updatedesktopicon(statusstr, tmpiconfile):
	try:
		icontitle = "Argon ONE UP"
		tmp = os.popen("find /home -maxdepth 1 -type d").read()
		alllines = tmp.split("\n")
		for curfolder in alllines:
			if curfolder == "/home" or curfolder == "":
				continue
			#debuglog("desktop-update-path", curfolder)
			#debuglog("desktop-update-text", statusstr)
			#debuglog("desktop-update-icon", tmpiconfile)
			with open(curfolder+"/Desktop/argononeup.desktop", "w") as txt_file:
				txt_file.write("[Desktop Entry]\nName="+icontitle+"\nComment="+statusstr+"\nIcon="+tmpiconfile+"\nExec=lxterminal --working-directory="+curfolder+"/ -t \"Argon ONE UP\" -e \"/etc/argon/argon-config\"\nType=Application\nEncoding=UTF-8\nTerminal=false\nCategories=None;\n")
	except Exception as desktope:
		#pass
		try:
			debuglog("desktop-update-error", str(desktope))
		except:
			debuglog("desktop-update-error", "Error")


if len(sys.argv) > 1:
	cmd = sys.argv[1].upper()
	if cmd == "GETBATTERY":
		outobj = battery_loadlogdata()
		try:
			print(outobj["power"])
		except:
			print("Error retrieving battery status")
	elif cmd == "RESETBATTERY":
		battery_checkupdateprofile()

	elif cmd == "SERVICE":
		# Starts sudo level services
		try:
			ipcq = Queue()
			if len(sys.argv) > 2:
				cmd = sys.argv[2].upper()
			t1 = Thread(target = battery_check, args =(ipcq, ))
			t2 = Thread(target = argonpowerbutton_monitorlid, args =(ipcq, ))

			t1.start()
			t2.start()

			ipcq.join()
		except Exception:
			sys.exit(1)
