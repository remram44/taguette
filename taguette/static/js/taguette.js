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

// Don't use RegExp literals https://github.com/python-babel/babel/issues/640
var _escapeA = new RegExp('&', 'g'),
    _escapeL = new RegExp('<', 'g'),
    _escapeG = new RegExp('>', 'g'),
    _escapeQ = new RegExp('"', 'g'),
    _escapeP = new RegExp("'", 'g');
function escapeHtml(s) {
  return s
    .replace(_escapeA, "&amp;")
    .replace(_escapeL, "&lt;")
    .replace(_escapeG, "&gt;")
    .replace(_escapeQ, "&quot;")
    .replace(_escapeP, "&#039;");
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

function getScrollPos() {
  var doc = document.scrollingElement || document.documentElement, body = document.body;
  var x = (doc && doc.scrollLeft || body && body.scrollLeft || 0) - (doc.clientLeft || 0);
  var y = (doc && doc.scrollTop || body && body.scrollTop || 0) - (doc.clientTop || 0);
  return {x: x, y: y};
}

function getPageXY(e) {
  // from jQuery
  // Calculate pageX/Y if missing
  if(e.pageX === null) {
    var scrollPos = getScrollPos();
    var x = e.clientX + scrollPos.x;
    var y = e.clientY + scrollPos.y;
    return {x: x, y: y};
  }
  return {x: e.pageX, y: e.pageY};
}

function getCookie(name) {
  var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
  return r ? r[1] : undefined;
}

function ApiError(response, message) {
  if(!message) {
    message = "Status " + response.status;
  }
  this.status = response.status;
  this.message = message;
}
ApiError.prototype.toString = function() {
  return this.message;
};

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
      mode: 'same-origin',
      redirect: 'error'
    }
  ).then(function(response) {
    if(response.status != 200) {
      return response.json()
      .then(
      function(json) {
        if("error" in json) {
          throw new ApiError(response, json.error);
        } else {
          throw new ApiError(response);
        }
      },
      function() {
        throw new ApiError(response);
      }
      );
    }
    return response.json().catch(function(error) { throw new ApiError(response, "Invalid JSON"); });
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
      redirect: 'error',
      method: 'DELETE'
    }
  ).then(function(response) {
    if(response.status != 204) {
      throw new ApiError(response);
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
      redirect: 'error',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify(data)
    }
  ).then(function(response) {
    if(response.status != 200) {
      return response.json()
      .then(
      function(json) {
        if("error" in json) {
          throw new ApiError(response, json.error);
        } else {
          throw new ApiError(response);
        }
      },
      function() {
        throw new ApiError(response);
      }
      );
    }
    return response.json().catch(function(error) { throw new ApiError(response, "Invalid JSON"); });
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
      redirect: 'error',
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify(data)
    }
  ).then(function(response) {
    if(response.status != 204) {
      return response.json()
      .then(
      function(json) {
        if("error" in json) {
          throw new ApiError(response, json.error);
        } else {
          throw new ApiError(response);
        }
      },
      function() {
        throw new ApiError(response);
      }
      );
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

window.addEventListener('load', function() {
  // https://css-tricks.com/snippets/jquery/draggable-without-jquery-ui/
  (function($) {
    $.fn.drags = function(opt) {
      opt = $.extend({handle:"",cursor:"move"}, opt);
      if(opt.handle === "") {
          var $el = this;
      } else {
          var $el = this.find(opt.handle);
      }

      return $el.css('cursor', opt.cursor).on("mousedown", function(e) {
        if(opt.handle === "") {
          var $drag = $(this).addClass('draggable');
        } else {
          var $drag = $(this).addClass('active-handle').parent().addClass('draggable');
        }
        var z_idx = $drag.css('z-index'),
            drg_h = $drag.outerHeight(),
            drg_w = $drag.outerWidth(),
            pos_y = $drag.offset().top + drg_h - e.pageY,
            pos_x = $drag.offset().left + drg_w - e.pageX;
        $drag.css('z-index', 1000).parents().on("mousemove", function(e) {
          $('.draggable').offset({
            top:e.pageY + pos_y - drg_h,
            left:e.pageX + pos_x - drg_w
          }).on("mouseup", function() {
            $(this).removeClass('draggable').css('z-index', z_idx);
          });
        });
        e.preventDefault(); // disable selection
      }).on("mouseup", function() {
        if(opt.handle === "") {
          $(this).removeClass('draggable');
        } else {
          $(this).removeClass('active-handle').parent().removeClass('draggable');
        }
      });
    }
  })(jQuery);
});

function showSpinner() {
  $('#spinner-modal').modal('show');
}

function hideSpinner() {
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
function highlightSelection(saved, id, clickedCallback, title) {
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
      span.setAttribute('title', title);
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
  if(project_name == metadata.project_name
   && project_description == metadata.description) {
    return;
  }
  // Update globals
  project_name = metadata.project_name;
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
      alert(gettext("Couldn't update project metadata!") + "\n\n" + error);
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
      '  <a href="javascript:editDocument(' + doc.id + ');" class="btn btn-primary btn-sm">' + gettext("Edit") + '</a>' +
      '</div>';
    documents_list.insertBefore(elem, before);
    var links = elem.getElementsByTagName('a');
    linkDocument(links[0], doc.id);
  }
  if(entries.length == 0) {
    var elem = document.createElement('div');
    elem.className = 'list-group-item disabled';
    elem.textContent = gettext("There are no documents in this project yet.");
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

function basename(filename) {
  if(filename) {
    var idx = Math.max(filename.lastIndexOf('/'), filename.lastIndexOf('\\'));
    if(idx > -1) {
      filename = filename.substring(idx + 1);
    }
  }
  return filename;
}

document.getElementById('document-add-form').addEventListener('submit', function(e) {
  e.preventDefault();
  console.log("Uploading document...");

  var form_data = new FormData();
  var name = document.getElementById('document-add-name').value;
  if(!name) {
    name = basename(document.getElementById('document-add-file').value);
  }
  form_data.append('name', name);
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
      var error = null;
      try {
        error = xhr.response.error;
      } catch(e) {
      }
      if(!error) {
        error = "Status " + xhr.status;
      }
      alert(gettext("Error uploading file!") + "\n\n" + error);
    }
    hideSpinner();
  };
  xhr.onerror = function(e) {
    console.log("Document upload failed:", e);
    alert(gettext("Error uploading file!"));
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
    alert(gettext("Document name cannot be empty"));
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
    alert(gettext("Couldn't update document!") + "\n\n" + error);
  })
  .then(hideSpinner);
});

document.getElementById('document-change-delete').addEventListener('click', function(e) {
  e.preventDefault();

  var doc_id = document.getElementById('document-change-id').value;
  if(!window.confirm(gettext("Are you sure you want to delete the document '%(doc)s'?", {doc: documents[doc_id].name}))) {
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
    alert(gettext("Couldn't delete document!") + "\n\n" + error);
  });
});


/*
 * Tags list
 */

var tags_list = document.getElementById('tags-list');
var tags_modal_list = document.getElementById('highlight-add-tags');

function linkTag(elem, tag_path) {
  var url = '/project/' + project_id + '/highlights/' + encodeURIComponent(tag_path);
  elem.setAttribute('href', url);
  elem.addEventListener('click', function(e) {
    e.preventDefault();
    window.history.pushState({tag_path: tag_path}, "Tag " + tag_path, url);
    loadTag(tag_path);
  });
}

linkTag(document.getElementById('load-all-tags'), '');

function addTag(tag) {
  if(!('count' in tag) && tag.id in tags) {
    tag.count = tags[tag.id].count;
  } else if(!('count' in tag)) {
    tag = Object.assign({'count': 0}, tag)
  }
  tags[tag.id] = tag;
  updateTagsList();
}

function removeTag(tag_id) {
  delete tags['' + tag_id];
  updateTagsList();
}

function mergeTags(tag_src, tag_dest) {
  for(var id in highlights) {
    var hl_tags = highlights[id].tags;

    if(hl_tags.includes(tag_src)) {
      // Remove src tag
      var idx = hl_tags.indexOf(tag_src);
      hl_tags.splice(idx, 1);

      if(!hl_tags.includes(tag_dest)) {
        // Add new tag
        hl_tags.push(tag_dest);
      }
    }
  }
  delete tags['' + tag_src];
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
    if(current_tag !== null && tag.path.substr(0, current_tag.length) == current_tag) {
      elem.classList.add('tag-current');
    }
    elem.innerHTML =
      '<div class="d-flex justify-content-between align-items-center">' +
      '  <div class="tag-name">' +
      '    <a id="tag-link-' + tag.id + '">' + escapeHtml(tag.path) + '</a>' +
      '  </div>' +
      '  <div style="white-space: nowrap;">' +
      '    <span class="badge badge-secondary badge-pill" id="tag-' + tag.id + '-count">' + tag.count + '</span>' +
      '    <a href="javascript:editTag(' + tag.id + ');" class="btn btn-primary btn-sm">' + gettext("Edit") + '</a>' +
      '  </div>' +
      '</div>';
    tags_list.insertBefore(elem, before);
    linkTag(document.getElementById('tag-link-' + tag.id), tag.path);
  }
  if(entries.length == 0) {
    var elem = document.createElement('div');
    elem.className = 'list-group-item disabled';
    elem.textContent = gettext("There are no tags in this project yet.");
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
    elem.className = 'tag-name form-check';
    elem.innerHTML =
      '<input type="checkbox" class="form-check-input" value="' + tag.id + '" name="highlight-add-tags" id="highlight-add-tags-' + tag.id + '" />' +
      '<label for="highlight-add-tags-' + tag.id + '" class="form-check-label">' + escapeHtml(tag.path) + '</label>';
    tags_modal_list.insertBefore(elem, before);
  }
  if(entries.length == 0) {
    var elem = document.createElement('li');
    elem.textContent = gettext("no tags");
    tags_modal_list.appendChild(elem);
  }

  console.log("Tags list updated");

  // Re-set all highlights, to update titles
  var hl_entries = Object.entries(highlights);
  for(var i = 0; i < hl_entries.length; ++i) {
    setHighlight(hl_entries[i][1]);
  }

  console.log("Highlights updated");
}

updateTagsList();

function updateTagCount(id, delta) {
  var tag = tags['' + id];
  tag.count += delta;
  var elem = document.getElementById('tag-' + id + '-count');
  elem.textContent = tag.count;
}

var tag_add_modal = document.getElementById('tag-add-modal');

function createTag() {
  document.getElementById('tag-add-form').reset();
  document.getElementById('tag-add-id').value = '';
  document.getElementById('tag-add-label-new').style.display = '';
  document.getElementById('tag-add-label-change').style.display = 'none';
  document.getElementById('tag-add-cancel').style.display = '';
  document.getElementById('tag-add-delete').style.display = 'none';
  document.getElementById('tag-add-merge').style.display = 'none';
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
  document.getElementById('tag-add-merge').style.display = '';
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
    alert(gettext("Invalid tag name"));
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
    alert(gettext("Couldn't create tag!") + "\n\n" + error);
  })
  .then(hideSpinner);
});

