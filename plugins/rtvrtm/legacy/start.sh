#!/bin/sh
cd "`dirname "$0"`"

running=`ps aux | grep rtv.sh | grep -v grep | wc -l`
if [ $running -eq 0 ]
then
  screen -dmS RTV ./rtv.sh
  echo "RTV started"
else
  echo "RTV is already running"
fi
