#!/bin/bash

oledconfigfile=/etc/argoneonoled.conf

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

get_pagename() {
	if [ "$1" == "clock" ]
	then
		pagename="Current Date/Time"
	elif [ "$1" == "cpu" ]
	then
		pagename="CPU Utilization"
	elif [ "$1" == "storage" ]
	then
		pagename="Storage Utilization"
	elif [ "$1" == "ram" ]
	then
		pagename="Available RAM"
	elif [ "$1" == "temp" ]
	then
		pagename="CPU Temperature"
	elif [ "$1" == "ip" ]
	then
		pagename="IP Address"
	elif [ "$1" == "logo1v5" ]
	then
		pagename="Logo:One v5"
	else
		pagename="Invalid"
	fi
}

configure_pagelist () {
	pagemasterlist="logo1v5 clock cpu storage ram temp ip"
	newscreenlist="$1"
	pageloopflag=1
	while [ $pageloopflag -eq 1 ]
	do
		echo "--------------------------------"
		echo " OLED Pages "
		echo "--------------------------------"
		i=1
		for curpage in $newscreenlist
		do
			get_pagename $curpage
			echo "  $i. Remove $pagename"
			i=$((i+1))
		done
		if [ $i -eq 1 ]
		then
			echo " No page configured"
		fi
		echo
		echo "  $i. Add Page"
		echo
		echo "  0. Done"
		echo -n "Enter Number (0-$i):"

		cmdmode=$( get_number )
		if [ $cmdmode -eq 0 ]
		then
			pageloopflag=0
		elif [[ $cmdmode -eq $i ]]
		then

			echo "--------------------------------"
			echo " Choose Page to Add"
			echo "--------------------------------"
			echo
			i=1
			for curpage in $pagemasterlist
			do
				get_pagename $curpage
				echo "  $i. $pagename"
				i=$((i+1))
			done

			echo
			echo "  0. Cancel"
			echo -n "Enter Number (0-$i):"
			pagenum=$( get_number )
			if [[ $pagenum -ge 1 && $pagenum -le $i ]]
			then
				i=1
				for curpage in $pagemasterlist
				do
					if [ $i -eq $pagenum ]
					then
						if [ "$newscreenlist" == "" ]
						then
							newscreenlist="$curpage"
						else
							newscreenlist="$newscreenlist $curpage"
						fi
					fi
					i=$((i+1))
				done
			fi
		elif [[ $cmdmode -ge 1 && $cmdmode -lt $i ]]
		then
			tmpscreenlist=""
			i=1
			for curpage in $newscreenlist
			do
				if [ ! $i -eq $cmdmode ]
				then
					tmpscreenlist="$tmpscreenlist $curpage"
				fi
				i=$((i+1))
			done
			if [ "$tmpscreenlist" == "" ]
			then
				newscreenlist="$tmpscreenlist"
			else
				# Remove leading space
				newscreenlist="${tmpscreenlist:1}"
			fi
		fi
	done
}

saveconfig () {
	echo "#" > $oledconfigfile
	echo "# Argon OLED Configuration" >> $oledconfigfile
	echo "#" >> $oledconfigfile
	echo "enabled=$1" >> $oledconfigfile
	echo "switchduration=$2" >> $oledconfigfile
	echo "screensaver=$3" >> $oledconfigfile
	echo "screenlist=\"$4\"" >> $oledconfigfile
}

updateconfig=1
oledloopflag=1
while [ $oledloopflag -eq 1 ]
do
	if [ $updateconfig -eq 1 ]
	then
		. $oledconfigfile
	fi

	updateconfig=0
	if [ -z "$enabled" ]
	then
		enabled="Y"
		updateconfig=1
	fi

	if [ -z "$screenlist" ]
	then
		screenlist="ip cpu ram"
		updateconfig=1
	fi

	if [ -z "$screensaver" ]
	then
		screensaver=120
		updateconfig=1
	fi

	if [ -z "$switchduration" ]
	then
		switchduration=0
		updateconfig=1
	fi

	# Write default values to config file, daemon already uses default so no need to restart service
	if [ $updateconfig -eq 1 ]
	then
		saveconfig $enabled $switchduration $screensaver "$screenlist"
		updateconfig=0
	fi

	displaystring=": Manually"
	if [ $switchduration -gt 1 ]
	then
		displaystring="Every $switchduration secs"
	fi

	echo "-----------------------------"
	echo "Argon OLED Configuration Tool"
	echo "-----------------------------"
	echo "Choose from the list:"
	echo "  1. Switch Page $displaystring"
	echo "  2. Configure Pages"
	echo "  3. Turn OFF OLED Screen when unchanged after $screensaver secs"
	echo "  4. Enable OLED Pages: $enabled"
	echo
	echo "  0. Back"
	echo -n "Enter Number (0-3):"

	newmode=$( get_number )
	if [ $newmode -eq 0 ]
	then
		oledloopflag=0
	elif [ $newmode -eq 1 ]
	then
		echo
		echo -n "Enter # of Seconds (10-60, Manual if 0):"

		cmdmode=$( get_number )
		if [ $cmdmode -eq 0 ]
		then
			switchduration=0
			updateconfig=1
		elif [[ $cmdmode -ge 10 && $cmdmode -le 60 ]]
		then
			updateconfig=1
			switchduration=$cmdmode
		else
			echo
			echo "Invalid duration"
			echo
		fi
	elif [ $newmode -eq 3 ]
	then
		echo
		echo -n "Enter # of Seconds (60 or above, Manual if 0):"

		cmdmode=$( get_number )
		if [ $cmdmode -eq 0 ]
		then
			screensaver=0
			updateconfig=1
		elif [ $cmdmode -ge 60 ]
		then
			updateconfig=1
			screensaver=$cmdmode
		else
			echo
			echo "Invalid duration"
			echo
		fi
	elif [ $newmode -eq 2 ]
	then
		configure_pagelist "$screenlist"
		if [ ! "$screenlist" == "$newscreenlist" ]
		then
			screenlist="$newscreenlist"
			updateconfig=1
		fi
	elif [ $newmode -eq 4 ]
	then
		echo
		echo -n "Enable OLED Pages (Y/n)?:"
		read -n 1 confirm
		tmpenabled="$enabled"
		if [[ "$confirm" == "n" || "$confirm" == "N" ]]
		then
			tmpenabled="N"
		elif [[ "$confirm" == "y" || "$confirm" == "Y" ]]
		then
			tmpenabled="Y"
		else
			echo "Invalid response"
		fi
		if [ ! "$enabled" == "$tmpenabled" ]
		then
			enabled="$tmpenabled"
			updateconfig=1
		fi

	fi

	if [ $updateconfig -eq 1 ]
	then
		saveconfig $enabled $switchduration $screensaver "$screenlist"
		sudo systemctl restart argononed.service
	fi
done

echo
