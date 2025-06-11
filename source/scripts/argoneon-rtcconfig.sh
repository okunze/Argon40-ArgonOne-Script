#!/bin/bash

if [ -z "$1" ]
then
	rtcdaemonname=argoneond
	rtcconfigfile=/etc/argoneonrtc.conf
else
	rtcdaemonname=${1}d
	rtcconfigfile=/etc/${1}.conf
fi


pythonbin=/usr/bin/python3
argonrtcscript=/etc/argon/$rtcdaemonname.py

CHECKPLATFORM="Others"
# Check if Raspbian
grep -q -F 'Raspbian' /etc/os-release &> /dev/null
if [ $? -eq 0 ]
then
	CHECKPLATFORM="Raspbian"
else
	# Ubuntu needs elevated access for SMBus
	pythonbin="sudo /usr/bin/python3"
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

configure_schedule () {
	scheduleloopflag=1
	while [ $scheduleloopflag -eq 1 ]
	do
		echo "--------------------------------"
		echo " Configure Schedule "
		echo "--------------------------------"
		echo "  1. Add Schedule"
		echo "  or"
		echo "  Remove Schedule"
		$pythonbin $argonrtcscript GETSCHEDULELIST
		echo
		echo " 99. Main Menu"
		echo "  0. Back"
		#echo "NOTE: You can also edit $rtcconfigfile directly"
		echo -n "Enter Number:"

		newmode=$( get_number )
		if [ $newmode -eq 0 ]
		then
			scheduleloopflag=0
		elif [ $newmode -eq 99 ]
		then
			scheduleloopflag=0
			rtcloopflag=2
		elif [ $newmode -eq 1 ]
		then
			configure_newschedule
		elif [ $newmode -gt 1 ]
		then
			echo "CONFIRM SCHEDULE REMOVAL"
			$pythonbin $argonrtcscript SHOWSCHEDULE $newmode
			echo -n "Press Y to remove schedule #$newmode:"
			read -n 1 confirm
			if [ "$confirm" = "y" ]
			then
				confirm="Y"
			fi
			if [ "$confirm" = "Y" ]
			then
				$pythonbin $argonrtcscript REMOVESCHEDULE $newmode
				sudo systemctl restart $rtcdaemonname.service
			fi
			echo ""
		fi
	done
}

configure_newschedule () {

	cmdmode=1
	hour=8
	minute=0
	minuteprefix=":0"
	dayidx=0
	repeat=1

	subloopflag=1
	while [ $subloopflag -eq 1 ]
	do
		minuteprefix=":0"
		if [ $minute -ge 10 ]
		then
			minuteprefix=":"
		fi

		typestr="Shutdown"
		if [ $cmdmode -eq 1 ]
		then
			typestr="Startup"
		fi

		daystr="Daily"
		if [ $dayidx -eq 1 ]
		then
			daystr="Mon"
		elif [ $dayidx -eq 2 ]
		then
			daystr="Tue"
		elif [ $dayidx -eq 3 ]
		then
			daystr="Wed"
		elif [ $dayidx -eq 4 ]
		then
			daystr="Thu"
		elif [ $dayidx -eq 5 ]
		then
			daystr="Fri"
		elif [ $dayidx -eq 6 ]
		then
			daystr="Sat"
		elif [ $dayidx -eq 7 ]
		then
			daystr="Sun"
		fi

		repeatstr="Yes"
		if [ $repeat -eq 0 ]
		then
			repeatstr="Once"
			if [ $dayidx -eq 0 ]
			then
				daystr="Next Occurence"
			fi
		fi

		echo "--------------------------------"
		echo " Configure Schedule"
		echo "--------------------------------"
		echo "  1. Type: $typestr"
		echo "  2. Set Time: $hour$minuteprefix$minute"
		echo "  3. Repeating: $repeatstr"
		echo "  4. Day: $daystr"
		echo
		echo "  5. Add Schedule"
		echo
		echo "  0. Cancel"
		echo -n "Enter Number (0-5):"

		setmode=$( get_number )
		if [ $setmode -eq 0 ]
		then
			subloopflag=0
		elif [ $setmode -eq 1 ]
		then
			echo "--------------------------------"
			echo " Schedule Type "
			echo "--------------------------------"
			echo "  1. Startup"
			echo "  2. Shutdown"
			echo
			echo -n "Enter Number (1-2):"

			tmpval=$( get_number )
			if [ $tmpval -eq 1 ]
			then
				cmdmode=1
			elif [ $tmpval -eq 2 ]
			then
				cmdmode=0
			else
				echo "Invalid Option"
			fi
		elif [ $setmode -eq 2 ]
		then
			echo -n "Enter Hour (0-23):"
			tmphour=$( get_number )
			echo -n "Enter Minute (0-59):"
			tmpminute=$( get_number )
			if [[ $tmpminute -ge 0 && $tmpminute -le 59 && $tmphour -ge 0 && $tmphour -le 23 ]]
			then
				minute=$tmpminute
				hour=$tmphour
			else
				echo "Invalid value(s)"
			fi
		elif [ $setmode -eq 3 ]
		then
			echo -n "Repeat schedule (Y/n)?:"
			read -n 1 confirm
			if [ "$confirm" = "y" ]
			then
				repeat=1
			else
				repeat=0
			fi
		elif [ $setmode -eq 4 ]
		then
			echo "Select Day of the Week:"
			echo "  0. Daily"
			echo "  1. Monday"
			echo "  2. Tuesday"
			echo "  3. Wednesday"
			echo "  4. Thursday"
			echo "  5. Friday"
			echo "  6. Saturday"
			echo "  7. Sunday"

			echo -n "Enter Number (0-7):"
			tmpval=$( get_number )
			if [[ $tmpval -ge 0 && $tmpval -le 7 ]]
			then
				dayidx=$tmpval
			else
				echo "Invalid Option"
			fi
		elif [ $setmode -eq 5 ]
		then
			if [ $dayidx -eq 0 ]
			then
				cronweekday="*"
			elif [ $dayidx -eq 7 ]
			then
				cronweekday="7"
			else
				cronweekday=$dayidx
			fi
			cmdcode="off"
			if [ $cmdmode -eq 1 ]
			then
				cmdcode="on"
			fi

			echo "$minute $hour * * $cronweekday $cmdcode" >> $rtcconfigfile
			sudo systemctl restart $rtcdaemonname.service
			subloopflag=0
		fi
	done
}

