#!/bin/bash
SCRIPT=`realpath $0`
SCRIPTPATH=`dirname $SCRIPT`
cd $SCRIPTPATH/../

python3 make.py

rm linien/server/linien.bin
cp fpga_build/linien.bin linien/server