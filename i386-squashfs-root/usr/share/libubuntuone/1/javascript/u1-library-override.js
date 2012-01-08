(function(){
	var lnks = document.querySelectorAll("a");
	for (var i=0; i<lnks.length; i++) {
		if (lnks[i].href.indexOf("library.aspx") != -1) {
			lnks[i].href = "%s";
		}
	}
})()