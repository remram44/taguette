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
 * - Members
 * - Load contents
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

function sortByKey(array, key) {
  array.sort(function(a, b) {
    if(key(a) < key(b)) {
      return -1;
    } else if(key(a) > key(b)) {
      return 1;
    } else {
      return 0;
    }
  });
}

function encodeGetParams(params) {
  return Object.entries(params)
    .filter(function(kv) { return kv[1] !== undefined; })
    .map(function(kv) { return kv.map(encodeURIComponent).join("="); })
    .join("&");
}

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
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
  if(e.pageX === null) {
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

function getJSON(url='', args) {
  if(args) {
    args = '?' + encodeGetParams(args);
  } else {
    args = '';
  }
  return fetch(
    url + args,
    {
      credentials: 'same-origin',
      mode: 'same-origin'
    }
  ).then(function(response) {
    if(response.status != 200) {
      throw "Status " + response.status;
    }
    return response.json();
  });
}

function deleteURL(url='', args) {
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
      method: 'DELETE'
    }
  ).then(function(response) {
    if(response.status != 204) {
      throw "Status " + response.status;
    }
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

function patchJSON(url='', data={}, args) {
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
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify(data)
    }
  ).then(function(response) {
    if(response.status != 204) {
      throw "Status " + response.status;
    }
  });
}

// Returns the byte length of a string encoded in UTF-8
// https://stackoverflow.com/q/5515869/711380
if(window.TextEncoder) {
  function lengthUTF8(s) {
    return (new TextEncoder('utf-8').encode(s)).length;
  }
} else {
  function lengthUTF8(s) {
    var l = s.length;
    for(var i = s.length - 1; i >= 0; --i) {
      var code = s.charCodeAt(i);
      if(code > 0x7f && code <= 0x7ff) ++l;
      else if(code > 0x7ff && code <= 0xffff) l += 2;
      if (code >= 0xDC00 && code <= 0xDFFF) i--; // trailing surrogate
    }
    return l;
  }
}

function showSpinner() {
  console.log("show");
  $('#spinner-modal').modal('show');
}

function hideSpinner() {
  console.log("hide");
  $('#spinner-modal').modal('hide');
}


/*
 * Selection stuff
 */

var chunk_offsets = [];

// Get the document offset from a position
function describePos(node, offset) {
  // Convert current offset from character to bytes
  offset = lengthUTF8(node.textContent.substring(0, offset));
  while(!node.id) {
    if(node.previousSibling) {
      node = node.previousSibling;
      offset += lengthUTF8(node.textContent);
    } else {
      node = node.parentNode;
    }
  }
  if(node.id.substring(0, 11) != 'doc-offset-') {
    return null;
  }
  return parseInt(node.id.substring(11)) + offset;
}

// Find a position from the document offset
function locatePos(pos) {
  // Find the right chunk
  var chunk_start = 0;
  for(var i = 0; i < chunk_offsets.length; ++i) {
    if(chunk_offsets[i] > pos) {
      break;
    }
    chunk_start = chunk_offsets[i];
  }

  var offset = pos - chunk_start;
  var node = document.getElementById('doc-offset-' + chunk_start);
  while(node.firstChild) {
    node = node.firstChild;
  }
  while(offset > 0) {
    if(lengthUTF8(node.textContent) >= offset) {
      break;
    } else {
      offset -= lengthUTF8(node.textContent);
      node = nextElement(node);
    }
  }
  return [node, offset]
}

var current_selection = null;