// Delete tag button
document.getElementById('tag-add-delete').addEventListener('click', function(e) {
  var tag_id = document.getElementById('tag-add-id').value;
  if(tag_id) {
    if(!window.confirm(gettext("Are you sure you want to delete the tag '%(tag)s'?", {tag: tags[tag_id].path}))) {
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
      alert(gettext("Couldn't delete tag!") + "\n\n" + error);
    });
  }
});

// Merge tags button in tag edit modal: shows merge modal
document.getElementById('tag-add-merge').addEventListener('click', function(e) {
  var tag_id = document.getElementById('tag-add-id').value;
  if(!tag_id)
    return;
  tag_id = parseInt(tag_id);

  document.getElementById('tag-merge-form').reset();

  // Set source tag
  document.getElementById('tag-merge-src-id').value = '' + tag_id;
  document.getElementById('tag-merge-src-name').value = tags['' + tag_id].path;

  // Empty target tag <select>
  var target = document.getElementById('tag-merge-dest');
  target.innerHTML = '';

  // Fill target tag <select>
  var entries = Object.entries(tags);
  sortByKey(entries, function(e) { return e[1].path; });
  for(var i = 0; i < entries.length; ++i) {
    if(entries[i][0] == '' + tag_id) {
      // Can't merge into itself
      continue;
    }
    var option = document.createElement('option');
    option.setAttribute('value', entries[i][0]);
    option.innerText = entries[i][1].path;
    target.appendChild(option);
  }

  $(document.getElementById('tag-merge-modal')).modal();
});

