flush_unopkg_cache() {
	/usr/lib/libreoffice/program/unopkg list --shared > /dev/null 2>&1
}

remove_extension() {
  if /usr/lib/libreoffice/program/unopkg list --shared $1 >/dev/null; then
    INSTDIR=`mktemp -d`
    export PYTHONPATH="/@OOBASISDIR@/program"
    if [ -L /usr/lib/libreoffice/basis-link ]; then
	d=/var/lib/libreoffice/`readlink /usr/lib/libreoffice/basis-link`/
    else
	d=/usr/lib/libreoffice
    fi
    /usr/lib/libreoffice/program/unopkg remove -v --shared $1 \
      "-env:UserInstallation=file://$INSTDIR" \
      "-env:UNO_JAVA_JFW_INSTALL_DATA=file://$d/share/config/javasettingsunopkginstall.xml" \
      "-env:JFW_PLUGIN_DO_NOT_CHECK_ACCESSIBILITY=1"
    if [ -n $INSTDIR ]; then rm -rf $INSTDIR; fi
    flush_unopkg_cache
  fi
}

validate_extensions() {
	/usr/lib/libreoffice/program/unopkg validate -v --shared
}

sync_extensions() {
  INSTDIR=`mktemp -d`
  export PYTHONPATH="/@OOBASISDIR@/program"
  if [ -L /usr/lib/libreoffice/basis-link ]; then
	d=/var/lib/libreoffice/`readlink /usr/lib/libreoffice/basis-link`/
  else
	d=/usr/lib/libreoffice
  fi
  if [ -e /usr/lib/libreoffice/share/prereg/bundled ] && readlink /usr/lib/libreoffice/share/prereg/bundled 2>&1 >/dev/null; then
    /usr/lib/libreoffice/program/unopkg sync -v --shared \
      "-env:BUNDLED_EXTENSIONS_USER=file:///usr/lib/libreoffice/share/prereg/bundled" \
      "-env:UserInstallation=file://$INSTDIR" \
      "-env:UNO_JAVA_JFW_INSTALL_DATA=file://$d/share/config/javasettingsunopkginstall.xml" \
      "-env:JFW_PLUGIN_DO_NOT_CHECK_ACCESSIBILITY=1"
  fi
}

