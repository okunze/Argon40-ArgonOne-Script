
# For Libreelec/Lakka, note that we need to add system paths
# import sys
# sys.path.append('/storage/.kodi/addons/virtual.rpi-tools/lib')
import gpiod
import os
import time

# Debug Logger
def argonpowerbutton_debuglog(typestr, logstr):
	try:
		DEBUGFILE="/dev/shm/argononegpiodebuglog.txt"
		tmpstrpadding = "                      "

		with open(DEBUGFILE, "a") as txt_file:
			txt_file.write("["+time.asctime(time.localtime(time.time()))+"] "+typestr.upper()+" "+logstr.strip().replace("\n","\n"+tmpstrpadding)+"\n")
	except:
		pass

def argonpowerbutton_getvalue(lineobj,lineid):
	if lineid is not None:
		tmpval = lineobj.get_value(lineid) != gpiod.line.Value.INACTIVE
		if tmpval == False:
			return 0
		return 1
	return lineobj.get_value()

def argonpowerbutton_watchline(debugname, dataq, lineid, callback):
	monitormode = True
	argonpowerbutton_debuglog(debugname, "Starting")
	# Pi5 mapping, 0 for older
	chippath = '/dev/gpiochip4'
	try:
		chip = gpiod.Chip(chippath)
	except Exception as gpioerr:
		try:
			# Old mapping
			chippath = '/dev/gpiochip0'
			chip = gpiod.Chip(chippath)
		except Exception as gpioolderr:
			chippath = ""

	if len(chippath) == 0:
		argonpowerbutton_debuglog(debugname+"-error", "Unable to initialize GPIO")
		try:
			dataq.put("ERROR")
		except:
			pass
		return

	# Monitoring starts
	try:
		try:
			# Reference https://github.com/brgl/libgpiod/blob/master/bindings/python/examples/gpiomon.py

			lineobj = chip.get_line(lineid)
			if lineid == 27:
				lineobj.request(consumer="argon", type=gpiod.LINE_REQ_EV_BOTH_EDGES, flags=gpiod.LINE_REQ_FLAG_BIAS_PULL_UP)
			else:
				lineobj.request(consumer="argon", type=gpiod.LINE_REQ_EV_BOTH_EDGES)
			while monitormode == True:
				hasevent = lineobj.event_wait(10)
				if hasevent:
					eventdata = lineobj.event_read()
					monitormode = callback(eventdata.type == gpiod.LineEvent.RISING_EDGE, lineobj, dataq, None)

			lineobj.release()
			chip.close()
		except Exception:
			# https://github.com/brgl/libgpiod/blob/master/bindings/python/examples/watch_line_rising.py
			configobj = {lineid: gpiod.LineSettings(direction=gpiod.line.Direction.INPUT, edge_detection=gpiod.line.Edge.BOTH)}
			if lineid == 27:
				configobj = {lineid: gpiod.LineSettings(direction=gpiod.line.Direction.INPUT, edge_detection=gpiod.line.Edge.BOTH, bias=gpiod.line.Bias.PULL_UP )}

			with gpiod.request_lines(
					chippath,
					consumer="argon",
					config=configobj,
				) as request:
					while monitormode:
						# Blocks until at least one event is available
						for event in request.read_edge_events():
							monitormode = callback(event.event_type == event.Type.RISING_EDGE, request, dataq, event.line_offset)
	except Exception as monitorerror:
		try:
			argonpowerbutton_debuglog(debugname+"-error", str(monitorerror))
		except:
			argonpowerbutton_debuglog(debugname+"-error", "Error aborting")
	try:
		dataq.put("ERROR")
	except:
		pass

# This function is the thread that monitors activity in our shutdown pin
# The pulse width is measured, and the corresponding shell command will be issued

def argonpowerbutton_getconfigval(keyname, datatype="int"):
	keyname = keyname.lower()
	fname = "/etc/argononeupd.conf"
	try:
		with open(fname, "r") as fp:
			for curline in fp:
				if not curline:
					continue
				tmpline = curline.replace(" ", "").replace("\t", "")
				if not tmpline:
					continue
				if tmpline[0] == "#":
					continue
				tmppair = tmpline.split("=")
				if len(tmppair) != 2:
					continue

				tmpvar = tmppair[0].lower()
				if tmpvar != keyname:
					continue

				try:
					if datatype == "int":
						return int(tmppair[1])
					elif datatype == "float":
						return float(tmppair[1])
					return tmppair[1]
				except:
					continue
	except:
		pass
	if datatype == "int":
		return -1
	elif datatype == "float":
		return -1
	return ""

def argonpowerbutton_monitorlidevent(isrising, lineobj, writeq, lineid):
	if isrising == False:
		targetsecs = argonpowerbutton_getconfigval("lidshutdownsecs")
		if targetsecs > 0:
			argonpowerbutton_debuglog("lid-monitor", "Close Detect; Wait for :"+str(targetsecs))
		else:
			argonpowerbutton_debuglog("lid-monitor", "Close Detected; Do nothing")
		# Time pulse data
		time.sleep(1)
		pulsetimesec = 1
		# 0 - Lid is closed, 1 - Lid is open
		while argonpowerbutton_getvalue(lineobj, lineid) == 0:
			if targetsecs > 0:
				if pulsetimesec >= targetsecs:
					argonpowerbutton_debuglog("lid-monitor", "Target Reached, shutting down")
					monitormode = False
					os.system("shutdown now -h")
					return False

			time.sleep(1)
			pulsetimesec += 1
		argonpowerbutton_debuglog("lid-monitor", "Open Detected")
	return True

def argonpowerbutton_monitorlid(writeq):
	LINE_LIDMONITOR=27
	argonpowerbutton_watchline("lid-monitor", writeq, LINE_LIDMONITOR, argonpowerbutton_monitorlidevent)

def argonpowerbutton_monitorevent(isrising, lineobj, writeq, lineid):
	pulsetime = 0
	if isrising == True:
		# Time pulse data
		while argonpowerbutton_getvalue(lineobj, lineid) == 1:
			time.sleep(0.01)
			pulsetime += 1

		if pulsetime >=2 and pulsetime <=3:
			# Testing
			#writeq.put("OLEDSWITCH")
			writeq.put("OLEDSTOP")
			os.system("reboot")
			return False
		elif pulsetime >=4 and pulsetime <=5:
			writeq.put("OLEDSTOP")
			os.system("shutdown now -h")
			return False
		elif pulsetime >=6 and pulsetime <=7:
			writeq.put("OLEDSWITCH")
	return True

def argonpowerbutton_monitor(writeq):
	LINE_SHUTDOWN=4
	argonpowerbutton_watchline("button", writeq, LINE_SHUTDOWN, argonpowerbutton_monitorevent)


def argonpowerbutton_monitorswitchevent(isrising, lineobj, writeq, lineid):
	pulsetime = 0
	if isrising == True:
		# Time pulse data
		while argonpowerbutton_getvalue(lineobj, lineid) == 1:
			time.sleep(0.01)
			pulsetime += 1

		if pulsetime >= 10:
			writeq.put("OLEDSWITCH")
	return True

def argonpowerbutton_monitorswitch(writeq):
	LINE_SHUTDOWN=4
	argonpowerbutton_watchline("button-switch", writeq, LINE_SHUTDOWN, argonpowerbutton_monitorswitchevent)

# Testing
#argonpowerbutton_monitor(None)
