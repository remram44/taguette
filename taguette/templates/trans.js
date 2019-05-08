var lang = {{ language }};
var catalog = {{ catalog }};

window.gettext = function(message, args) {
  var trans = catalog[message] || message;
  return trans.replace(/%\(([^)]+)\)s/g, function(match, name) { return args[name]; });
}
