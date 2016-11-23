#!/usr/bin/python

import sys
import os

if len(sys.argv) < 3:
    print("usage: " + sys.argv[0] + " {scriptname} [named parameters]")
    exit()

scriptName = sys.argv[1]
parameters = sys.argv[2:]

argumentCount = len(parameters)
argumentNameList = "{" + "} {".join(parameters) + "}"

argumentAssignments = []
for (index, parameter) in enumerate(parameters):
    argumentAssignments.append(parameter + "=$" + str(index + 1))
argumentAssignments = "\n".join(argumentAssignments)

resultingScript = """#!/bin/bash

confirm () {
    # call with a prompt string or use a default
    read -r -p "${1:-Are you sure? [y/N]} " response
    case $response in
        [yY][eE][sS]|[yY])
            true
            ;;
        *)
            echo "Aborting..."
            exit
            ;;
    esac
}

display_help () {
    # if this is called, it means the wrong number of arguments were
    # supplied. So we display help and exit.
    echo "Usage: $0 %s"
    exit
}

test $# -lt %d && display_help

# The current date/time is a common thing to need in scripts
DATE_STAMP=`date +%%Y-%%m-%%d-%%H-%%M-%%S`

%s
""" % (argumentNameList, argumentCount, argumentAssignments)

scriptFilename = os.environ["HOME"] + "/bin/" + scriptName
with open(scriptFilename, "w") as f:
    f.write(resultingScript)
os.system("chmod +x " + scriptFilename)
