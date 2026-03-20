#!/bin/bash

echo "*************"
echo " Argon Setup  "
echo "*************"

# Helper variables
ARGONDOWNLOADSERVER=https://download.argon40.com

eepromrpiscript="/usr/bin/rpi-eeprom-config"
eepromconfigscript=/dev/shm/argon-eeprom.py

# Check if Raspbian, Ubuntu, others
CHECKPLATFORM="Others"
if [ -f "/etc/os-release" ]
then
	source /etc/os-release
	if [ "$ID" = "raspbian" ]
	then
		CHECKPLATFORM="Raspbian"
	elif [ "$ID" = "debian" ]
	then
		# For backwards compatibility, continue using raspbian
		CHECKPLATFORM="Raspbian"
	elif [ "$ID" = "ubuntu" ]
	then
		CHECKPLATFORM="Ubuntu"
	fi
fi

# Check if original eeprom script exists before running
if [ "$CHECKPLATFORM" = "Raspbian" ]
then
	if [  -f "$eepromrpiscript" ]
	then
		sudo apt-get update && sudo apt-get upgrade -y
		sudo rpi-eeprom-update
		# EEPROM Config Script
		sudo wget $ARGONDOWNLOADSERVER/scripts/argon-rpi-eeprom-config-default.py -O $eepromconfigscript --quiet
		sudo chmod 755 $eepromconfigscript
		sudo $eepromconfigscript
	fi
else
	echo "Please run this under Raspberry Pi OS"
fi
