#!/bin/bash
sphinx-apidoc -f -M -o source/ src
make html
