#!/bin/sh
# Simple restart script to handle RTV crashes
# Thanks EW!
cd "`dirname "$0"`"

export LD_LIBRARY_PATH=.:$LD_LIBRARY_PATH
while :
do
  python rtvrtm.py -t 10
  sleep 5
done
