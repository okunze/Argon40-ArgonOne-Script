#!/usr/bin/python3

import json

import sys
import datetime
import math

import os
import time
import serial

from threading import Thread
from queue import Queue

sys.path.append("/etc/argon/")
import argonrtc


#################
# Common/Helpers
#################
#UPS_SERIALPORT="/dev/ttyUSB0"
UPS_SERIALPORT="/dev/ttyACM0"
UPS_LOGFILE="/dev/shm/upslog.txt"
UPS_CMDFILE="/dev/shm/upscmd.txt"

RTC_CONFIGFILE = "/etc/argonupsrtc.conf"


#############
# RTC
#############

def hexAsDec(hexval):
	return (hexval&0xF) + 10*((hexval>>4)&0xf)

def decAsHex(decval):
	return (decval%10) + (math.floor(decval/10)<<4)

# Returns RTC timestamp as datetime object
def getDatetimeObj(dataobj, datakey):
	try:
		datetimearray = dataobj[datakey].split(" ")
		if len(datetimearray)>1:
			datearray = datetimearray[0].split("/")
			timearray = datetimearray[1].split(":")
			if len(datearray) == 3 and len(timearray) > 1:
				year = int(datearray[2])
				month = int(datearray[0])
				caldate = int(datearray[1])
				hour = int(timearray[0])
				minute = int(timearray[1])
				second = 0
				if len(timearray) > 2:
					second = int(timearray[2])
				return datetime.datetime(year, month, caldate, hour, minute, second)+argonrtc.getLocaltimeOffset()
	except:
		pass

	return datetime.datetime(1999, 1, 1, 0, 0, 0)


def getRTCpoweronschedule():
	outobj = ups_sendcmd("7")
	return getDatetimeObj(outobj, "schedule")


def getRTCdatetime():
	outobj = ups_sendcmd("5")
	return getDatetimeObj(outobj, "time")


# set RTC time using datetime object (Local time)
def setRTCdatetime():
	# Set local time to UTC
	outobj = ups_sendcmd("3")
	return getDatetimeObj(outobj, "time")


# Set Next Alarm on RTC
def setNextAlarm(commandschedulelist, prevdatetime):
	nextcommandtime, weekday, caldate, hour, minute = argonrtc.getNextAlarm(commandschedulelist, prevdatetime)
	if prevdatetime >= nextcommandtime:
		return prevdatetime
	if weekday < 0 and caldate < 0 and hour < 0 and minute < 0:
		# No schedule
		# nextcommandtime is current time, which will be replaced/checked next iteration
		return nextcommandtime

	# Convert to RTC timezone
	alarmtime = nextcommandtime - argonrtc.getLocaltimeOffset()

	outobj = ups_sendcmd("6 "+alarmtime.strftime("%Y %m %d %H %M"))
	return getDatetimeObj(outobj, "schedule")


#############
# Status
#############

def ups_debuglog(typestr, logstr):
	try:
		UPS_DEBUGFILE="/dev/shm/upsdebuglog.txt"

		tmpstrpadding = "                      "

		with open(UPS_DEBUGFILE, "a") as txt_file:
			txt_file.write("["+datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"] "+typestr.upper()+" "+logstr.strip().replace("\n","\n"+tmpstrpadding)+"\n")
	except:
		pass

def ups_sendcmd(cmdstr):
	# status, version, time, schedule
	ups_debuglog("sendcmd", cmdstr)
	try:
		outstr = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

		with open(UPS_CMDFILE, "w") as txt_file:
			txt_file.write(datetime.datetime.now().strftime("%Y%m%d%H%M%S")+"\n"+cmdstr+"\n")
		time.sleep(3)
	except:
		pass

	outobj = ups_loadlogdata()
	try:
		ups_debuglog("sendcmd-response", json.dumps(outobj))
	except:
		pass

	return outobj

def ups_loadlogdata():
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

