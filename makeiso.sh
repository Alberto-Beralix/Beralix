chmod 664 ./i386/isolinux/isolinux.bin
genisoimage -A Beralix -R -b isolinux/isolinux.bin -no-emul-boot -boot-load-size 4 -boot-info-table -o ./Beralix-0.0.0-desktop-i386.iso ./i386/
