#!/bin/bash

echo "*************"
echo " Argon Setup  "
echo "*************"


# Check time if need to 'fix'
NEEDSTIMESYNC=0
LOCALTIME=$(date -u +%s%N | cut -b1-10)
GLOBALTIME=$(curl -s 'http://worldtimeapi.org/api/ip.txt' | grep unixtime | cut -b11-20)
TIMEDIFF=$((GLOBALTIME-LOCALTIME))

# about 26hrs, max timezone difference
if [ $TIMEDIFF -gt 100000 ]
then
	NEEDSTIMESYNC=1
fi


argon_time_error() {
	echo "**********************************************"
	echo "* WARNING: Device time seems to be incorrect *"
	echo "* This may cause problems during setup.      *"
	echo "**********************************************"
	echo "Possible Network Time Protocol Server issue"
	echo "Try running the following to correct:"
    echo " curl -k https://download.argon40.com/tools/setntpserver.sh | bash"
}

if [ $NEEDSTIMESYNC -eq 1 ]
then
	argon_time_error
fi


# Helper variables
ARGONDOWNLOADSERVER=https://download.argon40.com

INSTALLATIONFOLDER=/etc/argon

versioninfoscript=$INSTALLATIONFOLDER/argon-versioninfo.sh

uninstallscript=$INSTALLATIONFOLDER/argon-uninstall.sh
shutdownscript=/lib/systemd/system-shutdown/argon-shutdown.sh
configscript=$INSTALLATIONFOLDER/argon-config
unitconfigscript=$INSTALLATIONFOLDER/argon-unitconfig.sh
blstrdacconfigscript=$INSTALLATIONFOLDER/argon-blstrdac.sh
statusdisplayscript=$INSTALLATIONFOLDER/argon-status.sh

setupmode="Setup"

if [ -f $configscript ]
then
	setupmode="Update"
	echo "Updating files"
else
	sudo mkdir $INSTALLATIONFOLDER
	sudo chmod 755 $INSTALLATIONFOLDER
fi

##########
# Start code lifted from raspi-config
# is_pifive, get_serial_hw and do_serial_hw based on raspi-config

if [ -e /boot/firmware/config.txt ] ; then
  FIRMWARE=/firmware
else
  FIRMWARE=
fi
CONFIG=/boot${FIRMWARE}/config.txt
TMPCONFIG=/dev/shm/argontmp.bak

set_config_var() {
    if ! grep -q -E "$1=$2" $3 ; then
      echo "$1=$2" | sudo tee -a $3 > /dev/null
    fi
}

is_pifive() {
  grep -q "^Revision\s*:\s*[ 123][0-9a-fA-F][0-9a-fA-F]4[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]$" /proc/cpuinfo
  return $?
}


get_serial_hw() {
  if is_pifive ; then
    if grep -q -E "dtparam=uart0=off" $CONFIG ; then
      echo 1
    elif grep -q -E "dtparam=uart0" $CONFIG ; then
      echo 0
    else
      echo 1
    fi
  else
    if grep -q -E "^enable_uart=1" $CONFIG ; then
      echo 0
    elif grep -q -E "^enable_uart=0" $CONFIG ; then
      echo 1
    elif [ -e /dev/serial0 ] ; then
      echo 0
    else
      echo 1
    fi
  fi
}

do_serial_hw() {
  if [ $1 -eq 0 ] ; then
    if is_pifive ; then
      set_config_var dtparam=uart0 on $CONFIG
    else
      set_config_var enable_uart 1 $CONFIG
    fi
  else
    if is_pifive ; then
      sudo sed $CONFIG -i -e "/dtparam=uart0.*/d"
    else
      set_config_var enable_uart 0 $CONFIG
    fi
  fi
}

# End code lifted from raspi-config
##########

# Reuse is_pifive, set_config_var
set_nvme_default() {
  if is_pifive ; then
    set_config_var dtparam nvme $CONFIG
    set_config_var dtparam=pciex1_gen 3 $CONFIG
  fi
}
set_maxusbcurrent() {
  if is_pifive ; then
    set_config_var max_usb_current 1 $CONFIG
  fi
}


argon_check_pkg() {
    RESULT=$(dpkg-query -W -f='${Status}\n' "$1" 2> /dev/null | grep "installed")

    if [ "" == "$RESULT" ]; then
        echo "NG"
    else
        echo "OK"
    fi
}

