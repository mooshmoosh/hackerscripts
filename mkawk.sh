#!/bin/bash

if [ $# -lt 2 ]
then
    echo "Usage: mkawk {data_file} {awk_script}"
    exit
fi

touch $2

if [ $(uname) == "Darwin" ]
then
    CHECK_CMD="fswatch -1 '"$2"' '"$1"'"
else
    echo "Only figured out mac so far... :("
    exit 1
fi

while true
do
    if [ $(eval $CHECK_CMD) == "" ]
    then
        exit 0
    fi
    clear
    awk -f "$2" < "$1"
done
