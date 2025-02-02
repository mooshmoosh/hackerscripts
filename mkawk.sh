#!/bin/bash

if [ $# -lt 2 ]
then
    echo "Usage: mkawk {data_file} {awk_script}"
    exit
fi

touch $2

if [ $(uname) == "Darwin" ]
then
    fswatch --help > /dev/null || (echo "Need to install fswatch"; exit 1)
    CHECK_CMD="fswatch -1 '"$2"' '"$1"'"
else
    echo "Only figured out mac so far... :("
    exit 1
fi

while true
do
    # Check command needs to be command that prints a non empty string when the file has changed
    if [ $(eval $CHECK_CMD) == "" ]
    then
        # The check command was exited with ctrl-c, exit the whole script
        exit 0
    fi
    clear
    awk -f "$2" < "$1"
done
