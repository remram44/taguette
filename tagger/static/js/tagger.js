var output = document.getElementById('output');

function nextElement(node) {
  while(node && !node.nextSibling) {
    node = node.parentNode;
  }
  if(!node) {
    return null;
  }
  node = node.nextSibling;
  while(node.firstChild) {
    node = node.firstChild;
  }
  return node;
}

function describePos(node, offset) {
  while(!node.id) {
    if(node.previousSibling) {
      node = node.previousSibling;
      offset += node.textContent.length;
    } else {
      node = node.parentElement;
    }
  }
  return node.id.substring(9) + "+" + offset;
}

function locatePos(pos) {
  var split = pos.lastIndexOf("+");
  var id = "doc-item-" + pos.substring(0, split);
  var offset = parseInt(pos.substring(split + 1));
  var node = document.getElementById(id);
  while(node.firstChild) {
    node = node.firstChild;
  }
  while(offset > 0) {
    if(node.textContent.length >= offset) {
      break;
    } else {
      offset -= node.textContent.length;
      node = nextElement(node);
    }
  }
  return [node, offset]
}

var current_selection = null;

var record_timer = null;
function recordSelection() {
  var new_node = document.createElement('p');
  if(current_selection === null) {
    new_node.innerHTML = (
      'empty <a href="javascript:restoreSelection(null);">[restore]</a>'
    );
  } else {
    var repr = '[\'' + current_selection[0] + '\', \'' + current_selection[1] + '\']';
    new_node.innerHTML = (
      current_selection[0] + ' ; ' + current_selection[1] +
      ' <a href="javascript:restoreSelection(' +
      repr + ');">[restore]</a>' +
      ' <a href="javascript:highlightSelection(' + repr + ');">[highlight]</a>'
    );
  }
  output.parentNode.insertBefore(new_node, output);
}

function describeSelection() {
  var sel = window.getSelection();
  if(sel.rangeCount != 0) {
    var range = sel.getRangeAt(0);
    if(!range.collapsed) {
      var start = describePos(range.startContainer, range.startOffset);
      var end = describePos(range.endContainer, range.endOffset);
      output.innerText = "current selection: " + start + " ; " + end;
      return [start, end];
    }
  }
  output.innerText = "no selection";
  return null;
}

function selectionChanged() {
  var old_selection = current_selection;
  current_selection = describeSelection();
  if(current_selection === null) {
    document.getElementById('hlinfo').style.display = 'none';
  }
  if(record_timer) {
    clearTimeout(record_timer);
  }
  if(old_selection != current_selection) {
    record_timer = setTimeout(recordSelection, 2000);
  }
}
document.addEventListener('selectionchange', selectionChanged);

function restoreSelection(saved) {
  var sel = window.getSelection();
  sel.removeAllRanges();
  if(saved !== null) {
    var range = new Range();//document.createRange();
    var start = locatePos(saved[0]);
    var end = locatePos(saved[1]);
    range.setStart(start[0], start[1]);
    range.setEnd(end[0], end[1]);
    sel.addRange(range);
  }
}

function splitAtPos(pos, after) {
  if(pos[1] == 0) {
    return pos[0];
  } else if(pos[1] == pos[0].textContent.length) {
    return nextElement(pos[0]);
  } else {
    return pos[0].splitText(pos[1]);
  }
}

function highlightSelection(saved) {
  if(saved == null) {
    return;
  }
  var start = locatePos(saved[0]);
  start = splitAtPos(start, false);
  var end = locatePos(saved[1]);
  end = splitAtPos(end, true);

  var node = start;
  while(node != end) {
    var next = nextElement(node);
    if(node.nodeType == 3) {
      var span = document.createElement('span');
      span.className = 'highlight';
      node.parentNode.insertBefore(span, node);
      span.appendChild(node);
    }
    node = next;
  }
}

function getPageXY(e) {
  // from jQuery
  // Calculate pageX/Y if missing
  if(e.pageX == null) {
    var doc = document.documentElement, body = document.body;
    var x = e.clientX + (doc && doc.scrollLeft || body && body.scrollLeft || 0) - (doc.clientLeft || 0);
    var y = e.clientY + (doc && doc.scrollTop || body && body.scrollTop || 0) - (doc.clientTop || 0);
    return {x: x, y: y};
  }
  return {x: e.pageX, y: e.pageY};
}

function mouseIsUp(e) {
  var coords = getPageXY(e);
  var hlinfo = document.getElementById('hlinfo');
  setTimeout(function() {
    hlinfo.style.top = coords.y + 'px';
    hlinfo.style.left = coords.x + 'px';
    if(current_selection !== null) {
      hlinfo.style.display = 'block';
    }
  }, 1);
}
document.addEventListener('mouseup', mouseIsUp);
