#!/bin/bash


if [ -e /boot/firmware/config.txt ] ; then
  FIRMWARE=/firmware
else
  FIRMWARE=
fi
CONFIG=/boot${FIRMWARE}/config.txt

CHECKGPIOMODE="libgpiod" # gpiod or rpigpio

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

pythonbin=/usr/bin/python3

#  Files
ARGONDOWNLOADSERVER=https://download.argon40.com
INSTALLATIONFOLDER=/etc/argon
basename="argononeups"
daemonname=$basename"d"

daemonupsservice=/lib/systemd/system/$daemonname.service
upsdaemonscript=$INSTALLATIONFOLDER/$daemonname.py

rtcdaemonname="argonupsrtcd"

daemonrtcservice=/lib/systemd/system/$rtcdaemonname.service
rtcdaemonscript=$INSTALLATIONFOLDER/$rtcdaemonname.py


requireinstall=0
newmode=0
echo "-----------------------------------"
echo " Argon Industria UPS Configuration"
echo "-----------------------------------"
if [ ! -f "$upsdaemonscript" ]
then
	echo "Install Argon Industria UPS Tools"
	echo -n "Press Y to continue:"
	read -n 1 confirm
	echo

	if [ "$confirm" = "y" ]
	then
		confirm="Y"
	fi

	if [ "$confirm" != "Y" ]
	then
		echo "Cancelled"
		exit
	fi

	requireinstall=1
	newmode=3	# Reinstall

fi


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

UPSCMDFILE="/dev/shm/upscmd.txt"
UPSSTATUSFILE="/dev/shm/upslog.txt"
rtcconfigscript=$INSTALLATIONFOLDER/argonups-rtcconfig.sh

if [ -f "$UPSSTATUSFILE" ]
then
#	cat $UPSSTATUSFILE
	sudo $pythonbin $rtcdaemonscript GETBATTERY
fi


