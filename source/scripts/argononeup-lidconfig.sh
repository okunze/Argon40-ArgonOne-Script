#!/bin/bash

tmpfile="/dev/shm/argontmpconf.txt"
daemonconfigfile="/etc/argononeupd.conf"

if [ -f "$daemonconfigfile" ]
then
	. $daemonconfigfile
fi

if [ -z "$lidshutdownsecs" ]
then
	lidshutdownsecs=0
fi


mainloopflag=1
newmode=0


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
		fi
		echo $curnumber
		return
	fi
	echo "-1"
	return
}

while [ $mainloopflag -eq 1 ]
do

	lidshutdownmins=$((lidshutdownsecs / 60))


	echo "------------------------------------------"
	echo " Argon One Up Lid Configuration Tool"
	echo "------------------------------------------"

	echo
	echo "Lid Close Behavior:"
	if [ $lidshutdownsecs -lt 1 ]
	then
		echo "(Do Nothing)"
	else
		echo "(Shut down after $lidshutdownmins minute(s))"
	fi
	echo "  1. Do Nothing"
	echo "  2. Shutdown"
	echo
	echo "  0. Exit"
	echo "NOTE: You can also edit $daemonconfigfile directly"
	echo -n "Enter Number (0-2):"
	newmode=$( get_number )

	if [[ $newmode -eq 0 ]]
	then
		mainloopflag=0
	elif [ $newmode -eq 1 ]
	then
		lidshutdownsecs=0
	elif [ $newmode -eq 2 ]
	then
		maxmins=120
		echo "Please provide number of minutes until shutdown:"
		echo -n "Enter Number (1-$maxmins):"
		curval=$( get_number )
		if [ $curval -gt $maxmins ]
		then
			newmode=0
			echo "Invalid input"
		elif [ $curval -lt 1 ]
		then
			newmode=0
			echo "Invalid input"
		else
			lidshutdownsecs=$((curval * 60))
		fi
	fi

	if [ $newmode -eq 1 ] || [ $newmode -eq 2 ]
	then
		if [ -f "$daemonconfigfile" ]
		then
			grep -v 'lidshutdownsecs' "$daemonconfigfile" > $tmpfile
		else
			echo '#' > $tmpfile
			echo '# Argon One Up Configuration' >> $tmpfile
			echo '#' >> $tmpfile
		fi
		echo '# lidshutdownsecs number of seconds till shutdown when lid is closed 0 if do nothing' >> $tmpfile
		echo "lidshutdownsecs=$lidshutdownsecs" >> $tmpfile

		sudo cp $tmpfile $daemonconfigfile
		sudo chmod 666 $daemonconfigfile

		echo "Configuration updated."

	fi
done

echo

