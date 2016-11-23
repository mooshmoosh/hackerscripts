#!/bin/bash

display_help() {
    echo "Record the output of a script at regular intervals"
    echo ""
    echo "Useful for monitoring the speed of a website, or in real time"
    echo "seeing Hilary's chance of winning the election."
    echo ""
    echo "Usage: monitor.sh [script] [interval in seconds] [output file]"
    exit
}

test $# -lt 3 && display_help

echo "Year,Month,Day,Hour,Minute,Second,Output" >> $3

while true
do
    sleep $2
    echo "`date +'%Y,%m,%d,%H,%M,%S'`,`$1`" | tee -a $3
done;
