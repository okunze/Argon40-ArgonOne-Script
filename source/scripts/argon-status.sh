#!/bin/bash


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

INSTALLATIONFOLDER=/etc/argon
pythonbin="sudo /usr/bin/python3"
argonstatusscript=$INSTALLATIONFOLDER/argonstatus.py
argondashboardscript=$INSTALLATIONFOLDER/argondashboard.py
argononefanscript=$INSTALLATIONFOLDER/argononed.py
argoneonrtcscript=$INSTALLATIONFOLDER/argoneond.py


echo "--------------------------"
echo " Argon System Information"
echo "--------------------------"


loopflag=1
while [ $loopflag -eq 1 ]
do
	echo
	echo "  1. Temperatures"
	echo "  2. CPU Utilization"
	echo "  3. Storage Capacity"
	echo "  4. RAM"
	echo "  5. IP Address"
	lastoption=5
	if [ -f $argononefanscript ]
	then
		echo "  6. Fan Speed"
		lastoption=6
	fi
	if [ -f "$argoneonrtcscript" ]
	then
		echo "  7. RTC Schedules"
		echo "  8. RAID"
		lastoption=8
	fi
	lastoption=$((lastoption + 1))
	echo "  ${lastoption}. Dashboard"
	echo
	echo "  0. Back"
	echo -n "Enter Number (0-${lastoption}):"

	newmode=$( get_number )
	if [ $newmode -eq 0 ]
	then
		loopflag=0
	elif [ $newmode -gt 0 ] && [ $newmode -le $lastoption ]
	then
		echo "--------------------------"
		if [ $newmode -eq $lastoption ]
		then
			$pythonbin $argondashboardscript
		elif [ $newmode -eq 1 ]
		then
			$pythonbin $argonstatusscript "temperature"
		elif [ $newmode -eq 2 ]
		then
			$pythonbin $argonstatusscript "cpu usage"
		elif [ $newmode -eq 3 ]
		then
			$pythonbin $argonstatusscript "storage"
		elif [ $newmode -eq 4 ]
		then
			$pythonbin $argonstatusscript "ram"
		elif [ $newmode -eq 5 ]
		then
			$pythonbin $argonstatusscript "ip"
		elif [ $newmode -eq 6 ]
		then
			$pythonbin $argonstatusscript "temperature" "fan configuration" "fan speed"
		elif [ $newmode -eq 7 ]
		then
			$pythonbin $argoneonrtcscript GETSCHEDULELIST
		elif [ $newmode -eq 8 ]
		then
			$pythonbin $argonstatusscript "raid"
		fi
		echo "--------------------------"
	fi
done