CHECKDEVICE="one"	# Hardcoded for argonone
# Check if has RTC
# Todo for multiple OS

#i2cdetect -y 1 | grep -q ' 51 '
#if [ $? -eq 0 ]
#then
#        CHECKDEVICE="eon"
#fi

CHECKGPIOMODE="libgpiod" # libgpiod or rpigpio

# Check if Raspbian, Ubuntu, others
CHECKPLATFORM="Others"
CHECKPLATFORMVERSION=""
CHECKPLATFORMVERSIONNUM=""
if [ -f "/etc/os-release" ]
then
	source /etc/os-release
	if [ "$ID" = "raspbian" ]
	then
		CHECKPLATFORM="Raspbian"
		CHECKPLATFORMVERSION=$VERSION_ID
	elif [ "$ID" = "debian" ]
	then
		# For backwards compatibility, continue using raspbian
		CHECKPLATFORM="Raspbian"
		CHECKPLATFORMVERSION=$VERSION_ID
	elif [ "$ID" = "ubuntu" ]
	then
		CHECKPLATFORM="Ubuntu"
		CHECKPLATFORMVERSION=$VERSION_ID
	fi
	echo ${CHECKPLATFORMVERSION} | grep -e "\." > /dev/null
	if [ $? -eq 0 ]
	then
		CHECKPLATFORMVERSIONNUM=`cut -d "." -f2 <<< $CHECKPLATFORMVERSION `
		CHECKPLATFORMVERSION=`cut -d "." -f1 <<< $CHECKPLATFORMVERSION `
	fi
fi

gpiopkg="python3-libgpiod"
if [ "$CHECKGPIOMODE" = "rpigpio" ]
then
	if [ "$CHECKPLATFORM" = "Raspbian" ]
	then
		gpiopkg="raspi-gpio python3-rpi.gpio"
	else
		gpiopkg="python3-rpi.gpio"
	fi
fi

if [ "$CHECKPLATFORM" = "Raspbian" ]
then
	if [ "$CHECKDEVICE" = "eon" ]
	then
		pkglist=($gpiopkg python3-smbus i2c-tools smartmontools)
	else
		pkglist=($gpiopkg python3-smbus i2c-tools)
	fi
else
	# Todo handle lgpio
	# Ubuntu has serial and i2c enabled
	if [ "$CHECKDEVICE" = "eon" ]
	then
		pkglist=($gpiopkg python3-smbus i2c-tools smartmontools)
	else
		pkglist=($gpiopkg python3-smbus i2c-tools)
	fi
fi

for curpkg in ${pkglist[@]}; do
	sudo apt-get install -y $curpkg
	RESULT=$(argon_check_pkg "$curpkg")
	if [ "NG" == "$RESULT" ]
	then
		echo "********************************************************************"
		echo "Please also connect device to the internet and restart installation."
		echo "********************************************************************"
		exit
	fi
done

# Ubuntu Mate for RPi has raspi-config too
command -v raspi-config &> /dev/null
if [ $? -eq 0 ]
then
	# Enable i2c and serial
	sudo raspi-config nonint do_i2c 0
	if [ ! "$CHECKDEVICE" = "fanhat" ]
	then

		if [ "$CHECKPLATFORM" = "Raspbian" ]
		then
			# bookworm raspi-config prompts user when configuring serial
			if [ $(get_serial_hw) -eq 1 ]; then
				do_serial_hw 0
			fi
		else
			sudo raspi-config nonint do_serial 2
		fi
	fi
fi

# Added to enabled NVMe for pi5
set_nvme_default

# Fan Setup
basename="argonone"
daemonname=$basename"d"
irconfigscript=$INSTALLATIONFOLDER/${basename}-ir
fanconfigscript=$INSTALLATIONFOLDER/${basename}-fanconfig.sh
eepromrpiscript="/usr/bin/rpi-eeprom-config"
eepromconfigscript=$INSTALLATIONFOLDER/${basename}-eepromconfig.py
powerbuttonscript=$INSTALLATIONFOLDER/$daemonname.py
unitconfigfile=/etc/argonunits.conf
daemonconfigfile=/etc/$daemonname.conf
daemonfanservice=/lib/systemd/system/$daemonname.service

daemonhddconfigfile=/etc/${daemonname}-hdd.conf


