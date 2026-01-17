#!/bin/bash
coverage run -m unittest discover .
coverage report
coverage html
