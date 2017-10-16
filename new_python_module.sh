#!/bin/bash

display_help () {
    # if this is called, it means the wrong number of arguments were
    # supplied. So we display help and exit.
    echo "Usage: $0 %s"
    exit
}

test $# -lt 1 && display_help
MODULE_NAME=$1

mkdir $MODULE_NAME
echo "from .$MODULE_NAME import $MODULE_NAME" >> $MODULE_NAME/__init__.py
cat <<EOF >> $MODULE_NAME/$MODULE_NAME.py
class $MODULE_NAME:
    def __init__(self):
        pass
EOF
mkdir $MODULE_NAME/tests
touch $MODULE_NAME/tests/__init__.py
cat <<EOF >> $MODULE_NAME/tests/test$MODULE_NAME.py
import unittest
from .Mock$MODULE_NAME import Mock$MODULE_NAME

class ${MODULE_NAME}tests(unittest.TestCase):
    def testBasicSetup(self):
        object = Mock$MODULE_NAME()
EOF
cat <<EOF >> $MODULE_NAME/tests/Mock$MODULE_NAME.py
from $MODULE_NAME import $MODULE_NAME

class Mock${MODULE_NAME}($MODULE_NAME):
    pass
EOF

