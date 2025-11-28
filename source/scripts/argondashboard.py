#!/bin/python3

import time
import os
import sys

import signal
import curses


sys.path.append("/etc/argon/")
from argonsysinfo import *
from argonregister import *



############
# Constants
############
COLORPAIRID_DEFAULT=1
COLORPAIRID_LOGO=2
COLORPAIRID_DEFAULTINVERSE=3
COLORPAIRID_ALERT=4
COLORPAIRID_WARNING=5
COLORPAIRID_GOOD=6




INPUTREFRESHMS=100
DISPLAYREFRESHMS=5000
UPS_LOGFILE="/dev/shm/upslog.txt"


###################
# Display Elements
###################

def displaydatetime(stdscr):
	try:
		curtimenow = time.localtime()

		stdscr.addstr(1, 1, time.strftime("%A", curtimenow), curses.color_pair(COLORPAIRID_DEFAULT))
		stdscr.addstr(2, 1, time.strftime("%b %d,%Y", curtimenow), curses.color_pair(COLORPAIRID_DEFAULT))
		stdscr.addstr(3, 1, time.strftime("%I:%M%p", curtimenow), curses.color_pair(COLORPAIRID_DEFAULT))
	except:
		pass

def displayipbattery(stdscr):
	try:
		displaytextright(stdscr,1, argonsysinfo_getip()+" ", COLORPAIRID_DEFAULT)
	except:
		pass
	try:
		status = ""
		level = ""
		outobj = {}
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

			colorpairidx = COLORPAIRID_DEFAULT
			if tmp_charging:
				if tmp_battery > 99:
					status="Plugged"
					level=""
				else:
					status="Charging"
					level=str(tmp_battery)+"%"
			else:
				status="Battery"
				level=str(tmp_battery)+"%"
				if tmp_battery <= 20:
					colorpairidx = COLORPAIRID_ALERT
				elif tmp_battery <= 50:
					colorpairidx = COLORPAIRID_WARNING
				else:
					colorpairidx = COLORPAIRID_GOOD

			displaytextright(stdscr,2, status+" ", colorpairidx)
			displaytextright(stdscr,3, level+" ", colorpairidx)
		except:
			pass


	except:
		pass


def displayramcpu(stdscr, refcpu, rowstart, colstart):
	curusage_b = argonsysinfo_getcpuusagesnapshot()
	try:
		outputlist = []
		tmpraminfo = argonsysinfo_getram()
		outputlist.append({"title": "ram ", "value": tmpraminfo[1]+" "+tmpraminfo[0]+" Free"})

		for cpuname in refcpu:
			if cpuname == "cpu":
				continue
			if refcpu[cpuname]["total"] == curusage_b[cpuname]["total"]:
				outputlist.append({"title": cpuname, "value": "Loading"})
			else:
				total = curusage_b[cpuname]["total"]-refcpu[cpuname]["total"]
				idle = curusage_b[cpuname]["idle"]-refcpu[cpuname]["idle"]
				outputlist.append({"title": cpuname, "value": str(int(100*(total-idle)/(total)))+"% Used"})
		displaytitlevaluelist(stdscr, rowstart, colstart, outputlist)
	except:
		pass
	return curusage_b


def displaytempfan(stdscr, rowstart, colstart):
	try:
		outputlist = []
		try:
			if busobj is not None:
				fanspeed = argonregister_getfanspeed(busobj)
				fanspeedstr = "Off"
				if fanspeed > 0:
					fanspeedstr = str(fanspeed)+"%"
				outputlist.append({"title": "Fan ", "value": fanspeedstr})
		except:
			pass
		# Todo load from config
		temperature = "C"
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
					outputlist.append({"title": curdev.upper(), "value": tmpstr +temperature})
				else:
					outputlist.append({"title": curdev.upper(), "value": tmpstr +temperature})
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

			outputlist.append({"title": "Temp", "value": tmpstr +temperature})
		displaytitlevaluelist(stdscr, rowstart, colstart, outputlist)
	except:
		pass



def displaystorage(stdscr, rowstart, colstart):
	try:
		outputlist = []
		tmpobj = argonsysinfo_listhddusage()
		for curdev in tmpobj:
			outputlist.append({"title": curdev, "value": argonsysinfo_kbstr(tmpobj[curdev]['total'])+ " "+ str(int(100*tmpobj[curdev]['used']/tmpobj[curdev]['total']))+"% Used" })
		displaytitlevaluelist(stdscr, rowstart, colstart, outputlist)
	except:
		pass

##################
# Helpers
##################

# Initialize I2C Bus
bus = argonregister_initializebusobj()

def handle_resize(signum, frame):
	# TODO: Not working?
	curses.update_lines_cols()
	# Ideally redraw here

