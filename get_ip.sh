#!/bin/bash
s="dynamic"
while getopts "t:" option;do
    case $option in
        t) s=$OPTARG ;;
        *) s="dynamic" ;;
    esac
done
#echo $s
ip address show eth0 | grep $s | awk '{print $2}' | cut -f1 -d'/'