if [ -f "$eepromrpiscript" ]
then
	# EEPROM Config Script
	sudo wget $ARGONDOWNLOADSERVER/scripts/argon-rpi-eeprom-config-psu.py -O $eepromconfigscript --quiet
	sudo chmod 755 $eepromconfigscript
fi

# Fan Config Script
sudo wget $ARGONDOWNLOADSERVER/scripts/argonone-fanconfig.sh -O $fanconfigscript --quiet
sudo chmod 755 $fanconfigscript


# Fan Daemon/Service Files
sudo wget $ARGONDOWNLOADSERVER/scripts/argononed.py -O $powerbuttonscript --quiet
sudo wget $ARGONDOWNLOADSERVER/scripts/argononed.service -O $daemonfanservice --quiet
sudo chmod 644 $daemonfanservice

if [ ! "$CHECKDEVICE" = "fanhat" ]
then
	# IR Files
	sudo wget $ARGONDOWNLOADSERVER/scripts/argonone-irconfig.sh -O $irconfigscript --quiet
	sudo chmod 755 $irconfigscript

	if [ ! "$CHECKDEVICE" = "eon" ]
	then
		sudo wget $ARGONDOWNLOADSERVER/scripts/argon-blstrdac.sh -O $blstrdacconfigscript --quiet
		sudo chmod 755 $blstrdacconfigscript
	fi
fi

# Other utility scripts
sudo wget $ARGONDOWNLOADSERVER/scripts/argonstatus.py -O $INSTALLATIONFOLDER/argonstatus.py --quiet
sudo wget $ARGONDOWNLOADSERVER/scripts/argon-status.sh -O $statusdisplayscript --quiet
sudo chmod 755 $statusdisplayscript


sudo wget $ARGONDOWNLOADSERVER/scripts/argon-versioninfo.sh -O $versioninfoscript --quiet
sudo chmod 755 $versioninfoscript

sudo wget $ARGONDOWNLOADSERVER/scripts/argonsysinfo.py -O $INSTALLATIONFOLDER/argonsysinfo.py --quiet

sudo wget $ARGONDOWNLOADSERVER/scripts/argonregister.py -O $INSTALLATIONFOLDER/argonregister.py --quiet

sudo wget "$ARGONDOWNLOADSERVER/scripts/argonpowerbutton-${CHECKGPIOMODE}.py" -O $INSTALLATIONFOLDER/argonpowerbutton.py --quiet

sudo wget $ARGONDOWNLOADSERVER/scripts/argononed.py -O $powerbuttonscript --quiet

sudo wget $ARGONDOWNLOADSERVER/scripts/argon-unitconfig.sh -O $unitconfigscript --quiet
sudo chmod 755 $unitconfigscript


# Generate default Fan config file if non-existent
if [ ! -f $daemonconfigfile ]; then
	sudo touch $daemonconfigfile
	sudo chmod 666 $daemonconfigfile

	echo '#' >> $daemonconfigfile
	echo '# Argon Fan Speed Configuration (CPU)' >> $daemonconfigfile
	echo '#' >> $daemonconfigfile
	echo '55=30' >> $daemonconfigfile
	echo '60=55' >> $daemonconfigfile
	echo '65=100' >> $daemonconfigfile
fi

if [ "$CHECKDEVICE" = "eon" ]
then
	if [ ! -f $daemonhddconfigfile ]; then
		sudo touch $daemonhddconfigfile
		sudo chmod 666 $daemonhddconfigfile

		echo '#' >> $daemonhddconfigfile
		echo '# Argon Fan Speed Configuration (HDD)' >> $daemonhddconfigfile
		echo '#' >> $daemonhddconfigfile
		echo '35=30' >> $daemonhddconfigfile
		echo '40=55' >> $daemonhddconfigfile
		echo '45=100' >> $daemonhddconfigfile
	fi
fi

# Generate default Unit config file if non-existent
if [ ! -f $unitconfigfile ]; then
	sudo touch $unitconfigfile
	sudo chmod 666 $unitconfigfile

	echo '#' >> $unitconfigfile
fi


