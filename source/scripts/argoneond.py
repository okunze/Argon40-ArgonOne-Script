#!/usr/bin/python3


import sys
import datetime
import math

import os
import time

sys.path.append("/etc/argon/")
from argonregister import argonregister_initializebusobj
import argonrtc


# Initialize I2C Bus
bus = argonregister_initializebusobj()

ADDR_RTC=0x51

#################
# Common/Helpers
#################

RTC_CONFIGFILE = "/etc/argoneonrtc.conf"

RTC_ALARM_BIT = 0x8
RTC_TIMER_BIT = 0x4

# PCF8563 number system Binary Coded Decimal (BCD)

# BCD to Decimal
def numBCDtoDEC(val):
	return (val & 0xf)+(((val >> 4) & 0xf)*10)

# Decimal to BCD
def numDECtoBCD(val):
	return (math.floor(val/10)<<4) + (val % 10)

# Check if Event Bit is raised
def hasRTCEventFlag(flagbit):
	if bus is None:
		return False
	bus.write_byte(ADDR_RTC,1)
	out = bus.read_byte_data(ADDR_RTC, 1)
	return (out & flagbit) != 0

# Clear Event Bit if raised
def clearRTCEventFlag(flagbit):
	if bus is None:
		return False

	out = bus.read_byte_data(ADDR_RTC, 1)
	if (out & flagbit) != 0:
		# Unset only if fired
		bus.write_byte_data(ADDR_RTC, 1, out&(0xff-flagbit))
		return True
	return False

# Enable Event Flag
def setRTCEventFlag(flagbit, enabled):
	if bus is None:
		return

	# 0x10 = TI_TP flag, 0 by default
	ti_tp_flag = 0x10
	# flagbit=0x4 for timer flag, 0x1 for enable timer flag
	# flagbit=0x8 for alarm flag, 0x2 for enable alarm flag
	enableflagbit = flagbit>>2
	disableflagbit = 0
	if enabled == False:
		disableflagbit = enableflagbit
		enableflagbit = 0

	out = bus.read_byte_data(ADDR_RTC, 1)
	bus.write_byte_data(ADDR_RTC, 1, (out&(0xff-flagbit-disableflagbit - ti_tp_flag))|enableflagbit)


#########
# Describe Methods
#########

# Describe Timer Setting
def describeTimer(showsetting):
	if bus is None:
		return "Error"

	out = bus.read_byte_data(ADDR_RTC, 14)
	tmp = out & 3
	if tmp == 3:
		outstr = " Minute(s)"
	elif tmp == 2:
		outstr = " Second(s)"
	elif tmp == 1:
		outstr = "/64th Second"
	elif tmp == 0:
		outstr = "/4096th Second"

	if (out & 0x80) != 0:
		out = bus.read_byte_data(ADDR_RTC, 15)
		return "Every "+(numBCDtoDEC(out)+1)+outstr
	elif showsetting == True:
		return "Disabled (Interval every 1"+outstr+")"
	# Setting might matter to save resources
	return "None"


# Describe Alarm Setting
def describeAlarm():
	if bus is None:
		return "Error"

	minute = -1
	hour = -1
	caldate = -1
	weekday = -1

	out = bus.read_byte_data(ADDR_RTC, 9)
	if (out & 0x80) == 0:
		minute = numBCDtoDEC(out & 0x7f)

	out = bus.read_byte_data(ADDR_RTC, 10)
	if (out & 0x80) == 0:
		hour = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte_data(ADDR_RTC, 11)
	if (out & 0x80) == 0:
		caldate = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte_data(ADDR_RTC, 12)
	if (out & 0x80) == 0:
		weekday = numBCDtoDEC(out & 0x7)

	if weekday < 0 and caldate < 0 and hour < 0 and minute < 0:
		return "None"

	# Convert from UTC
	utcschedule = argonrtc.describeSchedule([-1], [weekday], [caldate], [hour], [minute])
	weekday, caldate, hour, minute = argonrtc.convertAlarmTimezone(weekday, caldate, hour, minute, False)

	return argonrtc.describeSchedule([-1], [weekday], [caldate], [hour], [minute]) + " Local (RTC Schedule: "+utcschedule+" UTC)"


# Describe Control Flags
def describeControlRegisters():
	if bus is None:
		print("Error")
		return

	out = bus.read_byte_data(ADDR_RTC, 1)

	print("\n***************")
	print("Control Status 2")
	print("\tTI_TP Flag:", ((out & 0x10) != 0))
	print("\tAlarm Flag:", ((out & RTC_ALARM_BIT) != 0),"( Enabled =", (out & (RTC_ALARM_BIT>>2)) != 0, ")")
	print("\tTimer Flag:", ((out & RTC_TIMER_BIT) != 0),"( Enabled =", (out & (RTC_TIMER_BIT>>2)) != 0, ")")

	print("Alarm Setting:")
	print("\t"+describeAlarm())

	print("Timer Setting:")
	print("\t"+describeTimer(True))

	print("***************\n")


