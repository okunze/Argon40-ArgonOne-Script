
# For Libreelec/Lakka, note that we need to add system paths
# import sys
# sys.path.append('/storage/.kodi/addons/virtual.rpi-tools/lib')
import gpiod
import os
import time

# This function is the thread that monitors activity in our shutdown pin
# The pulse width is measured, and the corresponding shell command will be issued

def argonpowerbutton_monitor(writeq):

	try:
		# Reference https://github.com/brgl/libgpiod/blob/master/bindings/python/examples/gpiomon.py

		# Pin Assignments
		LINE_SHUTDOWN=4
		try:
			# Pi5 mapping
			chip = gpiod.Chip('4')
		except Exception as gpioerr:
			# Old mapping
			chip = gpiod.Chip('0')

		lineobj = chip.get_line(LINE_SHUTDOWN)
		lineobj.request(consumer="argon", type=gpiod.LINE_REQ_EV_BOTH_EDGES)
		while True:
			hasevent = lineobj.event_wait(10)
			if hasevent:
				pulsetime = 1
				eventdata = lineobj.event_read()
				if eventdata.type == gpiod.LineEvent.RISING_EDGE:
					# Time pulse data
					while lineobj.get_value() == 1:
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
		lineobj.release()
		chip.close()
	except Exception:
		writeq.put("ERROR")


def argonpowerbutton_monitorswitch(writeq):

	try:
		# Reference https://github.com/brgl/libgpiod/blob/master/bindings/python/examples/gpiomon.py

		# Pin Assignments
		LINE_SHUTDOWN=4
		try:
			# Pi5 mapping
			chip = gpiod.Chip('4')
		except Exception as gpioerr:
			# Old mapping
			chip = gpiod.Chip('0')

		lineobj = chip.get_line(LINE_SHUTDOWN)
		lineobj.request(consumer="argon", type=gpiod.LINE_REQ_EV_BOTH_EDGES)
		while True:
			hasevent = lineobj.event_wait(10)
			if hasevent:
				pulsetime = 1
				eventdata = lineobj.event_read()
				if eventdata.type == gpiod.LineEvent.RISING_EDGE:
					# Time pulse data
					while lineobj.get_value() == 1:
						time.sleep(0.01)
						pulsetime += 1

					if pulsetime >= 10:
						writeq.put("OLEDSWITCH")
		lineobj.release()
		chip.close()
	except Exception:
		writeq.put("ERROR")