if [ "$CHECKDEVICE" = "eon" ]
then
	# RTC Setup
	basename="argoneon"
	daemonname=$basename"d"

	rtcconfigfile=/etc/argoneonrtc.conf
	rtcconfigscript=$INSTALLATIONFOLDER/${basename}-rtcconfig.sh
	daemonrtcservice=/lib/systemd/system/$daemonname.service
	rtcdaemonscript=$INSTALLATIONFOLDER/$daemonname.py

	oledconfigscript=$INSTALLATIONFOLDER/${basename}-oledconfig.sh
	oledlibscript=$INSTALLATIONFOLDER/${basename}oled.py
	oledconfigfile=/etc/argoneonoled.conf

	# Generate default RTC config file if non-existent
	if [ ! -f $rtcconfigfile ]; then
		sudo touch $rtcconfigfile
		sudo chmod 666 $rtcconfigfile

		echo '#' >> $rtcconfigfile
		echo '# Argon RTC Configuration' >> $rtcconfigfile
		echo '#' >> $rtcconfigfile
	fi
	# Generate default OLED config file if non-existent
	if [ ! -f $oledconfigfile ]; then
		sudo touch $oledconfigfile
		sudo chmod 666 $oledconfigfile

		echo '#' >> $oledconfigfile
		echo '# Argon OLED Configuration' >> $oledconfigfile
		echo '#' >> $oledconfigfile
		echo 'switchduration=30' >> $oledconfigfile
		echo 'screenlist="clock cpu storage raid ram temp ip"' >> $oledconfigfile
	fi


	# RTC Config Script
	sudo wget $ARGONDOWNLOADSERVER/scripts/argoneon-rtcconfig.sh -O $rtcconfigscript --quiet
	sudo chmod 755 $rtcconfigscript

	# RTC Daemon/Service Files
	sudo wget $ARGONDOWNLOADSERVER/scripts/argoneond.py -O $rtcdaemonscript --quiet
	sudo wget $ARGONDOWNLOADSERVER/scripts/argoneond.service -O $daemonrtcservice --quiet
	sudo wget $ARGONDOWNLOADSERVER/scripts/argoneonoled.py -O $oledlibscript --quiet
	sudo chmod 644 $daemonrtcservice

	# OLED Config Script
	sudo wget $ARGONDOWNLOADSERVER/scripts/argoneon-oledconfig.sh -O $oledconfigscript --quiet
	sudo chmod 755 $oledconfigscript


	if [ ! -d $INSTALLATIONFOLDER/oled ]
	then
		sudo mkdir $INSTALLATIONFOLDER/oled
	fi

	for binfile in font8x6 font16x12 font32x24 font64x48 font16x8 font24x16 font48x32 bgdefault bgram bgip bgtemp bgcpu bgraid bgstorage bgtime
	do
		sudo wget $ARGONDOWNLOADSERVER/oled/${binfile}.bin -O $INSTALLATIONFOLDER/oled/${binfile}.bin --quiet
	done
fi


# Argon Uninstall Script
sudo wget $ARGONDOWNLOADSERVER/scripts/argon-uninstall.sh -O $uninstallscript --quiet
sudo chmod 755 $uninstallscript

# Argon Shutdown script
sudo wget $ARGONDOWNLOADSERVER/scripts/argon-shutdown.sh -O $shutdownscript --quiet
sudo chmod 755 $shutdownscript

# Argon Config Script
if [ -f $configscript ]; then
	sudo rm $configscript
fi
sudo touch $configscript

# To ensure we can write the following lines
sudo chmod 666 $configscript

echo '#!/bin/bash' >> $configscript

echo 'echo "--------------------------"' >> $configscript
echo 'echo "Argon Configuration Tool"' >> $configscript
echo "$versioninfoscript simple" >> $configscript
echo 'echo "--------------------------"' >> $configscript

echo 'get_number () {' >> $configscript
echo '	read curnumber' >> $configscript
echo '	if [ -z "$curnumber" ]' >> $configscript
echo '	then' >> $configscript
echo '		echo "-2"' >> $configscript
echo '		return' >> $configscript
echo '	elif [[ $curnumber =~ ^[+-]?[0-9]+$ ]]' >> $configscript
echo '	then' >> $configscript
echo '		if [ $curnumber -lt 0 ]' >> $configscript
echo '		then' >> $configscript
echo '			echo "-1"' >> $configscript
echo '			return' >> $configscript
echo '		elif [ $curnumber -gt 100 ]' >> $configscript
echo '		then' >> $configscript
echo '			echo "-1"' >> $configscript
echo '			return' >> $configscript
echo '		fi	' >> $configscript
echo '		echo $curnumber' >> $configscript
echo '		return' >> $configscript
echo '	fi' >> $configscript
echo '	echo "-1"' >> $configscript
echo '	return' >> $configscript
echo '}' >> $configscript
echo '' >> $configscript

