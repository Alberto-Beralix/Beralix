(function() {
	// capture the preview
	if (window.playTrack !== undefined) {
		window.playTrack = function(file, title) {
			window.status = "u1preview:::" + file + ":::" + title;
		}
	}

	// and hide the flashplayer
	var ply = document.getElementById("flashPlayer");
	if (ply) {
		ply.parentNode.removeChild(ply);
	}

	// look to see if this is WMA or AAC only and if so inject a warning
	var hasNonMP3 = false;
	var hasMP3 = false;
	var medias = document.querySelectorAll("img.mediaIcon");
	for (var i=0; i<medias.length; i++) {
	    if (medias[i].src.indexOf("fmt_mp3") != -1) {
	        hasMP3 = true;
	    } else if (medias[i].src.indexOf("fmt_320") != -1) { // sigh
	        hasMP3 = true; 
	    } else if (medias[i].src.indexOf("fmt_") != -1) {
	        hasNonMP3 = true;
	    }
	}
	if (hasMP3 && hasNonMP3) {
	    // has both; do nothing; mp3 will be downloaded automatically
	} else if (hasMP3 && !hasNonMP3) {
	    // only has MP3, no problem
	} else if (!hasMP3 && !hasNonMP3) {
	    // doesn't have a format at all. Probably means that the HTML
	    // has changed. Do nothing.
	} else if (!hasMP3 && hasNonMP3) {
	    // does not have MP3, does have others. Problem. Add a warning.
	    var warn = document.createElement("div");
	    warn.appendChild(document.createTextNode(
	      "Warning: this album does not appear to be in MP3 format."));
	    warn.style.borderWidth = "3px";
	    warn.style.borderColor = "red";
	    warn.style.borderStyle = "solid";
	    warn.style.padding = "25px";
	    warn.style.textAlign = "center";
	    warn.style.backgroundColor = "#ff9b9b";
	    
	    var mainContent = document.querySelector("td.mainContent");
	    if (mainContent && mainContent.firstChild) {
	        mainContent.insertBefore(warn, mainContent.firstChild);
	    }
	}

	// add a padlock if this is a secure page
	if (location.href.substr(0,6) == "https:") {
	    var padlock = document.createElement("img");
	    padlock.src = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAMCAYAAACwXJejAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAINJREFUeNpiTEtLYwACfiCeBsQ2QCwHxK+BeB8QZwHxOyYGCOgFYl0gjgNiQyD2B2IJIJ4DkmSBKvIGYjcgvsyAAOlAfAzEgJkkCsQ3GVDBI6gzwIp4gJgZiH+hKfoOFQdb9xkq+J8BO/jPxEAEGABFTwmoeQpSlALEL3AoAImnAAQYAHZ7FWCCovUtAAAAAElFTkSuQmCC";
	    padlock.style.position = "fixed";
	    padlock.style.bottom = "0";
	    padlock.style.right = "0";
	    padlock.style.zIndex = "1000";
	    padlock.onclick = function() {
	        window.status = "u1showcertificate:::";
	        return false;
	    }
	    document.body.appendChild(padlock);
	}
})()
