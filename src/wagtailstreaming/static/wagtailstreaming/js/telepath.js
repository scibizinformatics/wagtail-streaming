(function() {
  function StreamChooser(html, idPattern, _opts) {
    this.html = html;
    this.idPattern = idPattern;
  }

  StreamChooser.prototype.render = function(placeholder, name, id, initialState) {
    const html = this.html
      .replace(/__NAME__/g, name)
      .replace(/__ID__/g, id);

    placeholder.outerHTML = html;
    const chooser = createStreamChooser(id);
    chooser.setState(initialState);
    return chooser;
  };

  window.telepath.register('wagtailstreaming.StreamChooser', StreamChooser);
})();