loopflag=1
while [ $loopflag -eq 1 ]
do
	if [ $requireinstall -eq 0 ]
	then
		echo
		echo "Select option:"
		echo "  1. UPS Battery Status"
		echo "  2. Configure RTC and/or Schedule"
		echo "  3. Reinstall UPS Tools"
		echo "  4. Uninstall UPS Tools"
		echo ""
		echo "  0. Back"

		echo -n "Enter Number (0-4):"

		newmode=$( get_number )
	fi
	if [[ $newmode -ge 0 && $newmode -le 4 ]]
	then
		if [ $newmode -eq 1 ]
		then
			sudo $pythonbin $rtcdaemonscript GETBATTERY
			#if [ -f "$UPSSTATUSFILE" ]
			#then
			#	cat $UPSSTATUSFILE
			#else
			#	echo "Unable to retrieve status"
			#fi
		elif [ $newmode -eq 2 ]
		then
			$rtcconfigscript "argonupsrtc"
			#TMPTIMESTR=`date +"%Y%d%m%H%M%S"`
			#TMPDATASTR=`date +"%Y %m %d %H %M %S"`

			#echo "$TMPTIMESTR" > $UPSCMDFILE
			#echo "3 $TMPDATASTR" >> $UPSCMDFILE
		elif [ $newmode -eq 3 ]
		then
			# Start installation
			if [ ! -d "$INSTALLATIONFOLDER/ups" ]
			then
				sudo mkdir $INSTALLATIONFOLDER/ups
			fi


			rtcconfigfile=/etc/argonupsrtc.conf
			# Generate default RTC config file if non-existent
			if [ ! -f $rtcconfigfile ]; then
				sudo touch $rtcconfigfile
				sudo chmod 666 $rtcconfigfile

				echo '#' >> $rtcconfigfile
				echo '# Argon RTC Configuration' >> $rtcconfigfile
				echo '#' >> $rtcconfigfile
			fi

			for iconfile in battery_0 battery_2 battery_4 battery_charging battery_unknown battery_1 battery_3 battery_alert battery_plug
			do
				sudo wget $ARGONDOWNLOADSERVER/ups/${iconfile}.png -O $INSTALLATIONFOLDER/ups/${iconfile}.png --quiet
			done

			sudo wget $ARGONDOWNLOADSERVER/ups/upsimg.tar.gz -O $INSTALLATIONFOLDER/ups/upsimg.tar.gz --quiet
			sudo tar xfz $INSTALLATIONFOLDER/ups/upsimg.tar.gz -C $INSTALLATIONFOLDER/ups/
			sudo rm -Rf $INSTALLATIONFOLDER/ups/upsimg.tar.gz

			# Desktop Icon
			destfoldername=$USERNAME
			if [ -z "$destfoldername" ]
			then
				destfoldername=$USER
			fi
			if [ -z "$destfoldername" ]
			then
				destfoldername="pi"
			fi

			shortcutfile="/home/$destfoldername/Desktop/argonone-ups.desktop"
			if [ -d "/home/$destfoldername/Desktop" ]
			then
				terminalcmd="lxterminal --working-directory=/home/$destfoldername/ -t"
				if  [ -f "/home/$destfoldername/.twisteros.twid" ]
				then
					terminalcmd="xfce4-terminal --default-working-directory=/home/$destfoldername/ -T"
				fi

				echo "[Desktop Entry]" > $shortcutfile
				echo "Name=Argon UPS" >> $shortcutfile
				echo "Comment=Argon UPS" >> $shortcutfile
				echo "Icon=/etc/argon/ups/loading_0.png" >> $shortcutfile
				echo 'Exec='$terminalcmd' "Argon UPS" -e "'$rtcconfigscript' argonupsrtc"' >> $shortcutfile
				echo "Type=Application" >> $shortcutfile
				echo "Encoding=UTF-8" >> $shortcutfile
				echo "Terminal=false" >> $shortcutfile
				echo "Categories=None;" >> $shortcutfile
				chmod 755 $shortcutfile
			fi

			# Stopped using default battery indicator
			## Build Kernel Module
			#sourcecodefolder=$INSTALLATIONFOLDER/tmp
			#buildfolder=$sourcecodefolder/build
			#if [ -d $sourcecodefolder ]
			#then
			#		sudo rm -rf $sourcecodefolder
			#fi
			#if [ "$CHECKPLATFORM" = "Ubuntu" ]
			#then
			#		sudo apt-get install build-essential
			#fi
			#sudo mkdir -p $buildfolder
			#sudo chmod -R 755 $buildfolder

			#FILELIST="COPYING Makefile argonbatteryicon.c"
			#for fname in $FILELIST
			#do
			#		sudo wget $ARGONDOWNLOADSERVER/modules/argonbatteryicon/$fname -O $buildfolder/#$fname --quiet
			#done

			## Start Build
			#cd $buildfolder/
			#sudo make
			#sudo cp "$buildfolder/argonbatteryicon.ko" "$INSTALLATIONFOLDER/ups/"

			## Cleanup
			#cd $INSTALLATIONFOLDER/
			#sudo rm -Rf "$sourcecodefolder"

			sudo wget $ARGONDOWNLOADSERVER/scripts/argononeupsd.py -O "$upsdaemonscript" --quiet
			sudo wget $ARGONDOWNLOADSERVER/scripts/argononeupsd.service -O "$daemonupsservice" --quiet
			sudo chmod 666 $daemonupsservice
			#echo "User=$destfoldername" >> "$daemonupsservice"
			#echo "Group=$destfoldername" >> "$daemonupsservice"

			sudo chmod 644 $daemonupsservice

			sudo wget $ARGONDOWNLOADSERVER/scripts/argoneon-rtcconfig.sh -O $rtcconfigscript --quiet
			sudo chmod 755 $rtcconfigscript

			sudo wget $ARGONDOWNLOADSERVER/scripts/argonrtc.py -O $INSTALLATIONFOLDER/argonrtc.py --quiet
			sudo wget $ARGONDOWNLOADSERVER/scripts/argonupsrtcd.py -O "$rtcdaemonscript" --quiet
			sudo wget $ARGONDOWNLOADSERVER/scripts/argonupsrtcd.service -O "$daemonrtcservice" --quiet
			sudo chmod 644 $daemonrtcservice

			if [ $requireinstall -eq 1 ]
			then
				requireinstall=0
				sudo systemctl enable "$daemonname.service"
				sudo systemctl start "$daemonname.service"

				sudo systemctl enable "$rtcdaemonname.service"
				sudo systemctl start "$rtcdaemonname.service"
			else
				sudo systemctl restart "$daemonname.service"
				sudo systemctl restart "$rtcdaemonname.service"
				loopflag=0
			fi
			# Serial I/O is here
			sudo systemctl restart argononed.service
		elif [ $newmode -eq 4 ]
		then
			sudo systemctl stop "$daemonname.service"
			sudo systemctl disable "$daemonname.service"
			sudo rm $daemonupsservice
			sudo rm $upsdaemonscript

			sudo systemctl stop "$rtcdaemonname.service"
			sudo systemctl disable "$rtcdaemonname.service"
			sudo rm $daemonrtcservice
			sudo rm $rtcdaemonscript

			sudo rm -R -f $INSTALLATIONFOLDER/ups

			echo "Uninstall Completed"
			loopflag=0
		else
			echo "Cancelled"
			loopflag=0
		fi
	fi
done