configure_newcron () {
	subloopflag=1
	while [ $subloopflag -eq 1 ]
	do
		echo "--------------------------------"
		echo " Schedule Type "
		echo "--------------------------------"
		echo "  1. Startup"
		echo "  2. Shutdown"
		echo
		echo "  0. Cancel"
		echo -n "Enter Number (0-2):"

		cmdmode=$( get_number )
		if [ $cmdmode -eq 0 ]
		then
			subloopflag=0
		elif [[ $cmdmode -ge 1 && $cmdmode -le 2 ]]
		then
			cmdcode="on"
			echo "--------------------------------"
			if [ $cmdmode -eq 1 ]
			then
				echo " Schedule Startup"
			else
				echo " Schedule Shutdown"
				cmdcode="off"
			fi
			echo "--------------------------------"
			echo "Select Schedule:"
			echo "  1. Hourly"
			echo "  2. Daily"
			echo "  3. Weekly"
			echo "  4. Monthly"
			echo
			echo "  0. Back"
			echo -n "Enter Number (0-4):"

			newmode=$( get_number )
			if [[ $newmode -ge 1 && $newmode -le 4 ]]
			then
				echo ""
				if [ $cmdmode -eq 1 ]
				then
					echo "New Startup Schedule"
				else
					echo "New Shutdown Schedule"
				fi

				if [ $newmode -eq 1 ]
				then
					echo -n "Enter Minute (0-59):"
					minute=$( get_number )
					if [[ $minute -ge 0 && $minute -le 59 ]]
					then
						echo "$minute * * * * $cmdcode" >> $rtcconfigfile
						sudo systemctl restart $rtcdaemonname.service
						subloopflag=0
					else
						echo "Invalid value"
					fi
				elif [ $newmode -eq 2 ]
				then
					echo -n "Enter Hour (0-23):"
					hour=$( get_number )
					echo -n "Enter Minute (0-59):"
					minute=$( get_number )
					if [[ $minute -ge 0 && $minute -le 59 && $hour -ge 0 && $hour -le 23 ]]
					then
						echo "$minute $hour * * * $cmdcode" >> $rtcconfigfile
						sudo systemctl restart $rtcdaemonname.service
						subloopflag=0
					else
						echo "Invalid value(s)"
					fi
				elif [ $newmode -eq 3 ]
				then
					echo "Select Day of the Week:"
					echo "  0. Sunday"
					echo "  1. Monday"
					echo "  2. Tuesday"
					echo "  3. Wednesday"
					echo "  4. Thursday"
					echo "  5. Friday"
					echo "  6. Saturday"

					echo -n "Enter Number (0-6):"
					weekday=$( get_number )
					echo -n "Enter Hour (0-23):"
					hour=$( get_number )
					echo -n "Enter Minute (0-59):"
					minute=$( get_number )

					if [[ $minute -ge 0 && $minute -le 59 && $hour -ge 0 && $hour -le 23 && $weekday -ge 0 && $weekday -le 6 ]]
					then
						echo "$minute $hour * * $weekday $cmdcode" >> $rtcconfigfile
						sudo systemctl restart $rtcdaemonname.service
						subloopflag=0
					else
						echo "Invalid value(s)"
					fi
				elif [ $newmode -eq 4 ]
				then
					echo -n "Enter Date (1-31):"
					monthday=$( get_number )
					if [[ $monthday -ge 29 ]]
					then
						echo "WARNING: This schedule will not trigger for certain months"
					fi
					echo -n "Enter Hour (0-23):"
					hour=$( get_number )
					echo -n "Enter Minute (0-59):"
					minute=$( get_number )

					if [[ $minute -ge 0 && $minute -le 59 && $hour -ge 0 && $hour -le 23 && $monthday -ge 1 && $monthday -le 31 ]]
					then
						echo "$minute $hour $monthday * * $cmdcode" >> $rtcconfigfile
						sudo systemctl restart $rtcdaemonname.service
						subloopflag=0
					else
						echo "Invalid value(s)"
					fi
				fi
			fi
		fi
	done
}

rtcloopflag=1
while [ $rtcloopflag -eq 1 ]
do
	echo "----------------------------"
	echo "Argon RTC Configuration Tool"
	echo "----------------------------"
	$pythonbin $argonrtcscript GETRTCTIME
	echo "Choose from the list:"
	echo "  1. Update RTC Time"
	echo "  2. Configure Startup/Shutdown Schedules"
	echo
	echo "  0. Exit"
	echo -n "Enter Number (0-2):"

	newmode=$( get_number )
	if [ $newmode -eq 0 ]
	then
		rtcloopflag=0
	elif [[ $newmode -ge 1 && $newmode -le 2 ]]
	then
		if [ $newmode -eq 1 ]
		then
			echo "Matching RTC Time to System Time..."
			$pythonbin $argonrtcscript UPDATERTCTIME
		elif [ $newmode -eq 2 ]
		then
			configure_schedule
		fi
	fi
done

echo
