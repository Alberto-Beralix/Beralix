################################################################################
##                                                                            ##
## Script de Linux para construir una iamgen ISO de arranque para una distro. ##
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

# Eliminamos una posible compactación que hubiese entre los archivos de la ISO
rm ./i386/casper/filesystem.squashfs
# Compactamos el sistema de archivos de la distro
mksquashfs i386-squashfs-root/ ./i386/casper/filesystem.squashfs
# Cambiamos los permisos al archivo de arranque de la ISO
chmod 664 ./i386/isolinux/isolinux.bin
# Construimos la ISO
genisoimage -A Beralix -R -b isolinux/isolinux.bin -no-emul-boot -boot-load-size 4 -boot-info-table -o ./Beralix-0.0.0-desktop-i386.iso ./i386/
# Cambiamos los permisos a la iamgen ISO
chmod 444 ./Beralix-0.0.0-desktop-i386.iso
# Eliminamos la campactación squashfs del sistema de archivos de la distro
rm ./i386/casper/filesystem.squashfs
