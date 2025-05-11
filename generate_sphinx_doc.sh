#!/bin/bash
sphinx-apidoc -f -o source/ . lib/cloudsync
make html