def displaytitlevaluelist(stdscr, rowstart, leftoffset, curlist):
	rowidx = rowstart
	while rowidx < curses.LINES and len(curlist) > 0:
		curline = ""
		tmpitem = curlist.pop(0)
		curline = tmpitem["title"]+": "+str(tmpitem["value"])

		stdscr.addstr(rowidx, leftoffset, curline)
		rowidx = rowidx + 1


def displaytextcentered(stdscr, rownum, strval, colorpairidx = COLORPAIRID_DEFAULT):
	leftoffset = 0
	numchars = len(strval)
	if numchars < 1:
		return
	elif (numchars > curses.COLS):
		leftoffset = 0
		strval = strval[0:curses.COLS]
	else:
		leftoffset = (curses.COLS - numchars)>>1

	stdscr.addstr(rownum, leftoffset, strval, curses.color_pair(colorpairidx))


def displaytextright(stdscr, rownum, strval, colorpairidx = COLORPAIRID_DEFAULT):
	leftoffset = 0
	numchars = len(strval)
	if numchars < 1:
		return
	elif (numchars > curses.COLS):
		leftoffset = 0
		strval = strval[0:curses.COLS]
	else:
		leftoffset = curses.COLS - numchars

	stdscr.addstr(rownum, leftoffset, strval, curses.color_pair(colorpairidx))


def displaylinebreak(stdscr, rownum, colorpairidx = COLORPAIRID_DEFAULTINVERSE):
	strval = " "
	while len(strval) < curses.COLS:
		strval = strval + " "
	stdscr.addstr(rownum, 0, strval, curses.color_pair(colorpairidx))




##################
# Main Loop
##################

def mainloop(stdscr):
	try:
		# Set up signal handler
		signal.signal(signal.SIGWINCH, handle_resize)

		maxloopctr = int(DISPLAYREFRESHMS/INPUTREFRESHMS)
		sleepsecs = INPUTREFRESHMS/1000

		loopctr = maxloopctr
		loopmode = True

		stdscr = curses.initscr()

		# Turn off echoing of keys, and enter cbreak mode,
		# where no buffering is performed on keyboard input
		curses.noecho()
		curses.cbreak()
		curses.curs_set(0)
		curses.start_color()

		#curses.COLOR_BLACK
		#curses.COLOR_BLUE
		#curses.COLOR_CYAN
		#curses.COLOR_GREEN
		#curses.COLOR_MAGENTA
		#curses.COLOR_RED
		#curses.COLOR_WHITE
		#curses.COLOR_YELLOW

		curses.init_pair(COLORPAIRID_DEFAULT, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(COLORPAIRID_LOGO, curses.COLOR_WHITE, curses.COLOR_RED)
		curses.init_pair(COLORPAIRID_DEFAULTINVERSE, curses.COLOR_BLACK, curses.COLOR_WHITE)
		curses.init_pair(COLORPAIRID_ALERT, curses.COLOR_RED, curses.COLOR_BLACK)
		curses.init_pair(COLORPAIRID_WARNING, curses.COLOR_YELLOW, curses.COLOR_BLACK)
		curses.init_pair(COLORPAIRID_GOOD, curses.COLOR_GREEN, curses.COLOR_BLACK)

		stdscr.nodelay(True)

		refcpu = argonsysinfo_getcpuusagesnapshot()
		while True:
			try:
				key = stdscr.getch()
				# if key == ord('x') or key == ord('X'):
				# Any key
				if key > 0:
					break
			except curses.error:
				# No key was pressed
				pass

			loopctr = loopctr + 1
			if loopctr >= maxloopctr:
				loopctr = 0
				# Screen refresh loop
				# Clear screen
				stdscr.clear()

				displaytextcentered(stdscr, 0, "                     ", COLORPAIRID_LOGO)
				displaytextcentered(stdscr, 1, "  Argon40 Dashboard  ", COLORPAIRID_LOGO)
				displaytextcentered(stdscr, 2, "                     ", COLORPAIRID_LOGO)
				displaytextcentered(stdscr, 3, "Press any key to close")
				displaylinebreak(stdscr, 5)

				# Display Elements
				displaydatetime(stdscr)
				displayipbattery(stdscr)

				# Data Columns
				rowstart = 7
				colstart = 20
				refcpu = displayramcpu(stdscr, refcpu, rowstart, colstart)
				displaystorage(stdscr, rowstart, colstart+30)
				displaytempfan(stdscr, rowstart, colstart+60)

				# Main refresh even
				stdscr.refresh()

			time.sleep(sleepsecs)

	except Exception as initerr:
		pass

	##########
	# Cleanup
	##########

	try:
		curses.curs_set(1)
		curses.echo()
		curses.nocbreak()
		curses.endwin()
	except Exception as closeerr:
		pass

try:
	curses.wrapper(mainloop)
except Exception as wrapperr:
	pass
