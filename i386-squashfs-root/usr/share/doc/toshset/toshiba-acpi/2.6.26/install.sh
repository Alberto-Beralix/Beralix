#!/bin/sh

apt-get install build-essential libncurses5-dev kernel-package linux-headers-`uname -r`

cd /usr/share/doc/toshset/toshiba-acpi/2.6.26

make

cp toshiba_acpi.ko /lib/modules/`uname -r`/kernel/drivers/acpi/
depmod -a