#########
# Alarm
#########

# Check if RTC Alarm Flag is ON
def hasRTCAlarmFlag():
	return hasRTCEventFlag(RTC_ALARM_BIT)

# Clear RTC Alarm Flag
def clearRTCAlarmFlag():
	return clearRTCEventFlag(RTC_ALARM_BIT)

# Enables RTC Alarm Register
def enableAlarm(registeraddr, value, mask):
	if bus is None:
		return

	# 0x00 is Enabled
	bus.write_byte_data(ADDR_RTC, registeraddr, (numDECtoBCD(value)&mask))

# Disables RTC Alarm Register
def disableAlarm(registeraddr):
	if bus is None:
		return

	# 0x80 is disabled
	bus.write_byte_data(ADDR_RTC, registeraddr, 0x80)

# Removes all alarm settings
def removeRTCAlarm():
	setRTCEventFlag(RTC_ALARM_BIT, False)

	disableAlarm(9)
	disableAlarm(10)
	disableAlarm(11)
	disableAlarm(12)

# Set RTC Alarm (Negative values ignored)
def setRTCAlarm(enableflag, weekday, caldate, hour, minute):

	weekday, caldate, hour, minute = argonrtc.getRTCAlarm(weekday, caldate, hour, minute)
	if caldate < 1 and weekday < 0 and hour < 0 and minute < 0:
		return -1

	clearRTCAlarmFlag()
	setRTCEventFlag(RTC_ALARM_BIT, enableflag)

	if minute >= 0:
		enableAlarm(9, minute, 0x7f)
	else:
		disableAlarm(9)

	if hour >= 0:
		enableAlarm(10, hour, 0x7f)
	else:
		disableAlarm(10)

	if caldate >= 0:
		enableAlarm(11, caldate, 0x7f)
	else:
		disableAlarm(11)

	if weekday >= 0:
		# 0 - Sun (datetime 0 - Mon)
		if weekday > 5:
			weekday = 0
		else:
			weekday = weekday + 1
		enableAlarm(12, weekday, 0x7f)
	else:
		disableAlarm(12)

	return 0

# Set RTC Hourly Alarm
def setRTCAlarmHourly(enableflag, minute):
	return setRTCAlarm(enableflag, -1, -1, -1, minute)

# Set RTC Daily Alarm
def setRTCAlarmDaily(enableflag, hour, minute):
	return setRTCAlarm(enableflag, -1, -1, hour, minute)

# Set RTC Weekly Alarm
def setRTCAlarmWeekly(enableflag, dayofweek, hour, minute):
	return setRTCAlarm(enableflag, dayofweek, -1, hour, minute)

# Set RTC Monthly Alarm
def setRTCAlarmMonthly(enableflag, caldate, hour, minute):
	return setRTCAlarm(enableflag, -1, caldate, hour, minute)

#########
# Timer
#########

# Check if RTC Timer Flag is ON
def hasRTCTimerFlag():
	return hasRTCEventFlag(RTC_TIMER_BIT)

# Clear RTC Timer Flag
def clearRTCTimerFlag():
	return clearRTCEventFlag(RTC_TIMER_BIT)

# Remove RTC Timer Setting
def removeRTCTimer():
	if bus is None:
		return

	setRTCEventFlag(RTC_TIMER_BIT, False)

	# Timer disable and Set Timer frequency to lowest (0x3=1 per minute)
	bus.write_byte_data(ADDR_RTC, 14, 3)
	bus.write_byte_data(ADDR_RTC, 15, 0)

# Set RTC Timer Interval
def setRTCTimerInterval(enableflag, value, inSeconds = False):
	if bus is None:
		return -1

	if value > 255 or value < 1:
		return -1
	clearRTCTimerFlag()
	setRTCEventFlag(RTC_TIMER_BIT, enableflag)

	# 0x80 Timer Enabled, mode: 0x3=1/Min, 0x2=1/Sec, 0x1=Per 64th Sec, 0=Per 4096th Sec
	timerconfigFlag = 0x83
	if inSeconds == True:
		timerconfigFlag = 0x82

	bus.write_byte_data(ADDR_RTC, 14, timerconfigFlag)
	bus.write_byte_data(ADDR_RTC, 15, numDECtoBCD(value&0xff))
	return 0

#############
# Date/Time
#############

