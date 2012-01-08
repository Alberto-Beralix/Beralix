import os, apport.packaging, apport.hookutils

def add_info(report, ui):

    response = ui.choice("How would you describe the issue?", ["The totem interface is not working correctly", "No sound is being played", "Some audio files or videos are not being played correctly"], False)

    if response == None: # user cancelled
        raise StopIteration
    if response[0] == 1: # the issue is a sound one
        os.execlp('apport-bug', 'apport-bug', 'audio')

    if response[0] == 2: # the issue is a codec one
        report.add_package_info("libgstreamer0.10-0")
        return

    report["LogAlsaMixer"] = apport.hookutils.command_output(["/usr/bin/amixer"])
    report["GstreamerVersions"] = apport.hookutils.package_versions("gstreamer*")
    report["XorgLog"] = apport.hookutils.read_file("/var/log/Xorg.0.log")
