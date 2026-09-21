function openLinksInNewTab() {
  document.querySelectorAll(".md-content a[href]").forEach(function (a) {
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener");
  });
}
document$.subscribe(openLinksInNewTab);
