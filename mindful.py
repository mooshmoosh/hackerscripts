#!/usr/bin/python3

import time
import datetime
import os

# Script to periodically check if my mind is wandering

print("time_asked,time_responded,was_wandering")

def getLine():
    time_asked = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    if os.system('zenity --question --text "wandering?"') == 0:
        wandering = "1"
    else:
        wandering = "0"
    time_responded = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    return "{time_asked},{time_responded},{wandering}".format(
        time_asked=time_asked,
        time_responded=time_responded,
        wandering=wandering
    )

while True:
    print(getLine())
    try:
        time.sleep(300)
    except KeyboardInterrupt:
        print("Exiting")
        break

