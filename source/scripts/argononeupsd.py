#!/usr/bin/python3

import time
import os

UPS_LOGFILE="/dev/shm/upslog.txt"
#UPS_DEVFILE="/dev/argonbatteryicon"

def notifymessage(message, iscritical):
	wftype="notify"
	if iscritical:
		wftype="critical"
	os.system("export SUDO_UID=1000; wfpanelctl "+wftype+" \""+message+"\"")
	os.system("export DISPLAY=:0.0; lxpanelctl notify \""+message+"\"")

try:
	outobj = {}
	#os.system("insmod /etc/argon/ups/argonbatteryicon.ko")
	prevnotifymsg=""

	tmp_battery = 100
	tmp_charging = 1

	device_battery = -1
	device_charging = -1

	while True:
		try:
			# Load status
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

			# Map to data
			try:
				statuslist = outobj["power"].lower().split(" ")
				if statuslist[0] == "battery":
					tmp_charging = 0
				else:
					tmp_charging = 1
				tmp_battery = int(statuslist[1].replace("%",""))
			except:
				tmp_charging = device_charging
				tmp_battery = device_battery

			# Update module data if changed
			if tmp_charging != device_charging or tmp_battery!=device_battery:
				device_charging = tmp_charging
				device_battery = tmp_battery

				# No longer using default battery indicator
				#try:
				#	with open(UPS_DEVFILE, 'w') as f:
				#		f.write("capacity = "+str(device_battery)+"\ncharging = "+str(device_charging)+"\n")
				#except Exception as e:
				#	pass

				curnotifymsg = ""
				curnotifycritical=False

				if tmp_charging:
					if "Shutting Down" in prevnotifymsg:
						os.system("shutdown -c ""Charging, shutdown cancelled.""")

				if tmp_battery > 99:
					curnotifymsg="Fully Charged"
				elif tmp_charging:
					curnotifymsg="Charging"
				else:
					if tmp_battery > 50:
						curnotifymsg="Battery Mode"
					elif tmp_battery > 20:
						curnotifymsg="50%% Battery"
					elif tmp_battery > 10:
						curnotifymsg="20%% Battery"
					elif tmp_battery > 5:
						#curnotifymsg="Low Battery"
						curnotifymsg="Low Battery: The device may power off automatically soon."
						curnotifycritical=True
					else:
						curnotifymsg="CRITICAL BATTERY: Shutting Down in 1 minute"
						curnotifycritical=True


				if prevnotifymsg != curnotifymsg:
					notifymessage(curnotifymsg, curnotifycritical)
					if tmp_battery <= 5 and tmp_charging == 0:
						os.system("shutdown +1 """+curnotifymsg+".""")

				prevnotifymsg = curnotifymsg

		except OSError:
			pass
		time.sleep(60)
except:
	pass

