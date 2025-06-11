#!/bin/bash

pythonbin=/usr/bin/python3
argononefanscript=/etc/argon/argononed.py
argoneonrtcscript=/etc/argon/argoneond.py
argonirconfigscript=/etc/argon/argonone-ir

if [ ! -z "$1" ]
then
	$pythonbin $argononefanscript FANOFF
	if [ "$1" = "poweroff" ] || [ "$1" = "halt" ]
	then
		if [ -f $argonirconfigscript ]
		then
			if [ -f $argoneonrtcscript ]
			then
				$pythonbin $argoneonrtcscript SHUTDOWN
			fi
			$pythonbin $argononefanscript SHUTDOWN
		fi
	fi
fi
