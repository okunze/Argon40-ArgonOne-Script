#!/usr/bin/python3

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image

import sys
import datetime
import math

import os
import time

# Initialize I2C Bus
import smbus

oledport=1

try:
	bus=smbus.SMBus(1)
except Exception:
	try:
		oledport=0
		# Older version
		bus=smbus.SMBus(0)
	except Exception:
		print("Unable to detect i2c")
		bus=None


ADDR_OLED=0x3c
OLED_WD=1
OLED_HT=1
oled_device=None
try:
	oled_device=ssd1306(i2c(port=oledport, address=ADDR_OLED))

	OLED_WD=oled_device.bounding_box[2]+1
	OLED_HT=oled_device.bounding_box[3]+1
except Exception:
	print("Unable to initialize OLED")
	bus=None

OLED_NUMFONTCHAR=256

OLED_BUFFERIZE = ((OLED_WD*OLED_HT)>>3)
oled_imagebuffer = [0] * OLED_BUFFERIZE


def oled_getmaxY():
	return OLED_HT

def oled_getmaxX():
	return OLED_WD

def oled_loadbg(bgname):
	if bgname == "bgblack":
		oled_clearbuffer()
		return
	elif bgname == "bgwhite":
		oled_clearbuffer(1)
		return
	try:
		file = open("/etc/argon/oled/"+bgname+".bin", "rb")
		bgbytes = list(file.read())
		file.close()
		ctr = len(bgbytes)
		if ctr == OLED_BUFFERIZE:
			oled_imagebuffer[:] = bgbytes
		elif ctr > OLED_BUFFERIZE:
			oled_imagebuffer[:] = bgbytes[0:OLED_BUFFERIZE]
		else:
			oled_imagebuffer[0:ctr] = bgbytes
			# Clear the rest of the buffer
			while ctr < OLED_BUFFERIZE:
				oled_imagebuffer[ctr] = 0
				ctr=ctr+1
	except FileNotFoundError:
		oled_clearbuffer()


def oled_clearbuffer(value = 0):
	if value != 0:
		value = 0xff
	ctr = 0
	while ctr < OLED_BUFFERIZE:
		oled_imagebuffer[ctr] = value
		ctr=ctr+1

def oled_writebyterow(x,y,bytevalue, mode = 0):
	bufferoffset = OLED_WD*(y>>3) + x
	if mode == 0:
		oled_imagebuffer[bufferoffset] = bytevalue
	elif mode == 1:
		oled_imagebuffer[bufferoffset] = bytevalue^oled_imagebuffer[bufferoffset]
	else:
		oled_imagebuffer[bufferoffset] = bytevalue|oled_imagebuffer[bufferoffset]


def oled_writebuffer(x,y,value, mode = 0):

	yoffset = y>>3
	yshift = y&0x7
	ybit = (1<<yshift)

	ymask = 0xFF^ybit

	if value != 0:
		value = ybit

	bufferoffset = OLED_WD*yoffset + x

	curval = oled_imagebuffer[bufferoffset]
	if mode & 1:
		oled_imagebuffer[bufferoffset] = curval^value
	else:
		oled_imagebuffer[bufferoffset] = curval&ymask|value


def oled_fill(value):
	oled_clearbuffer(value)
	oled_flushimage()


def oled_flushimage(hidescreen = True):
	if bus is None:
		return
	if hidescreen == True:
		# Reset/Hide screen
		oled_power(False)

	tmplist = [0]*OLED_BUFFERIZE

	# Each byte = 1 col x 8 rows

	ymask = 0
	yidx = 0
	xmask = 0
	xidx = 0
	outbyte = 0
	srcidx = 0
	outoffsetidx = 0
	outyoffset = 0
	xoffset = 0
	while srcidx < OLED_BUFFERIZE:
		# OLED_WDx8 pixels at a time, y in reverse bit order
		outyoffset = 0
		yidx = 0
		ymask = 1
		while yidx < 8:

			outoffsetidx = 0
			outbyte = 0
			xmask = 0x80
			xidx = 0

			xoffset = 0
			while xoffset < OLED_WD:
				if oled_imagebuffer[srcidx+xoffset] & ymask:
					outbyte = outbyte | xmask
				xmask = xmask >> 1
				xidx = xidx + 1
				if xidx >= 8:
					tmplist[srcidx+outoffsetidx + outyoffset] = outbyte
					xmask = 0x80
					xidx = 0
					outbyte = 0
					outoffsetidx = outoffsetidx + 1

				xoffset = xoffset + 1

			outyoffset = outyoffset + (OLED_WD>>3)
			yidx = yidx + 1
			ymask = ymask << 1

		srcidx = srcidx + OLED_WD

	oled_device.display(Image.frombytes("1", [OLED_WD, OLED_HT], bytes(tmplist)))

	if hidescreen == True:
		# Display
		oled_power(True)