// Merge modal submit button
document.getElementById('tag-merge-form').addEventListener('submit', function(e) {
  e.preventDefault();

  var tag_src = document.getElementById('tag-merge-src-id').value;
  if(!tag_src)
    return;
  tag_src = parseInt(tag_src);

  var tag_dest = document.getElementById('tag-merge-dest').value;
  if(!tag_dest)
    return;
  tag_dest = parseInt(tag_dest);

  console.log(
    "Merging tag " + tag_src + " (" + tags['' + tag_src].path +
    ") into tag " + tag_dest + " (" + tags['' + tag_dest].path + ")");
  showSpinner();
  postJSON(
    '/api/project/' + project_id + '/tag/merge',
    {src: tag_src, dest: tag_dest}
  )
  .then(function() {
    console.log("Tag merge posted");
    $(document.getElementById('tag-merge-modal')).modal('hide');
  })
  .catch(function(error) {
    console.error("Failed to merge tags:", error);
    alert(gettext("Couldn't merge tags!") + "\n\n" + error);
  })
  .then(hideSpinner);
});


/*
 * Highlights
 */

// Add or replace a highlight
function setHighlight(highlight) {
  var id = '' + highlight.id;
  if(highlights[id]) {
    removeHighlight(id);
  }
  highlights[id] = highlight;
  var tag_names = highlight.tags.map(function(id) { return tags[id].path; });
  sortByKey(tag_names, function(path) { return path; });
  tag_names = tag_names.join(", ");
  try {
    highlightSelection([highlight.start_offset, highlight.end_offset], id, editHighlight, tag_names);
    console.log("Highlight set:", highlight);
  } catch(error) {
    console.error(
      "Error setting highlight ", highlight.id, " ", [highlight.start_offset, highlight.end_offset],
      ":", error,
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
      var scrollPos = getScrollPos();
      hlinfo.style.left = ((rect.x || rect.left) + rect.width) + 'px';
      hlinfo.style.top = ((rect.y || rect.top) + rect.height + scrollPos.y + 20) + 'px';
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
  $(highlight_add_modal).modal().drags({handle: '.modal-header'});
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
  $(highlight_add_modal).modal().drags({handle: '.modal-header'});
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
    alert(gettext("Couldn't create highlight!") + "\n\n" + error);
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
      alert(gettext("Couldn't delete highlight!") + "\n\n" + error);
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
var members_displayed = {};

function _memberRow(login, user, can_edit, is_self) {
  var elem = document.createElement('div');
  elem.className = 'row members-item';
  elem.innerHTML =
    '<div class="col-md-4">' +
    '  <p class="members-item-login">' + login + '</p>' +
    '</div>' +
    '<div class="col-md-4 form-group">' +
    '  <select class="form-control"' + (can_edit?'':' disabled') + '>' +
    '    <option value="ADMIN">' + gettext("Full permissions") + '</option>' +
    '    <option value="MANAGE_DOCS">' + gettext("Can't change collaborators / delete project") + '</option>' +
    '    <option value="TAG">' + gettext("View & make changes") + '</option>' +
    '    <option value="READ">' + gettext("View only") + '</option>' +
    '  </select>' +
    '</div>' +
    (is_self?
    '<button type="button" class="btn btn-danger col-md-4 form-group">Leave project</button>'
    :
    '<button type="button" class="btn btn-danger col-md-4 form-group"' + (can_edit?'':' disabled') + '>Remove collaborator</button>'
    );

  [].forEach.call(elem.querySelectorAll('option'), function(e) {
    if(e.value == user.privileges) {
      e.selected = true;
    }
  });

  elem.querySelector('button').addEventListener('click', function(e) {
    elem.parentNode.removeChild(elem);
    delete members_displayed[login];
  });

  return elem;
}

function showMembers() {
  document.getElementById('members-add').reset();

  can_edit = members[user_login].privileges == 'ADMIN';

  if(can_edit) {
    document.getElementById('members-add-fields').removeAttribute('disabled');
  } else {
    document.getElementById('members-add-fields').setAttribute('disabled', 1);
  }

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
    var elem = _memberRow(login, user, can_edit, login == user_login);

    current_members.appendChild(elem);
  }

  // Store current state so that we can compare later
  members_initial = Object.assign({}, members);
  members_displayed = Object.assign({}, members);

  $(members_modal).modal();
}

document.getElementById('members-add').addEventListener('submit', function(e) {
  e.preventDefault();

  var login = document.getElementById('member-add-name').value.toLowerCase();
  if(!login) { return; }
  var privileges = document.getElementById('member-add-privileges').value;

  // Check login
  if(login in members_displayed) {
    alert(gettext("Already a member!"));
    document.getElementById('members-add').reset();
    return;
  }
  postJSON(
    '/api/check_user',
    {login: login}
  )
  .then(function(result) {
    if(result.exists) {
      // Add it at the top
      var elem = _memberRow(login, {privileges: privileges});
      var current_members = document.getElementById('members-current');
      current_members.insertBefore(elem, current_members.firstChild);
      members_displayed[login] = true;

      document.getElementById('members-add').reset();
    } else {
      alert(gettext("This user doesn't exist!"));
    }
  })
});

function sendMembersPatch() {
  var patch = {};

  var members_before = Object.assign({}, members_initial);

  var rows = document.getElementById('members-current').querySelectorAll('.members-item');
  for(var i = 0; i < rows.length; ++i) {
    var row = rows[i];
    var login = row.querySelector('.members-item-login').textContent;
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
    alert(gettext("Couldn't update collaborators!") + "\n\n" + error);
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
    document_contents.innerHTML = '<p style="font-style: oblique; text-align: center;">' + gettext("Load a document on the left") + '</p>';
    return;
  }
  showSpinner();
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
    var document_links = document.getElementsByClassName('document-link-current');
    for(var i = document_links.length - 1; i >= 0; --i) {
      document_links[i].classList.remove('document-link-current');
    }
    document.getElementById('document-link-' + current_document).classList.add('document-link-current');
    current_tag = null;
    var tag_links = document.getElementsByClassName('tag-current');
    for(var i = tag_links.length - 1; i >= 0; --i) {
      tag_links[i].classList.remove('tag-current');
    }
    console.log("Loaded document", document_id);
    for(var i = 0; i < result.highlights.length; ++i) {
      setHighlight(result.highlights[i]);
    }
    console.log("Loaded " + result.highlights.length + " highlights");

    // Update export button
    export_button.style.display = '';
    var items = export_button.getElementsByClassName('dropdown-item');
    for(var i = 0; i < items.length; ++i) {
      var ext = items[i].getAttribute('data-extension');
      if(items[i].getAttribute('data-document') !== 'false') {
        items[i].setAttribute(
          'href',
          '/project/' + project_id + '/export/document/' + document_id + '.' + ext,
        );
        items[i].style.display = '';
      } else {
        items[i].style.display = 'none';
      }
    }

    // Scroll up
    window.setTimeout(function() { window.scrollTo(0, 0); }, 0);
  })
  .catch(function(error) {
    console.error("Failed to load document:", error);
    alert(gettext("Error loading document!") + "\n\n" + error);
  })
  .then(hideSpinner);
}