// Describe the selection e.g. [14, 56]
function describeSelection() {
  var sel = window.getSelection();
  if(sel.rangeCount != 0) {
    var range = sel.getRangeAt(0);
    if(!range.collapsed) {
      var start = describePos(range.startContainer, range.startOffset);
      var end = describePos(range.endContainer, range.endOffset);
      if(start !== null && end !== null) {
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
  var node = pos[0], idx = pos[1];
  if(idx === 0) {
    // Leftmost index: return current node
    return node;
  } else if(idx >= lengthUTF8(node.textContent)) {
    // Rightmost index: return next node
    return nextElement(node);
  } else {
    // Find the character index from the byte index
    var idx_char = 0;
    while(idx > 0) {
      var code = node.textContent.charCodeAt(idx_char);
      if(code <= 0x7f) idx -= 1;
      else if(code <= 0x7ff) idx -= 2;
      else if(code <= 0xffff) idx -= 3;
      else idx -= 4;
      idx_char += 1;
    }
    if(idx_char >= node.textContent.length) {
      console.error("Error computing character position!");
      idx_char = node.textContent.length - 1;
    }
    // Split, return right node
    return node.splitText(idx_char);
  }
}

// Highlight a described selection
function highlightSelection(saved, id, clickedCallback) {
  console.log("Highlighting", saved);
  if(saved === null) {
    return;
  }
  var start = locatePos(saved[0]);
  start = splitAtPos(start, false);
  var end = locatePos(saved[1]);
  end = splitAtPos(end, true);

  var node = start;
  while(node != end) {
    var next = nextElement(node);
    if(node.nodeType == 3 && node.textContent) { // TEXT_NODE
      var span = document.createElement('a');
      span.className = 'highlight highlight-' + id;
      span.setAttribute('data-highlight-id', '' + id);
      span.addEventListener('click', clickedCallback);
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
      '/api/project/' + project_id,
      meta
    )
    .then(function(result) {
      setProjectMetadata(meta, false);
    })
    .catch(function(error) {
      console.error("Failed to update project metadata:", error);
      alert("Couldn't update project metadata!");
      project_name_input.value = project_name;
      project_description_input.value = project_description;
    });
  }
}

document.getElementById('project-metadata-form').addEventListener('submit', function(e) {
  e.preventDefault();
  projectMetadataChanged();
});
project_name_input.addEventListener('blur', projectMetadataChanged);
project_description_input.addEventListener('blur', projectMetadataChanged);


/*
 * Documents list
 */

var current_document = null;
var current_tag = null;
var documents_list = document.getElementById('documents-list');

function linkDocument(elem, doc_id) {
  var url = '/project/' + project_id + '/document/' + doc_id;
  elem.setAttribute('href', url);
  elem.addEventListener('click', function(e) {
    e.preventDefault();
    window.history.pushState({document_id: doc_id}, "Document " + doc_id, url);
    loadDocument(doc_id);
  });
}

function updateDocumentsList() {
  // Empty the list
  while(documents_list.firstChild) {
    var first = documents_list.firstChild;
    if(first.classList
     && first.classList.contains('special-item-button')) {
      break;
    }
    documents_list.removeChild(first);
  }

  // Fill up the list again
  var before = documents_list.firstChild;
  var entries = Object.entries(documents);
  sortByKey(entries, function(e) { return e[1].name; });
  for(var i = 0; i < entries.length; ++i) {
    var doc = entries[i][1];
    var elem = document.createElement('li');
    elem.setAttribute('id', 'document-link-' + doc.id);
    elem.className = 'list-group-item document-link';
    elem.innerHTML =
      '<div class="d-flex justify-content-between align-items-center">' +
      '  <a class="document-link-a">' + escapeHtml(doc.name) + '</a>' +
      '  <a href="javascript:editDocument(' + doc.id + ');" class="badge badge-primary badge-pill">edit</a>' +
      '</div>';
    documents_list.insertBefore(elem, before);
    var links = elem.getElementsByTagName('a');
    linkDocument(links[0], doc.id);
  }
  if(entries.length == 0) {
    var elem = document.createElement('div');
    elem.className = 'list-group-item disabled';
    elem.textContent = "There are no documents in this project yet.";
    documents_list.insertBefore(elem, before);
  }
  console.log("Documents list updated");
}

updateDocumentsList();

function addDocument(document) {
  documents['' + document.id] = document;
  updateDocumentsList();
}

function removeDocument(document_id) {
  delete documents['' + document_id];
  updateDocumentsList();
  if(current_document == document_id) {
    window.history.pushState({}, "Project", '/project/' + project_id);
    loadDocument(null);
  }
}


/*
 * Add document
 */

var document_add_modal = document.getElementById('document-add-modal');

function createDocument() {
  document.getElementById('document-add-form').reset();
  $(document_add_modal).modal();
}

document.getElementById('document-add-form').addEventListener('submit', function(e) {
  e.preventDefault();
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
  xhr.open('POST', '/api/project/' + project_id + '/document/new');
  showSpinner();
  xhr.onload = function() {
    if(xhr.status == 200) {
      $(document_add_modal).modal('hide');
      document.getElementById('document-add-form').reset();
      console.log("Document upload complete");
    } else {
      console.error("Document upload failed: status", xhr.status);
      alert("Error uploading file!");
    }
    hideSpinner();
  };
  xhr.onerror = function(e) {
    console.log("Document upload failed:", e);
    alert("Error uploading file!");
    hideSpinner();
  }
  xhr.send(form_data);
});


/*
 * Change document
 */

var document_change_modal = document.getElementById('document-change-modal');

function editDocument(doc_id) {
  document.getElementById('document-change-form').reset();
  document.getElementById('document-change-id').value = '' + doc_id;
  document.getElementById('document-change-name').value = '' + documents['' + doc_id].name;
  document.getElementById('document-change-description').value = '' + documents['' + doc_id].description;
  $(document_change_modal).modal();
}

document.getElementById('document-change-form').addEventListener('submit', function(e) {
  e.preventDefault();
  console.log("Changing document...");

  var update = {
    name: document.getElementById('document-change-name').value,
    description: document.getElementById('document-change-description').value
  };
  if(!update.name || update.name.length == 0) {
    alert("Document name cannot be empty");
    return;
  }

  var doc_id = document.getElementById('document-change-id').value;
  showSpinner();
  postJSON(
    '/api/project/' + project_id + '/document/' + doc_id,
    update
  )
  .then(function() {
    console.log("Document update posted");
    $(document_change_modal).modal('hide');
    document.getElementById('document-change-form').reset();
  })
  .catch(function(error) {
    console.error("Failed to update document:", error);
    alert("Couldn't update document!");
  })
  .then(hideSpinner);
});

document.getElementById('document-change-delete').addEventListener('click', function(e) {
  e.preventDefault();

  var doc_id = document.getElementById('document-change-id').value;
  if(!window.confirm("Are you sure you want to delete the document '" + documents[doc_id].name + "'?")) {
    return;
  }
  console.log("Deleting document " + doc_id + "...");
  deleteURL('/api/project/' + project_id + '/document/' + doc_id)
  .then(function() {
    console.log("Document deletion posted");
    $(document_change_modal).modal('hide');
    document.getElementById('document-change-form').reset();
  })
  .catch(function(error) {
    console.error("Failed to delete document:", error);
    alert("Couldn't delete document!");
  });
});


/*
 * Tags list
 */

var tags_list = document.getElementById('tags-list');
var tags_modal_list = document.getElementById('highlight-add-tags');

function linkTag(elem, tag_path) {
  var url = '/project/' + project_id + '/highlights/' + tag_path;
  elem.setAttribute('href', url);
  elem.addEventListener('click', function(e) {
    e.preventDefault();
    window.history.pushState({tag_path: tag_path}, "Tag " + tag_path, url);
    loadTag(tag_path);
  });
}

linkTag(document.getElementById('load-all-tags'), '');

function addTag(tag) {
  tags[tag.id] = tag;
  updateTagsList();
}

function removeTag(tag_id) {
  delete tags['' + tag_id];
  updateTagsList();
}

function updateTagsList() {
  var entries = Object.entries(tags);
  sortByKey(entries, function(e) { return e[1].path; });

  // The list in the left panel

  // Empty the list
  while(tags_list.firstChild) {
    var first = tags_list.firstChild;
    if(first.classList
     && first.classList.contains('special-item-button')) {
      break;
    }
    tags_list.removeChild(first);
  }
  // Fill up the list again
  // TODO: Show this as a tree
  var tree = {};
  var before = tags_list.firstChild;
  for(var i = 0; i < entries.length; ++i) {
    var tag = entries[i][1];
    var elem = document.createElement('li');
    elem.className = 'list-group-item';
    elem.innerHTML =
      '<div class="d-flex justify-content-between align-items-center">' +
      '  <div class="tag-name">' +
      '    <a class="expand-marker">&nbsp;</a> ' +
      '    <a id="tag-link-' + tag.id + '">' + escapeHtml(tag.path) + '</a>' +
      '  </div>' +
      '  <a href="javascript:editTag(' + tag.id + ');" class="badge badge-primary badge-pill">edit</a>' +
      //'  <span href="#" class="badge badge-primary badge-pill">?</span>' + // TODO: highlight count
      '</div>' +
      '<ul class="sublist"></div>';
    tags_list.insertBefore(elem, before);
    linkTag(document.getElementById('tag-link-' + tag.id), tag.path);
  }
  if(entries.length == 0) {
    var elem = document.createElement('div');
    elem.className = 'list-group-item disabled';
    elem.textContent = "There are no tags in this project yet.";
    tags_list.insertBefore(elem, before);
  }

  // The list in the highlight modal

  // Empty the list
  while(tags_modal_list.firstChild) {
    var first = tags_modal_list.firstChild;
    if(first.classList
     && first.classList.contains('special-item-button')) {
      break;
    }
    tags_modal_list.removeChild(first);
  }
  // Fill up the list again
  // TODO: Show this as a tree
  var tree = {};
  var before = tags_modal_list.firstChild;
  for(var i = 0; i < entries.length; ++i) {
    var tag = entries[i][1];
    var elem = document.createElement('li');
    elem.className = 'tag-name';
    elem.innerHTML =
      '<input type="checkbox" value="' + tag.id + '" name="highlight-add-tags" id="highlight-add-tags-' + tag.id + '" />' +
      '<label for="highlight-add-tags-' + tag.id + '">' + tag.path + '</label>';
    tags_modal_list.insertBefore(elem, before);
  }
  if(entries.length == 0) {
    var elem = document.createElement('li');
    elem.textContent = "no tags";
    tags_modal_list.appendChild(elem);
  }

  console.log("Tags list updated");
}

updateTagsList();

var tag_add_modal = document.getElementById('tag-add-modal');

function createTag() {
  document.getElementById('tag-add-form').reset();
  document.getElementById('tag-add-id').value = '';
  document.getElementById('tag-add-label-new').style.display = '';
  document.getElementById('tag-add-label-change').style.display = 'none';
  document.getElementById('tag-add-cancel').style.display = '';
  document.getElementById('tag-add-delete').style.display = 'none';
  $(tag_add_modal).modal();
}

function editTag(tag_id) {
  document.getElementById('tag-add-form').reset();
  document.getElementById('tag-add-id').value = '' + tag_id;
  document.getElementById('tag-add-path').value = tags['' + tag_id].path;
  document.getElementById('tag-add-description').value = tags['' + tag_id].description;
  document.getElementById('tag-add-label-new').style.display = 'none';
  document.getElementById('tag-add-label-change').style.display = '';
  document.getElementById('tag-add-cancel').style.display = 'none';
  document.getElementById('tag-add-delete').style.display = '';
  $(tag_add_modal).modal();
}

// Save tag button
document.getElementById('tag-add-form').addEventListener('submit', function(e) {
  e.preventDefault();

  var tag_id = document.getElementById('tag-add-id').value;
  if(tag_id) {
    tag_id = parseInt(tag_id);
  } else {
    tag_id = null;
  }
  var tag_path = document.getElementById('tag-add-path').value;
  if(!tag_path) {
    alert("Invalid tag name");
    return;
  }
  var req;
  if(tag_id !== null) {
    console.log("Posting update for tag " + tag_id);
    req = postJSON(
      '/api/project/' + project_id + '/tag/' + tag_id,
      {path: tag_path,
       description: document.getElementById('tag-add-description').value}
    );
  } else {
    console.log("Posting new tag");
    req = postJSON(
      '/api/project/' + project_id + '/tag/new',
      {path: tag_path,
       description: document.getElementById('tag-add-description').value}
    );
  }
  showSpinner();
  req.then(function() {
    console.log("Tag posted");
    $(tag_add_modal).modal('hide');
    document.getElementById('tag-add-form').reset();
  })
  .catch(function(error) {
    console.error("Failed to create tag:", error);
    alert("Couldn't create tag!");
  })
  .then(hideSpinner);
});

// Delete tag button
document.getElementById('tag-add-delete').addEventListener('click', function(e) {
  var tag_id = document.getElementById('tag-add-id').value;
  if(tag_id) {
    if(!window.confirm("Are you sure you want to delete the tag '" + tags[tag_id].path + "'?")) {
      e.preventDefault();
      return;
    }
    tag_id = parseInt(tag_id);
    console.log("Posting tag " + tag_id + " deletion");
    deleteURL(
      '/api/project/' + project_id + '/tag/' + tag_id
    )
    .then(function() {
      $(tag_add_modal).modal('hide');
      document.getElementById('tag-add-form').reset();
    })
    .catch(function(error) {
      console.error("Failed to delete tag:", error);
      alert("Couldn't delete tag!");
    });
  }
});


/*
 * Highlights
 */

var highlights = {};

// Add or replace a highlight
function setHighlight(highlight) {
  var id = '' + highlight.id;
  if(highlights[id]) {
    removeHighlight(highlights[id]);
  }
  highlights[id] = highlight;
  try {
    highlightSelection([highlight.start_offset, highlight.end_offset], id, editHighlight);
    console.log("Highlight set:", highlight);
  } catch(error) {
    console.error(
      "Error setting highlight ", highlight.id, " ", [highlight.start_offset, highlight.end_offset],
      ": ", error, "\n", error.stack,
    );
  }
}

// Remove a highlight
function removeHighlight(id) {
  id = '' + id;
  if(!highlights[id]) {
    return;
  }

  var highlight = highlights[id];
  delete highlights[id];
  console.log("Highlight removed:", id);

  // Loop over highlight-<id> elements
  var elements = document.getElementsByClassName('highlight-' + id);
  for(var i = 0; i < elements.length; ++i) {
    // Move children up and delete this element
    var node = elements[i];
    while(node.firstChild) {
      node.parentNode.insertBefore(node.firstChild, node);
    }
    node.parentNode.removeChild(node);
  }
}

// Backlight
var backlight_checkbox = document.getElementById('backlight');
backlight_checkbox.addEventListener('change', function(e) {
  var classes = document.getElementById('document-view').classList;
  if(backlight_checkbox.checked == classes.contains('backlight')) {
    ; // all good
  } else if(backlight_checkbox.checked) {
    classes.add('backlight');
  } else {
    classes.remove('backlight');
  }
});


/*
 * Add highlight
 */

var highlight_add_modal = document.getElementById('highlight-add-modal');

// Updates current_selection and visibility of the controls
function selectionChanged() {
  current_selection = describeSelection();
  if(current_selection !== null) {
    var current_range = window.getSelection().getRangeAt(0);
    if(current_range.endOffset > 0) {
      var last_char_range = document.createRange();
      last_char_range.setStart(current_range.endContainer, current_range.endOffset - 1);
      last_char_range.setEnd(current_range.endContainer, current_range.endOffset);
      var rect = last_char_range.getClientRects().item(0);
      var doc = document.documentElement, body = document.body;
      hlinfo.style.left = (rect.x + rect.width) + 'px';
      hlinfo.style.top = (rect.y + rect.height + document.documentElement.scrollTop + 20) + 'px';
      hlinfo.style.display = 'block';
    } else {
      // We are in a weird situation where the end of the selection is in
      // an empty node. We just don't move the popup, seems to work in practice
    }
  } else {
    document.getElementById('hlinfo').style.display = 'none';
  }
}
document.addEventListener('selectionchange', selectionChanged);

function createHighlight(selection) {
  document.getElementById('highlight-add-id').value = '';
  document.getElementById('highlight-add-start').value = selection[0];
  document.getElementById('highlight-add-end').value = selection[1];
  document.getElementById('highlight-add-form').reset();
  $(highlight_add_modal).modal();
}

function editHighlight(e) {
  document.getElementById('highlight-add-form').reset();
  var id = this.getAttribute('data-highlight-id');
  document.getElementById('highlight-add-id').value = id;
  document.getElementById('highlight-add-start').value = highlights[id].start_offset;
  document.getElementById('highlight-add-end').value = highlights[id].end_offset;
  var hl_tags = highlights['' + id].tags;
  for(var i = 0; i < hl_tags.length; ++i) {
    document.getElementById('highlight-add-tags-' + hl_tags[i]).checked = true;
  }
  $(highlight_add_modal).modal();
}

// Save highlight button
document.getElementById('highlight-add-form').addEventListener('submit', function(e) {
  e.preventDefault();
  var highlight_id = document.getElementById('highlight-add-id').value;
  var selection = [
    parseInt(document.getElementById('highlight-add-start').value),
    parseInt(document.getElementById('highlight-add-end').value)
  ];
  var hl_tags = [];
  var entries = Object.entries(tags);
  for(var i = 0; i < entries.length; ++i) {
    var id = entries[i][1].id;
    if(document.getElementById('highlight-add-tags-' + id).checked) {
      hl_tags.push(id);
    }
  }
  var req;
  if(highlight_id) {
    console.log("Posting update for highlight " + highlight_id);
    req = postJSON(
      '/api/project/' + project_id + '/document/' + current_document + '/highlight/' + highlight_id,
      {start_offset: selection[0],
       end_offset: selection[1],
       tags: hl_tags}
    );
  } else {
    console.log("Posting new highlight");
    req = postJSON(
      '/api/project/' + project_id + '/document/' + current_document + '/highlight/new',
      {start_offset: selection[0],
       end_offset: selection[1],
       tags: hl_tags}
    );
  }
  showSpinner();
  req.then(function() {
    console.log("Highlight posted");
    $(highlight_add_modal).modal('hide');
    document.getElementById('highlight-add-form').reset();
  })
  .catch(function(error) {
    console.error("Failed to create highlight:", error);
    alert("Couldn't create highlight!");
  })
  .then(hideSpinner);
});

// Delete highlight button
document.getElementById('highlight-delete').addEventListener('click', function(e) {
  var highlight_id = document.getElementById('highlight-add-id').value;
  if(highlight_id) {
    highlight_id = parseInt(highlight_id);
    console.log("Posting highlight " + highlight_id + " deletion");
    deleteURL(
      '/api/project/' + project_id + '/document/' + current_document + '/highlight/' + highlight_id
    )
    .then(function() {
      $(highlight_add_modal).modal('hide');
      document.getElementById('highlight-add-form').reset();
    })
    .catch(function(error) {
      console.error("Failed to delete highlight:", error);
      alert("Couldn't delete highlight!");
    });
  }
});


/*
 * Members
 */

function addMember(login, privileges) {
  members[login] = {privileges: privileges};
}

function removeMember(login) {
  delete members[login];
}

var members_modal = document.getElementById('members-modal');
var members_initial = {};

function _memberRow(login, user) {
  var elem = document.createElement('div');
  elem.className = 'row members-item';
  elem.innerHTML =
    '<div class="col-md-4">' +
    '  <p class="members-item-login">' + login + '</p>' +
    '</div>' +
    '<div class="col-md-4 form-group">' +
    '  <select class="form-control">' +
    '    <option value="ADMIN">Full permissions</option>' +
    '    <option value="MANAGE_DOCS">Can\'t change collaborators / delete project</option>' +
    '    <option value="TAG">View &amp; make changes</option>' +
    '    <option value="READ">View only</option>' +
    '  </select>' +
    '</div>' +
    '<button type="button" class="btn btn-danger col-md-4 form-group">Remove collaborator</button>';

  [].forEach.call(elem.querySelectorAll('option'), function(e) {
    if(e.value == user.privileges) {
      e.selected = true;
    }
  });

  elem.querySelector('button').addEventListener('click', function(e) {
    elem.parentNode.removeChild(elem);
  });

  return elem;
}

function showMembers() {
  document.getElementById('members-add').reset();

  var entries = Object.entries(members);
  sortByKey(entries, function(e) { return e[0]; });
  console.log(
    "Members:",
    entries.map(function(e) { return e[0] + " (" + e[1].privileges + ")"; })
    .join(", ")
  );

  // Empty the list
  var current_members = document.getElementById('members-current');
  current_members.innerHTML = '';

  // Fill it back up
  for(var i = 0; i < entries.length; ++i) {
    var login = entries[i][0];
    var user = entries[i][1];
    var elem = _memberRow(login, user);

    if(login == user_login) {
      var to_disable = elem.querySelectorAll('select, button');
      [].forEach.call(to_disable, function(e) {
        e.disabled = true;
      });
    }

    current_members.appendChild(elem);
  }

  // Store current state so that we can compare later
  members_initial = Object.assign({}, members);

  $(members_modal).modal();
}

document.getElementById('members-add').addEventListener('submit', function(e) {
  e.preventDefault();

  var login = document.getElementById('member-add-name').value;
  if(!login) { return; }
  var privileges = document.getElementById('member-add-privileges').value;

  // Add it at the top
  var elem = _memberRow(login, {privileges: privileges});
  var current_members = document.getElementById('members-current');
  current_members.insertBefore(elem, current_members.firstChild);

  document.getElementById('members-add').reset();
});

function sendMembersPatch() {
  var patch = {};

  var members_before = Object.assign({}, members_initial);

  var rows = document.getElementById('members-current').querySelectorAll('.members-item');
  for(var i = 0; i < rows.length; ++i) {
    var row = rows[i];
    var login = row.querySelector('.members-item-login').textContent;
    if(login == user_login) continue; // Ignore self
    var privileges = row.querySelector('select').value;

    // Add to patch, if different from stored version
    if(!members_before[login] || members_before[login].privileges != privileges) {
      patch[login] = {privileges: privileges};
    }

    // Remove from object, so what's left are the removed members
    delete members_before[login];
  }

  // Remove the members that are left
  var entries = Object.entries(members_before);
  for(var i = 0; i < entries.length; ++i) {
    if(entries[i][0] == user_login) continue; // Ignore self
    patch[entries[i][0]] = null;
  }

  console.log("Patching members list");
  showSpinner();
  patchJSON(
    '/api/project/' + project_id + '/members',
    patch
  )
  .then(function() {
    console.log("Members list patched");
    $(members_modal).modal('hide');
  })
  .catch(function(error) {
    console.error("Failed to patch members list:", error);
    alert("Couldn't update collaborators");
  })
  .then(hideSpinner);

  members_initial = {};
}

document.getElementById('members-submit').addEventListener('click', function(e) {
  e.preventDefault();
  sendMembersPatch();
});

document.getElementById('members-current').addEventListener('submit', function(e) {
  e.preventDefault();
  sendMembersPatch();
});


/*
 * Load contents
 */

var document_contents = document.getElementById('document-contents');
var export_button = document.getElementById('export-button');

function loadDocument(document_id) {
  if(document_id === null) {
    document_contents.innerHTML = '<p style="font-style: oblique; text-align: center;">Load a document on the left</p>';
    return;
  }
  getJSON(
    '/api/project/' + project_id + '/document/' + document_id + '/content'
  )
  .then(function(result) {
    document_contents.innerHTML = '';
    highlights = {};
    chunk_offsets = [];
    for(var i = 0; i < result.contents.length; ++i) {
      var chunk = result.contents[i];
      var elem = document.createElement('div');
      elem.setAttribute('id', 'doc-offset-' + chunk.offset);
      elem.innerHTML = chunk.contents;
      document_contents.appendChild(elem);
      chunk_offsets.push(chunk.offset);
    }
    current_document = document_id;
    var document_links = document.getElementsByClassName('document-link');
    for(var i = 0; i < document_links.length; ++i) {
      document_links[i].classList.remove('document-link-current');
    }
    document.getElementById('document-link-' + current_document).classList.add('document-link-current');
    current_tag = null;
    console.log("Loaded document", document_id);
    for(var i = 0; i < result.highlights.length; ++i) {
      setHighlight(result.highlights[i]);
    }
    console.log("Loaded " + result.highlights.length + " highlights");

    // Update export button
    export_button.style.display = '';
    var items = export_button.getElementsByClassName('dropdown-item');
    for(var i = 0; i < items.length; ++i) {
      var ext = items[i].textContent.toLowerCase();
      items[i].setAttribute(
        'href',
        '/project/' + project_id + '/export/document/' + document_id + '.' + ext,
      );
    }
  })
  .catch(function(error) {
    console.error("Failed to load document:", error);
    alert("Error loading document!");
  });
}

function loadTag(tag_path) {
  getJSON(
    '/api/project/' + project_id + '/highlights/' + tag_path
  )
  .then(function(result) {
    console.log("Loaded highlights for tag", tag_path || "''");
    current_tag = tag_path;
    current_document = null;
    var document_links = document.getElementsByClassName('document-link');
    for(var i = 0; i < document_links.length; ++i) {
      document_links[i].classList.remove('document-link-current');
    }
    document_contents.innerHTML = '';
    highlights = {};
    for(var i = 0; i < result.highlights.length; ++i) {
      var hl = result.highlights[i];
      var elem = document.createElement('div');
      elem.className = 'highlight-entry';
      elem.setAttribute('id', 'highlight-entry-' + hl.id);
      elem.innerHTML = result.highlights[i].content;

      var doclink = document.createElement('a');
      doclink.className = 'badge badge-light';
      doclink.textContent = documents['' + hl.document_id].name;
      linkDocument(doclink, hl.document_id);
      elem.appendChild(doclink);
      elem.appendChild(document.createTextNode(' '));

      var tag_names = hl.tags.map(function(tag) { return tags['' + tag].path; });
      tag_names.sort();
      for(var j = 0; j < tag_names.length; ++j) {
        if(j > 0) {
          elem.appendChild(document.createTextNode(' '));
        }
        var taglink = document.createElement('a');
        taglink.className = 'badge badge-dark';
        taglink.textContent = tag_names[j];
        linkTag(taglink, taglink.textContent);
        elem.appendChild(taglink);
      }

      document_contents.appendChild(elem);
    }
    if(result.highlights.length == 0) {
      document_contents.innerHTML = '<p style="font-style: oblique; text-align: center;">No highlights with this tag yet.</p>';
    }

    // Update export button
    export_button.style.display = '';
    var items = export_button.getElementsByClassName('dropdown-item');
    for(var i = 0; i < items.length; ++i) {
      var ext = items[i].textContent.toLowerCase();
      items[i].setAttribute(
        'href',
        '/project/' + project_id + '/export/highlights/' + tag_path + '.' + ext,
      );
    }
  })
  .catch(function(error) {
    console.error("Failed to load tag highlights:", error);
    alert("Error loading tag highlights!");
  });
}

// Load the document if the URL includes one
var m = window.location.pathname.match(/\/project\/([0-9]+)\/document\/([0-9]+)/);
if(m) {
  loadDocument(parseInt(m[2]));
}
// Or a tag
m = window.location.pathname.match(/\/project\/([0-9]+)\/highlights\/([^\/]*)/);
if(m) {
  loadTag(m[2]);
}

// Load documents as we go through browser history
window.onpopstate = function(e) {
  if(e.state) {
    if(e.state.document_id !== undefined) {
      loadDocument(e.state.document_id);
    } else if(e.state.tag_path !== undefined) {
      loadTag(e.state.tag_path);
    } else {
      loadDocument(null);
    }
  } else {
    loadDocument(null);
  }
};


/*
 * Long polling
 */

var lastPoll = null;

function longPollForEvents() {
  lastPoll = Date.now();
  getJSON(
    '/api/project/' + project_id + '/events',
    {from: last_event}
  )
  .then(function(result) {
    console.log("Polling: ", result);
    if('project_meta' in result) {
      setProjectMetadata(result.project_meta);
    }
    if('document_add' in result) {
      for(var i = 0; i < result.document_add.length; ++i) {
        addDocument(result.document_add[i]);
      }
    }
    if('document_delete' in result) {
      for(var i = 0; i < result.document_delete.length; ++i) {
        removeDocument(result.document_delete[i]);
      }
    }
    if('highlight_add' in result) {
      var added = result.highlight_add['' + current_document];
      if(added) {
        for(var i = 0; i < added.length; ++i) {
          setHighlight(added[i]);
        }
      }
    }
    if('highlight_delete' in result) {
      var removed = result.highlight_delete['' + current_document];
      if(removed) {
        for(var i = 0; i < removed.length; ++i) {
          removeHighlight(removed[i]);
        }
      }
    }
    if('tag_add' in result) {
      for(var i = 0; i < result.tag_add.length; ++i) {
        addTag(result.tag_add[i]);
      }
    }
    if('tag_delete' in result) {
      for(var i = 0; i < result.tag_delete.length; ++i) {
        removeTag(result.tag_delete[i]);
      }
    }
    if('member_add' in result) {
      for(var i = 0; i < result.member_add.length; ++i) {
        addMember(result.member_add[i]['member'],
                  result.member_add[i]['privileges']);
      }
    }
    if('member_remove' in result) {
      for(var i = 0; i < result.member_remove.length; ++i) {
        removeMember(result.member_remove[i]);
      }
    }
    last_event = result.id;

    // Re-open connection
    setTimeout(longPollForEvents, 1);
  }, function(error) {
    setTimeout(longPollForEvents, Math.max(1, 5000 + lastPoll - Date.now()));
  })
  .catch(function(error) {
    console.error("Polling failed:", error);
  });
}
longPollForEvents();