def ups_check(readq):
	CMDSTARTBYTE=0xfe
	CMDCONTROLBYTECOUNT=3
	CHECKSTATUSLOOPFREQ=50

	CMDsendrequest = [ 0xfe, 0, 0, 0xfe, 0xfe, 0, 0, 0xfe, 0, 0, 0]

	lastcmdtime=""
	loopCtr = CHECKSTATUSLOOPFREQ
	sendcmdid = -1

	ups_debuglog("serial", "Starting "+UPS_SERIALPORT)

	updatedesktopicon("Argon UPS", "Argon UPS", "/etc/argon/ups/loading_0.png")

	while True: # Outer loop to reconnect to device

		qdata = ""
		if readq.empty() == False:
			qdata = readq.get()

		try:
			ser = serial.Serial(UPS_SERIALPORT, 115200, timeout = 1)
			ser.close()
			ser.open()
		except Exception as mainerr:
			try:
				ups_debuglog("serial-mainerror", str(mainerr))
			except:
				ups_debuglog("serial-mainerror", "Error")
			# Give time before retry
			time.sleep(10)
			continue


		previconfile = ""
		statusstr = ""
		device_battery=0
		device_charging=0
		device_chargecurrent=-1
		device_version=-1
		device_rtctime= [-1, -1, -1, -1, -1, -1]
		device_powerontime= [-1, -1, -1, -1, -1]

		while True: # Command loop
			try:
				if sendcmdid < 0:
					cmddatastr = ""
					try:
						fp = open(UPS_CMDFILE, "r")
						cmdlog = fp.read()
						alllines = cmdlog.split("\n")
						if len(alllines) > 1:
							if lastcmdtime != alllines[0]:
								lastcmdtime=alllines[0]
								cmddatastr=alllines[1]
								tmpcmdarray = cmddatastr.split(" ")
								sendcmdid = int(tmpcmdarray[0])
								if sendcmdid == 3:
									# Get/rebuild time here to minimize delay/time gap
									newrtcdatetime = datetime.datetime.now() - argonrtc.getLocaltimeOffset()
									cmddatastr = ("3 "+newrtcdatetime.strftime("%Y %m %d %H %M %S"))
									tmpcmdarray = cmddatastr.split(" ")
									if len(tmpcmdarray) != 7:
										cmddatastr = ""
										sendcmdid = 0
								elif sendcmdid == 6:
									if len(tmpcmdarray) != 6:
										cmddatastr = ""
										sendcmdid = 0
					except OSError:
						cmddatastr = ""

					if cmddatastr == "":
						if loopCtr >= CHECKSTATUSLOOPFREQ:
							# Check Battery Status
							sendcmdid = 0
							loopCtr = 0
						else:
							loopCtr = loopCtr + 1
							if loopCtr == 2:
								sendcmdid = 5	# Get RTC Time
							elif loopCtr == 3:
								sendcmdid = 7	# Get Power on Time
							elif loopCtr == 4:
								sendcmdid = 4	# Get Version
							elif loopCtr == 5:
								sendcmdid = 2	# Get Charge Current
							elif (loopCtr&1) == 0:
								sendcmdid = 0	# Check Battery Status

				if sendcmdid >= 0:
					sendSize = 0
					cmdSize = 0
					if len(cmddatastr) > 0:
						# set RTC Time (3, 6 bytes)
						# set Power of Time (6, 5 bytes)
						tmpcmdarray = cmddatastr.split(" ")
						CMDsendrequest[1] = len(tmpcmdarray) - 1 # Length
						CMDsendrequest[2] = sendcmdid

						cmdSize = CMDsendrequest[1] + 4

						# Copy payload
						tmpdataidx = cmdSize - 1 # Start at end
						while tmpdataidx > 3:
							tmpdataidx = tmpdataidx - 1
							if tmpdataidx == 3 and (sendcmdid == 3 or sendcmdid == 6):
								tmpval = int(tmpcmdarray[tmpdataidx-2])
								if tmpval >= 2000:
									tmpval = tmpval - 2000
								else:
									tmpval = 0
								CMDsendrequest[tmpdataidx] = decAsHex(tmpval)
							else:
								CMDsendrequest[tmpdataidx] = decAsHex(int(tmpcmdarray[tmpdataidx-2]))

						datasum = 0
						tmpdataidx = cmdSize - 1
						while tmpdataidx > 0:
							tmpdataidx = tmpdataidx - 1
							datasum = (datasum+CMDsendrequest[tmpdataidx]) & 0xff

						CMDsendrequest[cmdSize-1] = datasum
						sendSize = ser.write(serial.to_bytes(CMDsendrequest[0:cmdSize]))

						ups_debuglog("serial-out-cmd", serial.to_bytes(CMDsendrequest[0:cmdSize]).hex(" "))

					else:
						# Default Get/Read command
						CMDsendrequest[1] = 0 # Length
						CMDsendrequest[2] = sendcmdid
						CMDsendrequest[3] = (sendcmdid+CMDsendrequest[0]) & 0xff
						sendSize = ser.write(serial.to_bytes(CMDsendrequest[0:4]))
						cmdSize = CMDsendrequest[1] + 4

						#ups_debuglog("serial-out-def", serial.to_bytes(CMDsendrequest[0:4]).hex(" "))

					if cmdSize > 0:
						sendcmdid=-1
						if sendSize == cmdSize:
							# Give time to respond
							time.sleep(1)
						else:
							break

				# read incoming data
				readOut = ser.read()

				if len(readOut) == 0:
					continue

				readdatalen = 1
				while True:
					tmpreadlen = ser.inWaiting()		# Check remaining byte size
					if tmpreadlen < 1:
						break
					readOut += ser.read(tmpreadlen)
					readdatalen += tmpreadlen

				readintarray = [tmpint for tmpint in readOut]

				if len(cmddatastr) > 0:
					ups_debuglog("serial-in     ", readOut.hex(" "))
				cmddatastr = ""
				# Parse command stream
				tmpidx = 0
				while tmpidx < readdatalen:
					if readintarray[tmpidx] == CMDSTARTBYTE and tmpidx + CMDCONTROLBYTECOUNT < readdatalen:
						# Cmd format: Min 4 bytes
						# tmpidx tmpidx+1   tmpidx+2
						# 0xfe (byte count) (cmd ID) (payload; byte count) (datasum)

						tmpdatalen = readintarray[tmpidx+1]
						tmpcmd = readintarray[tmpidx+2]
						if tmpidx + CMDCONTROLBYTECOUNT + tmpdatalen < readdatalen:
							# Validate datasum
							datasum = 0
							tmpdataidx = tmpidx + tmpdatalen + CMDCONTROLBYTECOUNT
							while tmpdataidx > tmpidx:
								tmpdataidx = tmpdataidx - 1
								datasum = (datasum+readintarray[tmpdataidx]) & 0xff
							if datasum != readintarray[tmpidx + tmpdatalen + CMDCONTROLBYTECOUNT]:
								# Invalid sum
								pass
							else:
								needsupdate=False
								if tmpcmd == 0:
									# Check State
									if tmpdatalen >= 2:
										needsupdate=True
										tmp_battery = readintarray[tmpidx+CMDCONTROLBYTECOUNT]
										if tmp_battery>100:
											tmp_battery=100
										elif tmp_battery<1:
											tmp_battery=0
										tmp_charging = readintarray[tmpidx+CMDCONTROLBYTECOUNT+1]
										#ups_debuglog("battery-data", str(tmp_charging)+" "+str(tmp_battery))

										if tmp_charging != device_charging or tmp_battery!=device_battery:
											device_battery=tmp_battery
											device_charging=tmp_charging
											tmpiconfile = "/etc/argon/ups/"

											icontitle = "Argon UPS"
											if device_charging == 0:
												if device_battery==100:
													statusstr = "Charged"
													#tmpiconfile = tmpiconfile+"battery_plug"
												else:
													#icontitle = str(device_battery)+"%"+" Full"
													statusstr = "Charging"
													#tmpiconfile = tmpiconfile+"battery_charging"
												tmpiconfile = tmpiconfile+"charge_"+str(device_battery)
											else:
												#icontitle = str(device_battery)+"%"+" Left"
												statusstr = "Battery"
												tmp_battery = round(tmp_battery/20)
												if tmp_battery > 4:
													tmp_battery = 4
												#tmpiconfile = tmpiconfile+"battery_"+str(tmp_battery)
												tmpiconfile = tmpiconfile+"discharge_"+str(device_battery)
											tmpiconfile = tmpiconfile + ".png"

											statusstr = statusstr + " " + str(device_battery)+"%"

											#ups_debuglog("battery-info", statusstr)

											# Add/update desktop icons too; add check to minimize write
											if previconfile != tmpiconfile:
												updatedesktopicon(icontitle, statusstr, tmpiconfile)
											previconfile = tmpiconfile

								elif tmpcmd == 2:
									# Charge Current
									if tmpdatalen >= 2:
										device_chargecurrent = ((readintarray[tmpidx+CMDCONTROLBYTECOUNT])<<8) | readintarray[tmpidx+CMDCONTROLBYTECOUNT+1]
								elif tmpcmd == 4:
									# Version
									if tmpdatalen >= 1:
										needsupdate=True
										device_version = readintarray[tmpidx+CMDCONTROLBYTECOUNT]
								elif tmpcmd == 5:
									# RTC Time
									if tmpdatalen >= 6:
										needsupdate=True
										tmpdataidx = 0
										while tmpdataidx < 6:
											device_rtctime[tmpdataidx] = hexAsDec(readintarray[tmpidx+CMDCONTROLBYTECOUNT+tmpdataidx])
											tmpdataidx = tmpdataidx + 1
								elif tmpcmd == 7:
									# Power On Time
									if tmpdatalen >= 5:
										needsupdate=True
										tmpdataidx = 0
										while tmpdataidx < 5:
											device_powerontime[tmpdataidx] = hexAsDec(readintarray[tmpidx+CMDCONTROLBYTECOUNT+tmpdataidx])
											tmpdataidx = tmpdataidx + 1
								elif tmpcmd == 8:
									# Send Acknowledge
									sendcmdid = tmpcmd
								elif tmpcmd == 3:
									# New RTC Time set
									sendcmdid = 5
								elif tmpcmd == 6:
									# New Power On Time set
									sendcmdid = 7

								if needsupdate==True:
									# Log File
									otherstr = ""
									if device_version >= 0:
										otherstr = otherstr + "  Version:"+str(device_version)+"\n"
									if device_rtctime[0] >= 0:
										otherstr = otherstr + "  Time:"+str(device_rtctime[1])+"/"+str(device_rtctime[2])+"/"+str(device_rtctime[0]+2000)+" "+str(device_rtctime[3])+":"+str(device_rtctime[4])+":"+str(device_rtctime[5])+"\n"
									if device_powerontime[1] > 0:
										otherstr = otherstr + "  Schedule:"+str(device_powerontime[1])+"/"+str(device_powerontime[2])+"/"+str(device_powerontime[0]+2000)+" "+str(device_powerontime[3])+":"+str(device_powerontime[4])+"\n"
									with open(UPS_LOGFILE, "w") as txt_file:
										txt_file.write("Status as of: "+time.asctime(time.localtime(time.time()))+"\n  Power:"+statusstr+"\n"+otherstr)
									#ups_debuglog("status-update", "\n  Power:"+statusstr+"\n"+otherstr)
								# Point to datasum, so next loop iteration will be correct
								tmpidx = tmpidx + tmpdatalen + CMDCONTROLBYTECOUNT
					tmpidx = tmpidx + 1
			except Exception as e:
				try:
					ups_debuglog("serial-error", str(e))
				except:
					ups_debuglog("serial-error", "Error")
				break

