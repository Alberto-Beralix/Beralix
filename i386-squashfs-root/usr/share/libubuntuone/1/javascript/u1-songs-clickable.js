function makeSongClickable(li) {
	var md = li.getElementsByClassName("metadata");
	if (md.length == 1) {
		md[0].onclick = function(){
			var dp = this.parentNode.getAttribute("data-path")
			window.status = "u1playlibrary:::" + dp;
			return false;
		}
		li.className += " clickable";
	}
};
// Add custom clickable CSS
var styleElement = document.createElement("style");
styleElement.type = "text/css";
styleElement.appendChild(document.createTextNode("li.clickable .metadata p { cursor:pointer; color: black; }"));
document.getElementsByTagName("head")[0].appendChild(styleElement);


