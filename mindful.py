#!/usr/bin/python3

import argparse
import time
import datetime
import os

# Script to periodically check if my mind is wandering

print("time_asked,time_responded,was_wandering")

def getLine():
    time_asked = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    if os.system('zenity --question --text "not wandering?"') == 0:
        wandering = "0"
    else:
        wandering = "1"
    time_responded = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    return "{time_asked},{time_responded},{wandering}".format(
        time_asked=time_asked,
        time_responded=time_responded,
        wandering=wandering
    )

parser = argparse.ArgumentParser()
parser.add_argument('--delay', '-d', type=int, help="The delay between times when it asks if your mind is wandering")
args = parser.parse_args()

if args.delay is None:
    args.delay = 300
while True:
    print(getLine())
    try:
        time.sleep(args.delay)
    except KeyboardInterrupt:
        break