function loadTag(tag_path, page) {
  if(page === undefined) {
    page = 1;
  }
  showSpinner();
  getJSON(
    '/api/project/' + project_id + '/highlights/' + encodeURIComponent(tag_path) + '?page=' + page
  )
  .then(function(result) {
    console.log("Loaded highlights for tag", tag_path || "''");
    current_tag = tag_path;
    current_document = null;
    var document_links = document.getElementsByClassName('document-link-current');
    for(var i = document_links.length - 1; i >= 0; --i) {
      document_links[i].classList.remove('document-link-current');
    }
    // No need to clear the 'tag-current', we are calling updateTagsList() below
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
      document_contents.innerHTML = '<p style="font-style: oblique; text-align: center;">' + gettext("No highlights with this tag yet.") + '</p>';
    }

    // Pagination controls
    function makePageLink(page_nb, label, current, enabled) {
      var item;
      if(current) {
        item = document.createElement('li');
        item.className = 'page-item active';
        item.innerHTML = '<span class="page-link">' + label + '<span class="sr-only">(current)</span></span>';
      } else if(!enabled) {
        item = document.createElement('li');
        item.className = 'page-item disabled';
        item.innerHTML = '<span class="page-link">' + label + '</span>';
      } else {
        item = document.createElement('li');
        item.className = 'page-item';
        var link = document.createElement('a');
        link.className = 'page-link';
        link.setAttribute('href', '#');
        link.innerText = label;
        link.addEventListener('click', function(e) {
          e.preventDefault();
          loadTag(tag_path, page_nb);
        });
        item.appendChild(link);
      }
      return item;
    }
    if(result.pages > 1 || page !== 1) {
      if(result.pages === undefined && page !== 1) {
        result.pages = 1;
      }
      pagination = document.createElement('nav');
      pagination.setAttribute('aria-label', "Page navigation");
      var pagination_ul = document.createElement('ul');
      pagination_ul.className = 'pagination justify-content-center';
      var min_page = Math.max(2, page - 2);
      var max_page = Math.min(result.pages - 1, page + 2);

      // Previous button
      pagination_ul.appendChild(makePageLink(page - 1, "Previous", false, page > 1));
      // Page 1
      pagination_ul.appendChild(makePageLink(1, 1, 1 === page, 1 !== page));
      // "..." between 1 and other pages, if appropriate
      if(min_page > 2) {
        pagination_ul.appendChild(makePageLink(page, "...", false, false));
      }
      // Other pages
      for(var i = min_page; i <= max_page; ++i) {
        pagination_ul.appendChild(makePageLink(i, i, i === page, i !== page));
      }
      // "..." between other pages and last page, if appropriate
      if(max_page < result.pages - 1) {
        pagination_ul.appendChild(makePageLink(page, "...", false, false));
      }
      // Last page
      pagination_ul.appendChild(makePageLink(result.pages, result.pages, result.pages === page, result.pages !== page));
      // Next button
      pagination_ul.appendChild(makePageLink(page + 1, "Next", false, page < result.pages));

      pagination.appendChild(pagination_ul);
      document_contents.appendChild(pagination);
    }

    updateTagsList();

    // Update export button
    export_button.style.display = '';
    var items = export_button.getElementsByClassName('dropdown-item');
    for(var i = 0; i < items.length; ++i) {
      var ext = items[i].getAttribute('data-extension');
      if(items[i].getAttribute('data-highlights') !== 'false') {
        items[i].setAttribute(
          'href',
          '/project/' + project_id + '/export/highlights/' + encodeURIComponent(tag_path) + '.' + ext,
        );
        items[i].style.display = '';
      } else {
        items[i].style.display = 'none';
      }
    }

    // Scroll up
    window.setTimeout(function() { window.scrollTo(0, 0); }, 0);
  })
  .catch(function(error) {
    console.error("Failed to load tag highlights:", error);
    alert(gettext("Error loading tag highlights!") + "\n\n" + error);
  })
  .then(hideSpinner);
}

