#!/usr/bin/python

import sys
import os

if len(sys.argv) < 3:
    print("usage: " + sys.argv[0] + " {scriptname} [--choices] [named parameters]")
    print("")
    print("    Creates a template bash script which uses zenity to create a dialog for")
    print("    the user to enter the parameters. This is useful for creating bash")
    print("    scripts that can be run by non technical people without them having to")
    print("    use the terminal.")
    print("")
    print("    if you supply the --choices option, then the user will be asked to")
    print("    select one, from a list of the parameters in [named parameters]. The")
    print("    user's choice will be in a variable called CHOICE.")
    exit()
title = sys.argv[1]
scriptName = title.lower().replace(' ', '_')
parameters = sys.argv[2:]

if parameters[0] == '--choices':
    assignment_statements = []
    parameter_parsing_code = 'CHOICE=$(zenity --list --text="{title}" --column="Option" "{options}")'.format(
        title=title,
        options='" "'.join(parameters[1:])
    )
else:
    assignment_statements = ["# These are the parameters from the user"]
    form_elements = []
    for (index, parameter) in enumerate(parameters):
        form_elements.append('--add-entry="' + parameter + '"')
        parameter_name = parameter.upper().replace(' ', '_')
        assignment_statements.append(parameter_name + '="${PARAMETER_ARRAY[' + str(index) + ']}"')

    parameter_parsing_code = """
    PARAMETERS=$(zenity --forms --text="{title}" {form_elements}) || exit
    IFS="|" read -r -a PARAMETER_ARRAY <<< "$PARAMETERS"
    """.format(
        form_elements=' '.join(form_elements),
        title=title
    )

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

choose () {{
    # Present the user with multiple choice use it like this:
    #     CHOICE=$(choose "Please select a country" "Australia" "Mexico" "China")
    TITLE=$1
    shift
    zenity --list --text="$TITLE" --column="Option" "$@"
}}

{parameter_parsing_code}
# The current date/time is a common thing to need in scripts
DATE_STAMP=`date +%%Y-%%m-%%d-%%H-%%M-%%S`
{assignment_statements}

# Put the main content of your script here:

alert "All done!"
""".format(
    assignment_statements="\n".join(assignment_statements),
    parameter_parsing_code=parameter_parsing_code
)

scriptFilename = os.environ["HOME"] + "/bin/" + scriptName
with open(scriptFilename, "w") as f:
    f.write(resultingScript)
os.system("chmod +x " + scriptFilename)
