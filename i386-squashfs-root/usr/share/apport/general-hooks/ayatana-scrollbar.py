def add_info(report):
    if report.has_key("Stacktrace") and "/usr/lib/liboverlay-scrollbar" in report["Stacktrace"]: 
        report.add_package_info("overlay-scrollbar")
    if report.has_key("Stacktrace") and "os-scrollbar.c" in report["Stacktrace"]:
        report['Tags'] = report.get('Tags', '') + ' ayatana-scrollbar-scrollbar'
    if report.has_key("Stacktrace") and "os-thumb.c" in report["Stacktrace"]:
        report['Tags'] = report.get('Tags', '') + ' ayatana-scrollbar-thumb'
    if report.has_key("Stacktrace") and "os-pager.c" in report["Stacktrace"]:
        report['Tags'] = report.get('Tags', '') + ' ayatana-scrollbar-pager'
