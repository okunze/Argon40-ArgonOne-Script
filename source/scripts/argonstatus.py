#!/usr/bin/python3

import sys
import os

sys.path.append("/etc/argon/")
from argonsysinfo import *
from argonregister import *
from argononed import *

def getFahrenheit(celsiustemp):
	try:
		return (32+9*(celsiustemp)/5)
	except:
		return 0


temperature="C"
tmpconfig=load_unitconfig(UNIT_CONFIGFILE)
if "temperature" in tmpconfig:
	temperature = tmpconfig["temperature"]

baseleftoffset = ""

stdleftoffset = "   "

#if len(sys.argv) > 2:
#	baseleftoffset = stdleftoffset
baseleftoffset = stdleftoffset

argctr = 1
while argctr < len(sys.argv):
	cmd = sys.argv[argctr].lower()
	argctr = argctr + 1
	if baseleftoffset != "":
		print(cmd.upper(),"INFORMATION:")
	if cmd == "cpu usage":
		# CPU Usage
		curlist = argonsysinfo_listcpuusage()

		while len(curlist) > 0:
			curline = ""
			tmpitem = curlist.pop(0)
			curline = tmpitem["title"]+": "+str(tmpitem["value"])+"%"
			print(baseleftoffset+curline)
	elif cmd == "storage":
		# Storage Info
		curlist = []
		try:
			tmpobj = argonsysinfo_listhddusage()
			for curdev in tmpobj:
				curlist.append({"title": curdev, "value": argonsysinfo_kbstr(tmpobj[curdev]['total']), "usage": int(100*tmpobj[curdev]['used']/tmpobj[curdev]['total']) })
			#curlist = argonsysinfo_liststoragetotal()
		except Exception:
			curlist = []

		while len(curlist) > 0:
			tmpitem = curlist.pop(0)
			# Right column first, safer to overwrite white space
			print(baseleftoffset+tmpitem["title"], str(tmpitem["usage"])+"%","used of", tmpitem["value"])

	elif cmd == "raid":
		# Raid Info
		curlist = []
		try:
			tmpobj = argonsysinfo_listraid()
			curlist = tmpobj['raidlist']
		except Exception:
			curlist = []

		if len(curlist) > 0:
			tmpitem = curlist.pop(0)
			print(baseleftoffset+tmpitem["title"], tmpitem["value"], argonsysinfo_kbstr(tmpitem["info"]["size"]))

			if len(tmpitem['info']['state']) > 0:
				print(baseleftoffset+stdleftoffset,tmpitem['info']['state'])

			if len(tmpitem['info']['rebuildstat']) > 0:
				print(baseleftoffset+stdleftoffset,"Rebuild:" + tmpitem['info']['rebuildstat'])


			print(baseleftoffset+stdleftoffset,"Active:"+str(int(tmpitem["info"]["active"]))+"/"+str(int(tmpitem["info"]["devices"])))
			print(baseleftoffset+stdleftoffset,"Working:"+str(int(tmpitem["info"]["working"]))+"/"+str(int(tmpitem["info"]["devices"])))
			print(baseleftoffset+stdleftoffset,"Failed:"+str(int(tmpitem["info"]["failed"]))+"/"+str(int(tmpitem["info"]["devices"])))
		else:
			print(baseleftoffset+stdleftoffset,"N/A")

	elif cmd == "ram":
		# RAM
		try:
			tmpraminfo = argonsysinfo_getram()
			print(baseleftoffset+tmpraminfo[0],"of", tmpraminfo[1])
		except Exception:
			pass

	elif cmd == "temperature":
		# Temp
		try:
			hddtempctr = 0
			maxcval = 0
			mincval = 200

			alltempobj = {"cpu": argonsysinfo_getcputemp()}
			# Get min/max of hdd temp
			hddtempobj = argonsysinfo_gethddtemp()
			for curdev in hddtempobj:
				alltempobj[curdev] = hddtempobj[curdev]
				if hddtempobj[curdev] < mincval:
					mincval = hddtempobj[curdev]
				if hddtempobj[curdev] > maxcval:
					maxcval = hddtempobj[curdev]
				hddtempctr = hddtempctr + 1

			if hddtempctr > 0:
				alltempobj["hdd min"]=mincval
				alltempobj["hdd max"]=maxcval

			for curdev in alltempobj:
				if temperature == "C":
					# Celsius
					tmpstr = str(alltempobj[curdev])
					if len(tmpstr) > 4:
						tmpstr = tmpstr[0:4]
				else:
					# Fahrenheit
					tmpstr = str(getFahrenheit(alltempobj[curdev]))
					if len(tmpstr) > 5:
						tmpstr = tmpstr[0:5]
				print(baseleftoffset+curdev.upper()+": "+ tmpstr+ chr(176) +temperature)

		except Exception:
			pass
	elif cmd == "ip":
		# IP Address
		try:
			print(baseleftoffset+argonsysinfo_getip())
		except Exception:
			pass
	elif cmd == "fan speed":
		# Fan Speed
		try:
			newspeed = argonregister_getfanspeed(argonregister_initializebusobj())
			if newspeed <= 0:
				fanconfig = load_fancpuconfig()
				fanhddconfig = load_fanhddconfig()

				# Speed based on CPU Temp
				val = argonsysinfo_getcputemp()
				newspeed = get_fanspeed(val, fanconfig)

				val = argonsysinfo_getmaxhddtemp()
				tmpspeed = get_fanspeed(val, fanhddconfig)
				if tmpspeed > newspeed:
					newspeed = tmpspeed
			print(baseleftoffset+"Fan Speed",str(newspeed))
		except Exception:
			pass
	elif cmd == "fan configuration":
		fanconfig = load_fancpuconfig()
		fanhddconfig = load_fanhddconfig()

		if len(fanhddconfig) > 0:
			print(baseleftoffset+"Fan Temp-Speed cut-offs")
		for curconfig in fanconfig:
			print(baseleftoffset+stdleftoffset,curconfig)

		if len(fanhddconfig) > 0:
			print(baseleftoffset+"HDD Temp-Speed cut-offs")
			for curconfig in fanhddconfig:
				print(baseleftoffset+stdleftoffset,curconfig)