def updatedesktopicon(icontitle, statusstr, tmpiconfile):
	try:
		tmp = os.popen("find /home -maxdepth 1 -type d").read()
		alllines = tmp.split("\n")
		for curfolder in alllines:
			if curfolder == "/home" or curfolder == "":
				continue
			#ups_debuglog("desktop-update-path", curfolder)
			#ups_debuglog("desktop-update-text", statusstr)
			#ups_debuglog("desktop-update-icon", tmpiconfile)
			with open(curfolder+"/Desktop/argonone-ups.desktop", "w") as txt_file:
				txt_file.write("[Desktop Entry]\nName="+icontitle+"\nComment="+statusstr+"\nIcon="+tmpiconfile+"\nExec=lxterminal --working-directory="+curfolder+"/ -t \"Argon UPS\" -e \"/etc/argon/argonone-upsconfig.sh argonupsrtc\"\nType=Application\nEncoding=UTF-8\nTerminal=false\nCategories=None;\n")
	except Exception as desktope:
		#pass
		try:
			ups_debuglog("desktop-update-error", str(desktope))
		except:
			ups_debuglog("desktop-update-error", "Error")


def allowshutdown():
	uptime = 0.0
	errorflag = False
	try:
		cpuctr = 0
		tempfp = open("/proc/uptime", "r")
		alllines = tempfp.readlines()
		for temp in alllines:
			infolist = temp.split(" ")
			if len(infolist) > 1:
				uptime = float(infolist[0])
				break
		tempfp.close()
	except IOError:
		errorflag = True
	# 120=2mins minimum up time
	return uptime > 120


