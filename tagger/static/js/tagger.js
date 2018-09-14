/*
 * Utilities
 */

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

function postJSON(url='', data={}) {
  return fetch(
    url + '?_xsrf=' + encodeURIComponent(getCookie('_xsrf')),
    {
      credentials: 'same-origin',
      mode: 'same-origin',
      cache: 'no-cache',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify(data)
    }
  ).then(function(response) {
    return response.json();
  });
}


/*
 * Selection stuff
 */

// Describe a position e.g. "3+56"
function describePos(node, offset) {
  while(!node.id) {
    if(node.previousSibling) {
      node = node.previousSibling;
      offset += node.textContent.length;
    } else {
      node = node.parentElement;
    }
  }
  if(node.id.substring(0, 9) != 'doc-item-') {
    return null;
  }
  return node.id.substring(9) + "+" + offset;
}

// Find a described position
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

// Describe a selection e.g. ["3+56", "5+14"]
function describeSelection() {
  var sel = window.getSelection();
  if(sel.rangeCount != 0) {
    var range = sel.getRangeAt(0);
    if(!range.collapsed) {
      var start = describePos(range.startContainer, range.startOffset);
      var end = describePos(range.endContainer, range.endOffset);
      if(start && end) {
        return [start, end];
      }
    }
  }
  return null;
}

// Restore a described selection
function restoreSelection(saved) {
  var sel = window.getSelection();
  sel.removeAllRanges();
  if(saved !== null) {
    var range = document.createRange();
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

// Highlight a described selection using <span class="highlight">
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


/*
 * Controls
 */

// Updates current_selection and visibility of the controls
function selectionChanged() {
  current_selection = describeSelection();
  if(current_selection === null) {
    document.getElementById('hlinfo').style.display = 'none';
  }
}
document.addEventListener('selectionchange', selectionChanged);

// Update controls position
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


/*
 * Project metadata
 */

var project_id = parseInt(document.getElementById('project-id').value);

var project_name_input = document.getElementById('project-name');
var project_name = project_name_input.value;

var project_description_input = document.getElementById('project-description');
var project_description = project_description_input.value;

function getCookie(name) {
  var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
  return r ? r[1] : undefined;
}

function updateProjectMetadata() {
  if(project_name_input.value != project_name
   || project_description_input.value != project_description) {
     var name = project_name_input.value;
     var description = project_description_input.value;
     postJSON(
       '/project/' + project_id + '/meta',
       {name: name, description: description}
     )
     .then(function() {
       project_name = name;
       var elems = document.getElementsByClassName('project-name');
       for(var i = 0; i < elems.length; ++i) {
         elems[i].textContent = name;
       }
       project_description = description;
     })
     .catch(function(error) {
       console.error("failed to update project metadata:", error);
       project_name_input.value = project_name;
       project_description_input.value = project_description;
     });
   }
}

document.getElementById('project-metadata-form').addEventListener('submit', function(e) {
  updateProjectMetadata();
   e.preventDefault();
});
project_name_input.addEventListener('blur', function(e) {
  updateProjectMetadata();
});
project_description_input.addEventListener('blur', function(e) {
  updateProjectMetadata();
});


var documents_list = document.getElementById('documents-list');
var tags_list = document.getElementById('tags-list');
