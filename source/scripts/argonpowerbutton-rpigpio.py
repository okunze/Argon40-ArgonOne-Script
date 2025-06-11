
# For Libreelec/Lakka, note that we need to add system paths
# import sys
# sys.path.append('/storage/.kodi/addons/virtual.rpi-tools/lib')
import RPi.GPIO as GPIO
import os
import time

# This function is the thread that monitors activity in our shutdown pin
# The pulse width is measured, and the corresponding shell command will be issued

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
