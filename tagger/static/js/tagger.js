var output = document.getElementById('output');

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
  while(offset > 0) {
    if(node.firstChild) {
      node = node.firstChild;
    } else if(node.textContent.length >= offset) {
      break;
    } else {
      offset -= node.textContent.length;
      while(!node.nextSibling) {
        node = node.parentNode;
      }
      node = node.nextSibling;
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
      '<a href="javascript:restoreSelection(null);">empty</a>'
    );
  } else {
    new_node.innerHTML = (
      '<a href="javascript:restoreSelection(' +
      '[\'' + current_selection[0] + '\', \'' + current_selection[1] + '\']);">' +
      current_selection[0] + ' ; ' + current_selection[1] +
      '</a>'
    );
  }
  output.parentNode.insertBefore(new_node, output);
}

function selectionChanged() {
  var old_selection = current_selection;
  var sel = window.getSelection();
  if(sel.rangeCount == 0) {
    output.innerText = "no selection";
    current_selection = null;
  } else {
    var range = sel.getRangeAt(0);
    if(range.collapsed) {
      output.innerText = "no selection";
      current_selection = null;
    } else {
      var start = describePos(range.startContainer, range.startOffset);
      var end = describePos(range.endContainer, range.endOffset);
      output.innerText = "current selection: " + start + " ; " + end;
      current_selection = [start, end];
    }
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
  console.log("TODO restore:" + saved);
  var sel = window.getSelection();
  sel.removeAllRanges();
  if(saved !== null) {
    var range = new Range();//document.createRange();
    var start = locatePos(saved[0]);
    console.log("set to start:", start);
    var end = locatePos(saved[1]);
    console.log("set to end:", end);
    range.setStart(start[0], start[1]);
    range.setEnd(end[0], end[1]);
    sel.addRange(range);
  }
}