# Returns RTC timestamp as datetime object
def getRTCdatetime():
	if bus is None:
		return datetime.datetime(2000, 1, 1, 0, 0, 0)

	# Data Sheet Recommends to read this manner (instead of from registers)
	bus.write_byte(ADDR_RTC,2)

	out = bus.read_byte(ADDR_RTC)
	out = numBCDtoDEC(out & 0x7f)
	second = out
	#warningflag = (out & 0x80)>>7

	out = bus.read_byte(ADDR_RTC)
	minute = numBCDtoDEC(out & 0x7f)

	out = bus.read_byte(ADDR_RTC)
	hour = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte(ADDR_RTC)
	caldate = numBCDtoDEC(out & 0x3f)

	out = bus.read_byte(ADDR_RTC)
	#weekDay = numBCDtoDEC(out & 7)

	out = bus.read_byte(ADDR_RTC)
	month = numBCDtoDEC(out & 0x1f)

	out = bus.read_byte(ADDR_RTC)
	year = numBCDtoDEC(out)

	#print({"year":year, "month": month, "date": caldate, "hour": hour, "minute": minute, "second": second})

	if month == 0:
		# Reset, uninitialized RTC
		month = 1

	# Timezone is GMT/UTC +0
	# Year is from 2000
	try:
		return datetime.datetime(year+2000, month, caldate, hour, minute, second)+argonrtc.getLocaltimeOffset()
	except:
		return datetime.datetime(2000, 1, 1, 0, 0, 0)

# set RTC time using datetime object (Local time)
def setRTCdatetime(localdatetime):
	if bus is None:
		return
	# Set local time to UTC
	localdatetime = localdatetime - argonrtc.getLocaltimeOffset()

	# python Sunday = 6, RTC Sunday = 0
	weekDay = localdatetime.weekday()
	if weekDay == 6:
		weekDay = 0
	else:
		weekDay = weekDay + 1

	# Write to respective registers
	bus.write_byte_data(ADDR_RTC,2,numDECtoBCD(localdatetime.second))
	bus.write_byte_data(ADDR_RTC,3,numDECtoBCD(localdatetime.minute))
	bus.write_byte_data(ADDR_RTC,4,numDECtoBCD(localdatetime.hour))
	bus.write_byte_data(ADDR_RTC,5,numDECtoBCD(localdatetime.day))
	bus.write_byte_data(ADDR_RTC,6,numDECtoBCD(weekDay))
	bus.write_byte_data(ADDR_RTC,7,numDECtoBCD(localdatetime.month))

	# Year is from 2000
	bus.write_byte_data(ADDR_RTC,8,numDECtoBCD(localdatetime.year-2000))


#########
# Config
#########

# Set Next Alarm on RTC
def setNextAlarm(commandschedulelist, prevdatetime):
	nextcommandtime, weekday, caldate, hour, minute = argonrtc.getNextAlarm(commandschedulelist, prevdatetime)
	if prevdatetime >= nextcommandtime:
		return prevdatetime
	if weekday < 0 and caldate < 0 and hour < 0 and minute < 0:
		# No schedule
		# nextcommandtime is current time, which will be replaced/checked next iteration
		removeRTCAlarm()
		return nextcommandtime

	setRTCAlarm(True, nextcommandtime.weekday(), nextcommandtime.day, nextcommandtime.hour, nextcommandtime.minute)
	return nextcommandtime


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

	# Enable Alarm/Timer Flags
	enableflag = True

	if cmd == "CLEAN":
		removeRTCAlarm()
		removeRTCTimer()
	elif cmd == "SHUTDOWN":
		clearRTCAlarmFlag()
		clearRTCTimerFlag()

	elif cmd == "GETRTCSCHEDULE":
		print("Alarm Setting:")
		print("\t"+describeAlarm())
		#print("Timer Setting:")
		#print("\t"+describeTimer(True))

	elif cmd == "GETRTCTIME":
		print("RTC Time:", getRTCdatetime())

	elif cmd == "UPDATERTCTIME":
		setRTCdatetime(datetime.datetime.now())
		print("RTC Time:", getRTCdatetime())

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
		argonrtc.updateSystemTime(getRTCdatetime())

		commandschedulelist = argonrtc.formCommandScheduleList(argonrtc.loadConfigList(RTC_CONFIGFILE))
		nextrtcalarmtime = setNextAlarm(commandschedulelist, datetime.datetime.now())
		serviceloop = True
		while serviceloop==True:
			clearRTCAlarmFlag()
			clearRTCTimerFlag()

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


elif False:
	print("System Time: ", datetime.datetime.now())
	print("RTC    Time: ", getRTCdatetime())

	describeControlRegisters()
