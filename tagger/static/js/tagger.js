/*
 * Table of contents
 *
 * - Utilities
 * - Selection stuff
 * - Project metadata
 * - Documents list
 * - Add document
 * - Tags list
 * - Highlights
 * - Add highlight
 * - Long polling


/*
 * Utilities
 */

if(!Object.entries) {
  Object.entries = function(obj) {
    var ownProps = Object.keys(obj),
      i = ownProps.length,
      resArray = new Array(i); // preallocate the Array
    while(i--) {
      resArray[i] = [ownProps[i], obj[ownProps[i]]];
    }

    return resArray;
  };
}

function encodeGetParams(params) {
  return Object.entries(params)
    .filter(function(kv) { return kv[1] !== undefined; })
    .map(function(kv) { return kv.map(encodeURIComponent).join("="); })
    .join("&");
}


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

function getCookie(name) {
  var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
  return r ? r[1] : undefined;
}

function getPage(url='', args) {
  if(args) {
    args = '&' + encodeGetParams(args);
  } else {
    args = '';
  }
  return fetch(
    url + '?_xsrf=' + encodeURIComponent(getCookie('_xsrf')) + args,
    {
      credentials: 'same-origin',
      mode: 'same-origin'
    }
  );
}

function getJSON(url='', args) {
  return getPage(url, args)
  .then(function(response) {
    if(response.status != 200) {
      throw "Status " + response.status;
    }
    return response.json();
  });
}