echo 'mainloopflag=1' >> $configscript
echo 'while [ $mainloopflag -eq 1 ]' >> $configscript
echo 'do' >> $configscript
echo '	echo' >> $configscript
echo '	echo "Choose Option:"' >> $configscript
echo '	echo "  1. Configure Fan"' >> $configscript

blstrdacoption=0

if [ "$CHECKDEVICE" = "fanhat" ]
then
	uninstalloption="4"
else
	echo '	echo "  2. Configure IR"' >> $configscript
	if [ "$CHECKDEVICE" = "eon" ]
	then
		# ArgonEON Has RTC
		echo '	echo "  3. Configure RTC and/or Schedule"' >> $configscript
		echo '	echo "  4. Configure OLED"' >> $configscript
		uninstalloption="7"
	else
		uninstalloption="6"
		blstrdacoption=$(($uninstalloption-3))
		echo "	echo \"  $blstrdacoption. Configure BLSTR DAC (v3 only)\"" >> $configscript
	fi
fi

unitsoption=$(($uninstalloption-2))
echo "	echo \"  $unitsoption. Configure Units\"" >> $configscript
statusoption=$(($uninstalloption-1))
echo "	echo \"  $statusoption. System Information\"" >> $configscript

echo "	echo \"  $uninstalloption. Uninstall\"" >> $configscript
echo '	echo ""' >> $configscript
echo '	echo "  0. Exit"' >> $configscript
echo "	echo -n \"Enter Number (0-$uninstalloption):\"" >> $configscript
echo '	newmode=$( get_number )' >> $configscript


echo '	if [ $newmode -eq 0 ]' >> $configscript
echo '	then' >> $configscript
echo '		echo "Thank you."' >> $configscript
echo '		mainloopflag=0' >> $configscript
echo '	elif [ $newmode -eq 1 ]' >> $configscript
echo '	then' >> $configscript

if [ "$CHECKDEVICE" = "eon" ]
then
	echo '		echo "Choose Triggers:"' >> $configscript
	echo '		echo "  1. CPU Temperature"' >> $configscript
	echo '		echo "  2. HDD Temperature"' >> $configscript
	echo '		echo ""' >> $configscript
	echo '		echo "  0. Cancel"' >> $configscript
	echo "		echo -n \"Enter Number (0-2):\"" >> $configscript
	echo '		submode=$( get_number )' >> $configscript

	echo '		if [ $submode -eq 1 ]' >> $configscript
	echo '		then' >> $configscript
	echo "			$fanconfigscript" >> $configscript
	echo '			mainloopflag=0' >> $configscript
	echo '		elif [ $submode -eq 2 ]' >> $configscript
	echo '		then' >> $configscript
	echo "			$fanconfigscript hdd" >> $configscript
	echo '			mainloopflag=0' >> $configscript
	echo '		fi' >> $configscript

else
	echo "		$fanconfigscript" >> $configscript
	echo '		mainloopflag=0' >> $configscript
fi

if [ ! "$CHECKDEVICE" = "fanhat" ]
then
	echo '	elif [ $newmode -eq 2 ]' >> $configscript
	echo '	then' >> $configscript
	echo "		$irconfigscript" >> $configscript
	echo '		mainloopflag=0' >> $configscript

	if [ "$CHECKDEVICE" = "eon" ]
	then
		echo '	elif [ $newmode -eq 3 ]' >> $configscript
		echo '	then' >> $configscript
		echo "		$rtcconfigscript" >> $configscript
		echo '		mainloopflag=0' >> $configscript
		echo '	elif [ $newmode -eq 4 ]' >> $configscript
		echo '	then' >> $configscript
		echo "		$oledconfigscript" >> $configscript
		echo '		mainloopflag=0' >> $configscript
	fi

	if [ $blstrdacoption -gt 0 ]
	then
		echo "	elif [ \$newmode -eq $blstrdacoption ]" >> $configscript
		echo '	then' >> $configscript
		echo "		$blstrdacconfigscript" >> $configscript
		echo '		mainloopflag=0' >> $configscript
	fi