######
if len(sys.argv) > 1:
	cmd = sys.argv[1].upper()
	if cmd == "GETBATTERY":
		#outobj = ups_sendcmd("0")
		outobj = ups_loadlogdata()
		try:
			print(outobj["power"])
		except:
			print("Error retrieving battery status")

	elif cmd == "GETRTCSCHEDULE":
		tmptime = getRTCpoweronschedule()
		if tmptime.year > 1999:
			print("Alarm Setting:", tmptime)
		else:
			print("Alarm Setting: None")

	elif cmd == "GETRTCTIME":
		tmptime = getRTCdatetime()
		if tmptime.year > 1999:
			print("RTC Time:", tmptime)
		else:
			print("Error reading RTC Time")

	elif cmd == "UPDATERTCTIME":
		tmptime = setRTCdatetime()
		if tmptime.year > 1999:
			print("RTC Time:", tmptime)
		else:
			print("Error reading RTC Time")

	elif cmd == "GETSCHEDULELIST":
		argonrtc.describeConfigList(RTC_CONFIGFILE)

	elif cmd == "SHOWSCHEDULE":
		if len(sys.argv) > 2:
			if sys.argv[2].isdigit():
				# Display starts at 2, maps to 0-based index
				configidx = int(sys.argv[2])-2
				configlist = argonrtc.loadConfigList(RTC_CONFIGFILE)
				if len(configlist) > configidx:
					print ("  ",argonrtc.describeConfigListEntry(configlist[configidx]))
				else:
					print("   Invalid Schedule")

	elif cmd == "REMOVESCHEDULE":
		if len(sys.argv) > 2:
			if sys.argv[2].isdigit():
				# Display starts at 2, maps to 0-based index
				configidx = int(sys.argv[2])-2
				argonrtc.removeConfigEntry(RTC_CONFIGFILE, configidx)

	elif cmd == "SERVICE":
		ipcq = Queue()

		tmprtctime = getRTCdatetime()
		if tmprtctime.year >= 2000:
			argonrtc.updateSystemTime(tmprtctime)
		commandschedulelist = argonrtc.formCommandScheduleList(argonrtc.loadConfigList(RTC_CONFIGFILE))
		nextrtcalarmtime = setNextAlarm(commandschedulelist, datetime.datetime.now())

		t1 = Thread(target = ups_check, args =(ipcq, ))
		t1.start()

		serviceloop = True
		while serviceloop==True:
			tmpcurrenttime = datetime.datetime.now()
			if nextrtcalarmtime <= tmpcurrenttime:
				# Update RTC Alarm to next iteration
				nextrtcalarmtime = setNextAlarm(commandschedulelist, nextrtcalarmtime)
			if len(argonrtc.getCommandForTime(commandschedulelist, tmpcurrenttime, "off")) > 0:
				# Shutdown detected, issue command then end service loop
				if allowshutdown():
					os.system("shutdown now -h")
					serviceloop = False
					# Don't break to sleep while command executes (prevents service to restart)

			time.sleep(60)

		ipcq.join()


elif False:
	print("System Time: ", datetime.datetime.now())
	print("RTC    Time: ", getRTCdatetime())
