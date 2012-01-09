################################################################################
##                                                                            ##
## Script make Linux ISO image booteable of a distro.                         ##
##                                                                            ##
## makeiso.sh (C) 2012 Jesús Hernández Gormaz                                 ##
##                                                                            ##
##   This program is free software; you can redistribute it and/or            ##
##     modify it under the terms of the GNU General Public License as         ##
##     published by the Free Software Foundation; either version 3, or        ##
##     (at your option) any later version.                                    ##
##     This program is distributed in the hope that it will be useful,        ##
##     but WITHOUT ANY WARRANTY; without even the implied warranty of         ##
##     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the           ##
##     GNU General Public License for more details.                           ##
##     You should have received a copy of the GNU General Public License      ##
##     along with this program; if not, write to the Free Software            ##
##     Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.              ##
##                                                                            ##
##   Este programa es software libre. Puede redistribuirlo y/o                ##
##     modificarlo bajo los términos de la Licencia Pública General           ##
##     de GNU según es publicada por la Free Software Foundation,             ##
##     bien de la versión 3 de dicha Licencia o bien (según su                ##
##     elección) de cualquier versión posterior.                              ##
##     Este programa se distribuye con la esperanza de que sea                ##
##     útil, pero SIN NINGUNA GARANTÍA, incluso sin la garantía               ##
##     MERCANTIL implícita o sin garantizar la CONVENIENCIA PARA UN           ##
##     PROPÓSITO PARTICULAR. Para más detalles, véase la Licencia             ##
##     Pública General de GNU.                                                ##
##     Debería haber recibido una copia de la Licencia Pública                ##
##     General junto con este programa. En caso contrario, escriba            ##
##     a la Free Software Foundation, Inc., en 675 Mass Ave,                  ##
##     Cambridge, MA 02139, EEUU.                                             ##
##                                                                            ##
################################################################################

# Compacting the file system of the distribution.
mksquashfs i386-squashfs-root/ ./i386/casper/filesystem.squashfs
# We change file permissions to the ISO boot file..
chmod 664 ./i386/isolinux/isolinux.bin
# We build the ISO.
genisoimage -A Beralix -R -b isolinux/isolinux.bin -no-emul-boot -boot-load-size 4 -boot-info-table -o ./Beralix-0.0.0-desktop-i386.iso ./i386/
# We change the permissions of the ISO image.
chmod 444 ./Beralix-0.0.0-desktop-i386.iso
# We eliminate the compaction squashfs from the file system of the distribution.
rm ./i386/casper/filesystem.squashfs