// Load the document if the URL includes one
setTimeout(
  function() {
    var _document_url = new RegExp('/project/([0-9]+)/document/([0-9]+)');
    // Don't use RegExp literals https://github.com/python-babel/babel/issues/640
    var m = window.location.pathname.match(_document_url);
    if(m) {
      loadDocument(parseInt(m[2]));
    }
    // Or a tag
    var _tag_url = new RegExp('/project/([0-9]+)/highlights/([^/]*)');
    m = window.location.pathname.match(_tag_url);
    if(m) {
      loadTag(decodeURIComponent(m[2]));
    }
  },
  0,
);


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

// null: active now
// Date: inactive since then
var windowLastActive = new Date();
if(document.hasFocus()) {
  windowLastActive = null; // Focused now
}

window.addEventListener('focus', function() {
  // We are active as long as we have the focus
  windowLastActive = null;
  maybeResumePolling();
});
window.addEventListener('mousemove', function() {
  if(windowLastActive !== null) {
    // If the mouse moved over the window and we're not focused, refresh timer
    windowLastActive = new Date();
    maybeResumePolling();
  }
});
window.addEventListener('blur', function() {
  // We lost focus, start timer
  windowLastActive = new Date();
});

var lastPoll = null;
var polling = true;

function maybeResumePolling() {
  if(!polling) {
    longPollForEvents();
  }
}

