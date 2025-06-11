#!/bin/bash

unitconfigfile=/etc/argonunits.conf

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

saveconfig () {
	echo "#" > $unitconfigfile
	echo "# Argon Unit Configuration" >> $unitconfigfile
	echo "#" >> $unitconfigfile
	echo "temperature=$1" >> $unitconfigfile
}

updateconfig=1
unitloopflag=1
while [ $unitloopflag -eq 1 ]
do
	if [ $updateconfig -eq 1 ]
	then
		. $unitconfigfile
	fi

	updateconfig=0
	if [ -z "$temperature" ]
	then
		temperature="C"
		updateconfig=1
	fi

	# Write default values to config file, daemon already uses default so no need to restart service
	if [ $updateconfig -eq 1 ]
	then
		saveconfig $temperature
		updateconfig=0
	fi


	echo "-----------------------------"
	echo "Argon Display Units"
	echo "-----------------------------"
	echo "Choose from the list:"
	echo "  1. Temperature: $temperature"
	echo
	echo "  0. Back"
	echo -n "Enter Number (0-1):"

	newmode=$( get_number )
	if [ $newmode -eq 0 ]
	then
		unitloopflag=0
	elif [ $newmode -eq 1 ]
	then
		echo
		echo "-----------------------------"
		echo "Temperature Display"
		echo "-----------------------------"
		echo "Choose from the list:"
		echo "  1. Celsius"
		echo "  2. Fahrenheit"
		echo
		echo "  0. Cancel"
		echo -n "Enter Number (0-2):"

		cmdmode=$( get_number )
		if [ $cmdmode -eq 1 ]
		then
			temperature="C"
			updateconfig=1
		elif [ $cmdmode -eq 2 ]
		then
			temperature="F"
			updateconfig=1
		fi
	fi

	if [ $updateconfig -eq 1 ]
	then
		saveconfig $temperature
		sudo systemctl restart argononed.service
	fi
done

echo
