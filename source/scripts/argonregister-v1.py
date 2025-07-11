#!/usr/bin/python3

#
# Argon Register Helper methods
# Same as argonregister, but no support for new register commands
#

import time
import smbus

# I2C Addresses
ADDR_ARGONONEFAN=0x1a
ADDR_ARGONONEREG=ADDR_ARGONONEFAN

# ARGONONEREG Addresses
ADDR_ARGONONEREG_DUTYCYCLE=0x80
ADDR_ARGONONEREG_FW=0x81
ADDR_ARGONONEREG_IR=0x82
ADDR_ARGONONEREG_CTRL=0x86

# Initialize bus
def argonregister_initializebusobj():
	try:
		return smbus.SMBus(1)
	except Exception:
		try:
			# Older version
			return smbus.SMBus(0)
		except Exception:
			print("Unable to detect i2c")
			return None


# Checks if the FW supports control registers
def argonregister_checksupport(busobj):
	return False

def argonregister_getbyte(busobj, address):
	if busobj is None:
		return 0
	return busobj.read_byte_data(ADDR_ARGONONEREG, address)

def argonregister_setbyte(busobj, address, bytevalue):
	if busobj is None:
		return
	busobj.write_byte_data(ADDR_ARGONONEREG,address,bytevalue)
	time.sleep(1)

def argonregister_getfanspeed(busobj, regsupport=None):
	return 0

def argonregister_setfanspeed(busobj, newspeed, regsupport=None):
	if busobj is None:
		return

	if newspeed > 100:
		newspeed = 100
	elif newspeed < 0:
		newspeed = 0

	busobj.write_byte(ADDR_ARGONONEFAN,newspeed)
	time.sleep(1)

def argonregister_signalpoweroff(busobj):
	if busobj is None:
		return

	busobj.write_byte(ADDR_ARGONONEFAN,0xFF)

def argonregister_setircode(busobj, vallist):
	if busobj is None:
		return

	busobj.write_i2c_block_data(ADDR_ARGONONEREG, ADDR_ARGONONEREG_IR, vallist)
