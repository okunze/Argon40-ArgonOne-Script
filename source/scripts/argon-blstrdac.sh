#!/bin/bash


if [ -e /boot/firmware/config.txt ] ; then
  FIRMWARE=/firmware
else
  FIRMWARE=
fi
CONFIG=/boot${FIRMWARE}/config.txt

# Check if Raspbian
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
	fi
fi


echo "------------------------------------"
echo " Argon BLSTR DAC Configuration Tool"
echo "------------------------------------"

get_number () {
	read curnumber
	if [ -z "$curnumber" ]
	then
		echo "-2"
		return
	elif [[ $curnumber =~ ^[+-]?[0-9]+$ ]]
	then
		if [ $curnumber -lt 0 ]
		then
			echo "-1"
			return
		elif [ $curnumber -gt 100 ]
		then
			echo "-1"
			return
		fi
		echo $curnumber
		return
	fi
	echo "-1"
	return
}

irexecrcfile=/etc/lirc/irexec.lircrc
irexecshfile=/etc/argon/argonirexec
irdecodefile=/etc/argon/argonirdecoder
kodiuserdatafolder="$HOME/.kodi/userdata"
kodilircmapfile="$kodiuserdatafolder/Lircmap.xml"
remotemode=""
needinstallation=1


CONFIGSETTING="dtoverlay=hifiberry-dacplus,slave"

if grep -q -E "$CONFIGSETTING" $CONFIG
then
	# Already installed
	needinstallation=0
fi


loopflag=1
while [ $loopflag -eq 1 ]
do
	echo
	echo "Select option:"
	if [ $needinstallation -eq 1 ]
	then
		echo "  1. Enable BLSTR DAC"
		echo "  2. Cancel"
		echo -n "Enter Number (1-2):"
	else
		echo "  1. Select audio configuration"
		echo "  2. Disable BLSTR DAC"
		echo "  3. Cancel"
		echo -n "Enter Number (1-3):"
	fi
	newmode=$( get_number )
	if [[ $newmode -ge 1 && $newmode -le 3 ]]
	then
		if [[ $needinstallation -eq 1 && $newmode -ge 3 ]]
		then
			# Invalid option
			loopflag=1
			# Uninstall
		else
			loopflag=0
			if [ $needinstallation -eq 1 ]
			then
				if [ $newmode -eq 2 ]
				then
					# Cancel
					newmode=4
				fi
			else
				if [ $newmode -eq 1 ]
				then
					# Audio Conf
					newmode=3
				fi

			fi


		fi
	fi
done

needrestart=0

echo
if [ $newmode -eq 2 ]
then
	# Uninstall
	blstrdactmpconfigfile=/dev/shm/argonblstrdacconfig.txt

	cat $CONFIG | grep -v "$CONFIGSETTING" > $blstrdactmpconfigfile
	cat $blstrdactmpconfigfile | sudo tee $CONFIG 1> /dev/null
	sudo rm $blstrdactmpconfigfile

	echo "Uninstall Completed"
	echo

	needrestart=1

elif [ $newmode -eq 3 ]
then
	# Audio Conf

	loopflag=1
	while [ $loopflag -eq 1 ]
	do
		echo
		echo "Select audio configuration:"
		echo "  1. PulseAudio"
		echo "  2. Pipewire"
		echo "  3. Cancel"
		echo -n "Enter Number (1-3):"

		newmode=$( get_number )
		if [[ $newmode -ge 1 && $newmode -le 3 ]]
		then
			loopflag=0
		fi
	done

	if [[ $newmode -ge 1 && $newmode -le 2 ]]
	then
		sudo raspi-config nonint do_audioconf $newmode
	else
		echo "Cancelled"
	fi

elif [ $newmode -eq 1 ]
then
	# Install

	echo "$CONFIGSETTING" | sudo tee -a $CONFIG 1> /dev/null

	#sudo raspi-config nonint do_audioconf 1
	#systemctl --global -q disable pipewire-pulse
	#systemctl --global -q disable wireplumber
	#systemctl --global -q enable pulseaudio
	#if [ -e /etc/alsa/conf.d/99-pipewire-default.conf ] ; then
	#	rm /etc/alsa/conf.d/99-pipewire-default.conf
	#fi

	echo "Please run configuration and choose different audio configuration if there are problems"

	needrestart=1
else
	echo "Cancelled"
	#exit
fi


echo
#echo "Thank you."
if [ $needrestart -eq 1 ]
then
	echo "Changes should take after reboot."
fi