function postJSON(url='', data={}, args) {
  if(args) {
    args = '&' + encodeGetParams(args);
  } else {
    args = '';
  }
  return fetch(
    url + '?_xsrf=' + encodeURIComponent(getCookie('_xsrf')) + args,
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
    if(response.status != 200) {
      throw "Status " + response.status;
    }
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

// Highlight a described selection
function highlightSelection(saved) {
  console.log("Highlighting", saved);
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
 * Project metadata
 */

var project_name_input = document.getElementById('project-name');
var project_name = project_name_input.value;

var project_description_input = document.getElementById('project-description');
var project_description = project_description_input.value;

function setProjectMetadata(metadata, form=true) {
  if(project_name == metadata.name
   && project_description == metadata.description) {
    return;
  }
  // Update globals
  project_name = metadata.name;
  project_description = metadata.description;
  // Update form
  if(form) {
    project_name_input.value = project_name;
    project_description_input.value = project_description;
  }
  // Update elements
  var elems = document.getElementsByClassName('project-name');
  for(var i = 0; i < elems.length; ++i) {
    elems[i].textContent = project_name;
  }
  console.log("Project metadata updated");
}

function projectMetadataChanged() {
  if(project_name_input.value != project_name
   || project_description_input.value != project_description) {
    console.log("Posting project metadata update");
    var meta = {
      name: project_name_input.value,
      description: project_description_input.value
    };
    postJSON(
      '/project/' + project_id + '/meta',
      meta
    )
    .then(function(result) {
      setProjectMetadata(meta, false);
      last_event = result.ts;
    }, function(error) {
      console.error("failed to update project metadata:", error);
      project_name_input.value = project_name;
      project_description_input.value = project_description;
    });
  }
}

document.getElementById('project-metadata-form').addEventListener('submit', function(e) {
  projectMetadataChanged();
  e.preventDefault();
});
project_name_input.addEventListener('blur', projectMetadataChanged);
project_description_input.addEventListener('blur', projectMetadataChanged);


/*
 * Documents list
 */

var current_document = null;
var documents_list = document.getElementById('documents-list');
var documents_retry = 5;

function setDocumentsList(docs) {
  documents = docs

  // Empty the list
  while(documents_list.firstChild) {
    var first = documents_list.firstChild;
    if(first.classList
     && first.classList.contains('list-group-item-primary')) {
      break;
    }
    documents_list.removeChild(documents_list.firstChild);
  }

  // Fill up the list again
  var before = documents_list.firstChild;
  for(var i = 0; i < documents.length; ++i) {
    var doc = documents[i];
    var elem = document.createElement('a');
    elem.className = 'list-group-item';
    elem.href = '#';
    elem.textContent = doc.name;
    elem.addEventListener('click', function(e) {
      loadDocument(doc.id);
      e.preventDefault();
    });
    documents_list.insertBefore(elem, before);
  }
  if(documents.length == 0) {
    var elem = document.createElement('div');
    elem.className = 'list-group-item disabled';
    elem.textContent = "There are no documents in this project yet.";
    documents_list.insertBefore(elem, before);
  }
  console.log("Documents list updated");
}

setDocumentsList(documents);

var document_contents = document.getElementById('document-contents');

function loadDocument(document_id) {
  getPage(
    '/project/' + project_id + '/document/' + document_id
  )
  .then(function(result) {
    if(result.status == 200) {
      result.text().then(function(contents) {
        document_contents.innerHTML = contents;
        current_document = document_id;
      });
      console.log("Loaded document", document_id);
    }
  }, function(error) {
    console.error("failed to load document");
  });
}


/*
 * Add document
 */

var document_add_modal = document.getElementById('document-add-modal');

function addDocument() {
  $(document_add_modal).modal();
}

var progress = document.getElementById('document-add-progress');

document.getElementById('document-add-form').addEventListener('submit', function(e) {
  console.log("Uploading document...");

  var form_data = new FormData();
  form_data.append('name',
                   document.getElementById('document-add-name').value);
  form_data.append('description',
                   document.getElementById('document-add-description').value);
  form_data.append('file',
                   document.getElementById('document-add-file').files[0]);
  form_data.append('_xsrf', getCookie('_xsrf'));

  var xhr = new XMLHttpRequest();
  xhr.responseType = 'json';
  xhr.open('POST', '/project/' + project_id + '/document/new');
  xhr.onload = function() {
    if(xhr.status == 200) {
      $(document_add_modal).modal('hide');
      document.getElementById('document-add-form').reset();
      console.log("Document upload complete");
    } else {
      console.error("Document upload failed: status", xhr.status);
      alert("Error uploading file!");
    }
  };
  xhr.onerror = function(e) {
    console.log("Document upload failed:", e);
    alert("Error uploading file!");
  }
  xhr.onprogress = function(e) {
    if(e.lengthComputable) {
      var pc = e.loaded / e.total * 100;
      progress.setAttribute('aria-valuenow', '' + pc);
      progress.style.width = pc + '%';
    }
  };
  xhr.send(form_data);

  e.preventDefault();
})


/*
 * Tags list
 */

var tags_list = document.getElementById('tags-list');


/*
 * Highlights
 */

var highlights = {};

// Add or replace a highlight
function setHighlight(highlight) {
  var id = '' + highlight.id;
  if(highlight[id]) {
    removeHighlight(highlight[id]);
  }
  highlight[id] = highlight;
  highlightSelection([highlight.offsetStart, highlight.offsetEnd], id);
  console.log("Highlight updated:", highlight);
}

// Remove a highlight
function removeHighlight(id) {
  id = '' + id;
  if(!highlights[id]) {
    return;
  }

  console.log("Highlight removed:", id);
  delete highlights[id];

  var start = locatePos(highlights[id].offsetStart)[0];
  var end = locatePos(highlights[id].offsetEnd)[0];

  var node = start;
  while(node != end) {
    var classes = node.classList;
    if(classes && classes.contains('highlight-' + id)) {
      while(node.firstChild) {
        node.parent.insertBefore(node.firstChild, node);
      }
      node.parent.removeChild(node);
    }
    if(node.firstChild) {
      node = node.firstChild;
    } else {
      while(!node.nextSibling) {
        node = node.parentNode;
        if(node == end) return;
      }
      node = node.nextSibling;
    }
  }
}


/*
 * Add highlight
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

function createHighlight(selection) {
  console.log("Posting new highlight");
  // TODO: Modal to add tags
  postJSON(
    '/project/' + project_id + '/document/' + current_document + '/highlight/new',
    {offsetStart: selection[0],
     offsetEnd: selection[1]}
  )
  .catch(function(error) {
    console.error("failed to create highlight:", error);
  });
}


/*
 * Long polling
 */

var long_polling_retry = 5;

function longPollForEvents() {
  getJSON(
    '/project/' + project_id + '/events',
    {from: last_event}
  )
  .then(function(result) {
    console.log("Polling: ", result);
    long_polling_retry = 5;
    if('project' in result) {
      setProjectMetadata(result.project);
    }
    if('documents' in result) {
      setDocumentsList(result.documents);
    }
    if('highlightsRemove' in result) {
      var removed = result.highlightsRemove[current_document];
      if(removed) {
        for(var i = 0; i < removed.length; ++i) {
          removeHighlight(removed[i]);
        }
      }
    }
    if('highlightsAdd' in result) {
      var added = result.highlightsAdd[current_document];
      if(added) {
        for(var i = 0; i < added.length; ++i) {
          setHighlight(added[i]);
        }
      }
    }
    last_event = result.ts;

    // Re-open connection
    setTimeout(longPollForEvents, 1000);
  }, function(error) {
    setTimeout(longPollForEvents, long_polling_retry * 1000);
    if(long_polling_retry < 60) {
      long_polling_retry *= 2;
    }
  });
}
longPollForEvents();
