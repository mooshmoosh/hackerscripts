#!/usr/bin/python3

import os

print("Creating a template script. Now add the parameters you need:")
argument_types = {
    1: {
        "name": "An integer",
        "type": "int"
    },
    2: {
        "name": "a float",
        "type": "float"
    },
    3: {
        "name": "a string",
        "type": "str"
    }
}

def askYesNo(question):
    yes_no_map = {
        "y": True,
        "ye": True,
        "yes": True,
        "n": False,
        "no": False
    }
    while True:
        try:
            is_flag = input(question + " ").strip().lower()
            if is_flag == "":
                return False
            return yes_no_map[is_flag]
        except:
            print("what?")
scriptName = input("What is the name of this script? ")
parameters = []
while True:
    new_parameter = {}
    new_parameter['name'] = input("Parameter name (eg 'file size'): ").strip()
    if new_parameter['name'] == "":
        break
    new_parameter['argument_name'] = new_parameter['name'].strip().replace(' ', '-').lower()
    new_parameter['short_name'] = input("short name (eg 's'): ").strip()
    new_parameter['help_text'] = input("Help text: ").strip()
    new_parameter['is_flag'] = askYesNo("Is this parameter a flag? (present -> True, not present -> False) (y/N):")
    if not new_parameter['is_flag']:
        print("\n".join([
            "What type should this parameter be?"] + [
            "  {number}. {name}".format(number=number, name=argtype['type']) for number, argtype in argument_types.items()]))
        while True:
            new_parameter['type'] = int(input("Type: ").strip())
            if new_parameter['type'] == '':
                break
            try:
                new_parameter['type'] = argument_types[new_parameter['type']]['type']
                break
            except:
                print("what?")
        if new_parameter['type'] == '':
            continue
        new_parameter['is_list'] = askYesNo("Is this parameter a list? (y/N):")
    parameters.append(new_parameter)

print(parameters)
resultingScript = """#!/usr/bin/python3

import os
import getpass
import datetime
import json
import subprocess
import argparse

def askYesNo(question):
    yes_no_map = {{
        "y": True,
        "ye": True,
        "yes": True,
        "n": False,
        "no": False
    }}
    while True:
        try:
            is_flag = input(question + " ").strip().lower()
            if is_flag == "":
                return False
            return yes_no_map[is_flag]
        except:
            print("what?")

# Uncomment the following if you also need a password
#password = getpass.getpass('Please enter the password:')

# The current date/time is a common thing to need in scripts
DateString = datetime.datetime.now().strftime("%Y-%m-%%d-%H-%M-%S")

# Uncomment and adjust the following line if you need to import special libraries
#sys.path.append(os.environ["HOME"] + "/")
#
# Use the following if you need to capture the output of other bash commands
#
#def run_command(command, encoding='UTF-8'):
#    with subprocess.Popen(['/bin/bash', command], stdout=subprocess.PIPE) as p:
#        result = p.stdout.read()
#    return result.decode(encoding)
#

args = argparse.ArgumentParser()
{argparse_commands}
args.parse_args()
""".format(argparse_commands="\n".join([
    'args.add_argument("-{short_name}", "--{argument_name}", help="{help_text}"{type_spec}{list_spec}{flag_spec})'.format(
        short_name=parameter['short_name'],
        help_text=parameter['help_text'],
        argument_name=parameter['argument_name'],
        type_spec=', type=' + parameter.get('type') if not parameter.get('is_flag', False) else '',
        list_spec=', nargs="+"' if parameter.get('is_list', False) else '',
        flag_spec=', action="store_true"' if parameter.get('is_flag', False) else ''
    ) for parameter in parameters]))

scriptFilename = os.environ["HOME"] + "/bin/" + scriptName
with open(scriptFilename, "w") as f:
    f.write(resultingScript)
os.system("chmod +x " + scriptFilename)
