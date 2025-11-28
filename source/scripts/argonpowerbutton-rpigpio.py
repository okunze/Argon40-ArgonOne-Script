
# For Libreelec/Lakka, note that we need to add system paths
# import sys
# sys.path.append('/storage/.kodi/addons/virtual.rpi-tools/lib')
import RPi.GPIO as GPIO
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

def argonpowerbutton_monitorlid(writeq):
	try:
		argonpowerbutton_debuglog("lid-monitor", "Starting")
		monitormode = True
		# 0 - Lid is closed, 1 - Lid is open
		# Pin Assignments
		PIN_LIDMONITOR=27

		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(PIN_LIDMONITOR, GPIO.IN,  pull_up_down=GPIO.PUD_UP)

		while monitormode == True:
			pulsetimesec = 1
			GPIO.wait_for_edge(PIN_LIDMONITOR, GPIO.FALLING)
			targetsecs = argonpowerbutton_getconfigval("lidshutdownsecs")
			if targetsecs > 0:
				argonpowerbutton_debuglog("lid-monitor", "Close Detect; Wait for :"+str(targetsecs))
			else:
				argonpowerbutton_debuglog("lid-monitor", "Close Detected; Do nothing")
			# Time pulse data
			time.sleep(1)
			while GPIO.input(PIN_LIDMONITOR) == GPIO.LOW:
				if targetsecs > 0:
					if pulsetimesec >= targetsecs:
						argonpowerbutton_debuglog("lid-monitor", "Target Reached, shutting down")
						monitormode = False
						os.system("shutdown now -h")
						break
				time.sleep(1)
				pulsetimesec += 1
			argonpowerbutton_debuglog("lid-monitor", "Open Detected")
	except Exception as liderror:
		try:
			argonpowerbutton_debuglog("lid-monitor-error", str(liderror))
		except:
			argonpowerbutton_debuglog("lid-monitor-error", "Error aborting")
		#pass
	GPIO.cleanup()


def argonpowerbutton_monitor(writeq):
	try:
		# Pin Assignments
		PIN_SHUTDOWN=4

		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(PIN_SHUTDOWN, GPIO.IN,  pull_up_down=GPIO.PUD_DOWN)

		while True:
			pulsetime = 1
			GPIO.wait_for_edge(PIN_SHUTDOWN, GPIO.RISING)
			time.sleep(0.01)
			while GPIO.input(PIN_SHUTDOWN) == GPIO.HIGH:
				time.sleep(0.01)
				pulsetime += 1
			if pulsetime >=2 and pulsetime <=3:
				# Testing
				#writeq.put("OLEDSWITCH")
				writeq.put("OLEDSTOP")
				os.system("reboot")
				break
			elif pulsetime >=4 and pulsetime <=5:
				writeq.put("OLEDSTOP")
				os.system("shutdown now -h")
				break
			elif pulsetime >=6 and pulsetime <=7:
				writeq.put("OLEDSWITCH")
	except Exception:
		writeq.put("ERROR")
	GPIO.cleanup()



def argonpowerbutton_monitorswitch(writeq):
	try:
		# Pin Assignments
		PIN_SHUTDOWN=4

		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(PIN_SHUTDOWN, GPIO.IN,  pull_up_down=GPIO.PUD_DOWN)

		while True:
			pulsetime = 1
			GPIO.wait_for_edge(PIN_SHUTDOWN, GPIO.RISING)
			time.sleep(0.01)
			while GPIO.input(PIN_SHUTDOWN) == GPIO.HIGH:
				time.sleep(0.01)
				pulsetime += 1
			if pulsetime >= 10:
				writeq.put("OLEDSWITCH")
	except Exception:
		writeq.put("ERROR")
	GPIO.cleanup()