function longPollForEvents() {
  // If we've been inactive for 10min, pause polling for now
  if(windowLastActive !== null && (new Date() - windowLastActive > 600000)) {
    console.log("Browser window inactive, stop polling");
    polling = false;
    return;
  }

  polling = true;
  lastPoll = Date.now();
  getJSON(
    '/api/project/' + project_id + '/events',
    {from: last_event}
  )
  .then(function(result) {
    if('project_meta' in result) {
      setProjectMetadata(result.project_meta);
    }
    if('document_add' in result) {
      for(var i = 0; i < result.document_add.length; ++i) {
        var p = result.document_add[i];
        addDocument({
          id: p.document_id,
          name: p.document_name,
          description: p.description
        });
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
          var p = added[i];
          setHighlight({
            id: p.highlight_id,
            start_offset: p.start_offset,
            end_offset: p.end_offset,
            tags: p.tags
          });
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
        var p = result.tag_add[i]
        addTag({
          id: p.tag_id,
          path: p.tag_path,
          description: p.description
        });
      }
    }
    if('tag_delete' in result) {
      for(var i = 0; i < result.tag_delete.length; ++i) {
        removeTag(result.tag_delete[i]);
      }
    }
    if('tag_merge' in result) {
      for(var i = 0; i < result.tag_merge.length; ++i) {
        mergeTags(result.tag_merge[i].src_tag_id, result.tag_merge[i].dest_tag_id);
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
    if('tag_count_changes' in result) {
      var entries = Object.entries(result.tag_count_changes);
      for(var i = 0; i < entries.length; ++i) {
        updateTagCount(entries[i][0], entries[i][1]);
      }
    }
    last_event = result.id;

    // Re-open connection
    setTimeout(longPollForEvents, 1);
  }, function(error) {
    console.error("Polling failed:", error);
    if(error instanceof ApiError && error.status == 403) {
      alert(gettext("It appears that you have been logged out."));
      window.location = '/';
    } else if(error instanceof ApiError && error.status == 404) {
      alert(gettext("You can no longer access this project."));
      window.location = '/';
    } else {
      setTimeout(longPollForEvents, Math.max(1, 5000 + lastPoll - Date.now()));
    }
  })
  .catch(function(error) {
    console.error("Polling function error:", error);
  });
}
longPollForEvents();
