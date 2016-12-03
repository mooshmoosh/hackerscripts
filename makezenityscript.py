#!/usr/bin/python

import sys
import os

if len(sys.argv) < 3:
    print("usage: " + sys.argv[0] + " {scriptname} [named parameters]")
    print("")
    print("    Creates a template bash script which uses zenity to create a dialog for")
    print("    the user to enter the parameters. This is useful for creating bash")
    print("    scripts that can be run by non technical people without them having to")
    print("    use the terminal.")
    exit()
title = sys.argv[1]
scriptName = title.lower().replace(' ', '_')
parameters = sys.argv[2:]

assignment_statements = []
form_elements = []
for (index, parameter) in enumerate(parameters):
    form_elements.append('--add-entry="' + parameter + '"')
    parameter_name = parameter.upper().replace(' ', '_')
    assignment_statements.append(parameter_name + '="${PARAMETER_ARRAY[' + str(index) + ']}"')

resultingScript = """#!/bin/bash

confirm () {{
    # call with a question string. Only runs a command if the user clicks yes
    # Use like so:
    #
    #    confirm "Would you like to run 'some_script.sh'" && ./some_script.sh

    zenity --question --text="$1"
}}

alert () {{
    # This is a gui friendly alternative to echo
    zenity --info --text="$1"
}}

PARAMETERS=$(zenity --forms --text="{title}" {form_elements}) || exit
IFS="|" read -r -a PARAMETER_ARRAY <<< "$PARAMETERS"

# The current date/time is a common thing to need in scripts
DATE_STAMP=`date +%%Y-%%m-%%d-%%H-%%M-%%S`
# These are the parameters from the user
{assignment_statements}

# Put the main content of your script here:

alert "All done!"
""".format(
    form_elements=' '.join(form_elements),
    title=title,
    assignment_statements="\n".join(assignment_statements)
)

scriptFilename = os.environ["HOME"] + "/bin/" + scriptName
with open(scriptFilename, "w") as f:
    f.write(resultingScript)
os.system("chmod +x " + scriptFilename)
