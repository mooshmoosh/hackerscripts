#!/bin/bash

display_help () {
    # if this is called, it means the wrong number of arguments were
    # supplied. So we display help and exit.
    echo "Create a new python module with place for tests, and a single class"
    echo "Usage: $0 {module name}"
    exit
}

test $# -lt 1 && display_help
MODULE_NAME=$1

# Create the directory that holds the module
mkdir $MODULE_NAME

# Create the __init__.py file that makes the folder a python module. Also
# in this file we import the class from the file it resides in. This means
# that other code can import the main class with from BLAH import BLAH, otherwise
# it would be from BLAH import BLAH.BLAH as BLAH
echo "from .$MODULE_NAME import $MODULE_NAME" >> $MODULE_NAME/__init__.py

# Create the skeleton of the new class
cat <<EOF >> $MODULE_NAME/$MODULE_NAME.py
class $MODULE_NAME:
    def __init__(self):
        pass
EOF

# create a directory to hold the tests, and make it a python module
mkdir $MODULE_NAME/tests
touch $MODULE_NAME/tests/__init__.py

# Create the skeleton of the tests. Once class with one method that instantiates
# a mock version of the class to be tested
cat <<EOF >> $MODULE_NAME/tests/test$MODULE_NAME.py
import unittest
from .Mock$MODULE_NAME import Mock$MODULE_NAME

class ${MODULE_NAME}tests(unittest.TestCase):
    def testBasicSetup(self):
        obj = Mock$MODULE_NAME()
EOF

# The mock version of the class to be tested. Write all the main code in
# the main class, but if the main class makes web requests, or sends queries
# to external databases, that should be done in specific methods that are
# overridden here to just get the same data locally.
cat <<EOF >> $MODULE_NAME/tests/Mock$MODULE_NAME.py
from $MODULE_NAME import $MODULE_NAME
import os

module_dir = os.path.realpath(os.path.dirname(__file__))

class Mock${MODULE_NAME}($MODULE_NAME):
    pass
EOF