def oled_drawfilledrectangle(x, y, wd, ht, mode = 0):
	ymax = y + ht
	cury = y&0xF8

	xmax = x + wd
	curx = x
	if ((y & 0x7)) != 0:
		yshift = y&0x7
		bytevalue = (0xFF<<yshift)&0xFF

		# If 8 no additional masking needed
		if ymax-cury  < 8:
			yshift = 8-((ymax-cury)&0x7)
			bytevalue = bytevalue & (0xFF>>yshift)

		while curx < xmax:
			oled_writebyterow(curx,cury,bytevalue, mode)
			curx = curx + 1
		cury = cury + 8
	# Draw 8 rows at a time when possible
	while cury + 8 < ymax:
		curx = x
		while curx < xmax:
			oled_writebyterow(curx,cury,0xFF, mode)
			curx = curx + 1
		cury = cury + 8

	if cury < ymax:
		yshift = 8-((ymax-cury)&0x7)
		bytevalue = (0xFF>>yshift)

		curx = x
		while curx < xmax:
			oled_writebyterow(curx,cury,bytevalue, mode)
			curx = curx + 1


def oled_writetextaligned(textdata, x, y, boxwidth, alignmode, charwd = 6, mode = 0):
	leftoffset = 0
	if alignmode == 1:
		# Centered
		leftoffset = (boxwidth-len(textdata)*charwd)>>1
	elif alignmode == 2:
		# Right aligned
		leftoffset = (boxwidth-len(textdata)*charwd)

	oled_writetext(textdata, x+leftoffset, y, charwd, mode)


def oled_writetext(textdata, x, y, charwd = 6, mode = 0):
	if charwd < 6:
		charwd = 6

	charht = int((charwd<<3)/6)
	if charht & 0x7:
		charht = (charht&0xF8) + 8

	try:
		file = open("/etc/argon/oled/font"+str(charht)+"x"+str(charwd)+".bin", "rb")
		fontbytes = list(file.read())
		file.close()
	except FileNotFoundError:
		try:
			# Default to smallest
			file = open("/etc/argon/oled/font8x6.bin", "rb")
			fontbytes = list(file.read())
			file.close()
		except FileNotFoundError:
			return

	if ((y & 0x7)) == 0:
		# Use optimized loading
		oled_fastwritetext(textdata, x, y, charht, charwd, fontbytes, mode)
		return

	numfontrow = charht>>3
	ctr = 0
	while ctr < len(textdata):
		fontoffset = ord(textdata[ctr])*charwd
		fontcol = 0
		while fontcol < charwd and x < OLED_WD:
			fontrow = 0
			row = y
			while fontrow < numfontrow and row < OLED_HT and x >= 0:
				curbit = 0x80
				curbyte = (fontbytes[fontoffset + fontcol + (OLED_NUMFONTCHAR*charwd*fontrow)])
				subrow = 0
				while subrow < 8 and row < OLED_HT:
					value = 0
					if (curbyte&curbit) != 0:
						value = 1
					oled_writebuffer(x,row,value, mode)
					curbit = curbit >> 1
					row = row + 1
					subrow = subrow + 1
				fontrow = fontrow + 1
			fontcol = fontcol + 1
			x = x + 1
		ctr = ctr + 1

def oled_fastwritetext(textdata, x, y, charht, charwd, fontbytes, mode = 0):

	numfontrow = charht>>3
	ctr = 0
	while ctr < len(textdata):
		fontoffset = ord(textdata[ctr])*charwd
		fontcol = 0
		while fontcol < charwd and x < OLED_WD:
			fontrow = 0
			row = y&0xF8
			while fontrow < numfontrow and row < OLED_HT and x >= 0:
				curbyte = (fontbytes[fontoffset + fontcol + (OLED_NUMFONTCHAR*charwd*fontrow)])
				oled_writebyterow(x,row,curbyte, mode)
				fontrow = fontrow + 1
				row = row + 8
			fontcol = fontcol + 1
			x = x + 1
		ctr = ctr + 1
	return


def oled_power(turnon = True):
	if bus is None:
		return
	try:
		if turnon == True:
			oled_device.show()
		else:
			oled_device.hide()
	except:
		return


def oled_inverse(enable = True):
	# Not supported?
	return


def oled_fullwhite(enable = True):
	# Not supported?
	return



def oled_reset():
	return


