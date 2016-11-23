#!/usr/bin/python

import sys
import os

if len(sys.argv) < 3:
    print("usage: " + sys.argv[0] + " {scriptname} [named parameters]")
    exit()

scriptName = sys.argv[1]
parameters = sys.argv[2:]

# argumentsCount is 1 (for the script itself) plus the number of parameters
argumentCount = len(parameters) + 1
argumentNameList = "{" + "} {".join(parameters) + "}"

argumentAssignments = []
for (index, parameter) in enumerate(parameters):
    argumentAssignments.append(parameter + " = sys.argv[" + str(index + 1) + "]")
argumentAssignments = "\n".join(argumentAssignments)

resultingScript = """#!/usr/bin/python3

import os
import sys
import getpass
import datetime
import requests
import json
import subprocess

if len(sys.argv) < %d:
    print("usage: " + sys.argv[0] + " %s")
    exit()

# Uncomment the following if you also need a password
#password = getpass.getpass('Please enter the password:')

# The current date/time is a common thing to need in scripts
DateString = datetime.datetime.now().strftime("%%Y-%%m-%%d-%%H-%%M-%%S")

# Uncomment and adjust the following line if you need to import special libraries
#sys.path.append(os.environ["HOME"] + "/")
#import csvtodict
#
# Use the following if you need to make any web requests
#
#response = requests.post(
#    'https://www.google.com/',
#    data={
#
#    },
#    verify='/etc/ssl/certs/ca-certificates.crt'
#    proxies=proxies
#).content
#
#response = requests.get(
#    'https://www.google.com/',
#    verify='/etc/ssl/certs/ca-certificates.crt'
#    proxies=proxies
#).content
#
# Use the following if you need to capture the output of other bash commands
#
#def run_command(command, encoding='UTF-8'):
#    with subprocess.Popen(['/bin/bash', command], stdout=subprocess.PIPE) as p:
#        result = p.stdout.read()
#    return result.decode(encoding)
#
%s
""" % (argumentCount, argumentNameList, argumentAssignments)

scriptFilename = os.environ["HOME"] + "/bin/" + scriptName
with open(scriptFilename, "w") as f:
    f.write(resultingScript)
os.system("chmod +x " + scriptFilename)