fi

echo "	elif [ \$newmode -eq $unitsoption ]" >> $configscript
echo '	then' >> $configscript
echo "		$unitconfigscript" >> $configscript
echo '		mainloopflag=0' >> $configscript

echo "	elif [ \$newmode -eq $statusoption ]" >> $configscript
echo '	then' >> $configscript
echo "		$statusdisplayscript" >> $configscript

echo "	elif [ \$newmode -eq $uninstalloption ]" >> $configscript
echo '	then' >> $configscript
echo "		$uninstallscript" >> $configscript
echo '		mainloopflag=0' >> $configscript
echo '	fi' >> $configscript
echo 'done' >> $configscript

sudo chmod 755 $configscript

# Desktop Icon
shortcutfile="/home/pi/Desktop/argonone-config.desktop"
if [ "$CHECKPLATFORM" = "Raspbian" ] && [ -d "/home/pi/Desktop" ]
then
	terminalcmd="lxterminal --working-directory=/home/pi/ -t"
	if  [ -f "/home/pi/.twisteros.twid" ]
	then
		terminalcmd="xfce4-terminal --default-working-directory=/home/pi/ -T"
	fi
	imagefile=ar1config.png
	if [ "$CHECKDEVICE" = "eon" ]
	then
		imagefile=argoneon.png
	fi
	sudo wget http://download.argon40.com/$imagefile -O /usr/share/pixmaps/$imagefile --quiet
	if [ -f $shortcutfile ]; then
		sudo rm $shortcutfile
	fi

	# Create Shortcuts
	echo "[Desktop Entry]" > $shortcutfile
	echo "Name=Argon Configuration" >> $shortcutfile
	echo "Comment=Argon Configuration" >> $shortcutfile
	echo "Icon=/usr/share/pixmaps/$imagefile" >> $shortcutfile
	echo 'Exec='$terminalcmd' "Argon Configuration" -e '$configscript >> $shortcutfile
	echo "Type=Application" >> $shortcutfile
	echo "Encoding=UTF-8" >> $shortcutfile
	echo "Terminal=false" >> $shortcutfile
	echo "Categories=None;" >> $shortcutfile
	chmod 755 $shortcutfile
fi

configcmd="$(basename -- $configscript)"

if [ "$setupmode" = "Setup" ]
then
	if [ -f "/usr/bin/$configcmd" ]
	then
		sudo rm /usr/bin/$configcmd
	fi
	sudo ln -s $configscript /usr/bin/$configcmd

	if [ "$CHECKDEVICE" = "one" ]
	then
		sudo ln -s $configscript /usr/bin/argonone-config
		sudo ln -s $uninstallscript /usr/bin/argonone-uninstall
		sudo ln -s $irconfigscript /usr/bin/argonone-ir
	elif [ "$CHECKDEVICE" = "fanhat" ]
	then
		sudo ln -s $configscript /usr/bin/argonone-config
		sudo ln -s $uninstallscript /usr/bin/argonone-uninstall
	fi

	# Enable and Start Service(s)
	sudo systemctl daemon-reload
	sudo systemctl enable argononed.service
	sudo systemctl start argononed.service
	if [ "$CHECKDEVICE" = "eon" ]
	then
		sudo systemctl enable argoneond.service
		sudo systemctl start argoneond.service
	fi
else
	sudo systemctl daemon-reload
	sudo systemctl restart argononed.service
	if [ "$CHECKDEVICE" = "eon" ]
	then
		sudo systemctl restart argoneond.service
	fi
fi

if [ "$CHECKPLATFORM" = "Raspbian" ]
then
	if [ -f "$eepromrpiscript" ]
	then
		sudo apt-get update && sudo apt-get upgrade -y
		sudo rpi-eeprom-update
		# EEPROM Config Script
		sudo $eepromconfigscript
	fi
else
	echo "WARNING: EEPROM not updated.  Please run this under Raspberry Pi OS"
fi

set_maxusbcurrent


echo "*********************"
echo "  $setupmode Completed "
echo "*********************"
$versioninfoscript
echo
echo "Use '$configcmd' to configure device"
echo



if [ $NEEDSTIMESYNC -eq 1 ]
then
	argon_time_error
fi

