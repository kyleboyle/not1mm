#!/bin/bash
pip uninstall -y qsourcelogger
rm dist/*
python3 -m build
pip install -e .

