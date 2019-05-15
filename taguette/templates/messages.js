// This file doesn't load until messages are available
(function() {
var messages = {{ messages }};
var container = document.getElementById('messages-div');
for(var i = 0; i < messages.length; ++i) {
  var msg = document.createElement('div');
  msg.className = 'alert alert-secondary';
  msg.innerHTML = messages[i]['html'];
  container.appendChild(msg);
}
})();
