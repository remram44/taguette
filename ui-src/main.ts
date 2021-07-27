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
 */


/*
 * Utilities
 */

if(!Object.entries) {
  Object.entries = function<T>(obj: {[k: string]: T}): [string, T][] {
    const ownProps = Object.keys(obj);
    let i = ownProps.length;
    const resArray = new Array(i); // preallocate the Array
    while(i--) {
      resArray[i] = [ownProps[i], obj[ownProps[i]]];
    }

    return resArray;
  };
}

function sortByKey<T>(array: T[], key: (key: T) => any): void {
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

function encodeGetParams(params: {[k: string]: string}): string {
  return Object.entries(params)
    .filter(function(kv) { return kv[1] !== undefined; })
    .map(function(kv) { return kv.map(encodeURIComponent).join("="); })
    .join("&");
}

// Don't use RegExp literals https://github.com/python-babel/babel/issues/640
const _escapeA = new RegExp('&', 'g'),
      _escapeL = new RegExp('<', 'g'),
      _escapeG = new RegExp('>', 'g'),
      _escapeQ = new RegExp('"', 'g'),
      _escapeP = new RegExp("'", 'g');
function escapeHtml(s: string): string {
  return s
    .replace(_escapeA, "&amp;")
    .replace(_escapeL, "&lt;")
    .replace(_escapeG, "&gt;")
    .replace(_escapeQ, "&quot;")
    .replace(_escapeP, "&#039;");
}

function nextElement(node: Node | null): Node | null {
  while(node && !node.nextSibling) {
    node = node.parentNode;
  }
  if(!node) {
    return null;
  }
  // If the loop above finished, either !node or node.nextSibling != null
  // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
  node = node.nextSibling!;
  while(node.firstChild) {
    node = node.firstChild;
  }
  return node;
}

function getScrollPos() {
  const doc = document.scrollingElement || document.documentElement, body = document.body;
  const x = (doc && doc.scrollLeft || body && body.scrollLeft || 0) - (doc.clientLeft || 0);
  const y = (doc && doc.scrollTop || body && body.scrollTop || 0) - (doc.clientTop || 0);
  return {x: x, y: y};
}

function getCookie(name: string): string | undefined {
  const r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
  return r ? r[1] : undefined;
}

class ApiError {
  status: number;
  message: string;

  constructor(response: Response, message?: string) {
    if(!message) {
      message = "Status " + response.status;
    }
    this.status = response.status;
    this.message = message;
  }

  toString() {
    return this.message;
  }
}

function getJSON(url='', args?: {[k: string]: string}) {
  let query = '';
  if(args) {
    query = '?' + encodeGetParams(args);
  }
  return fetch(
    url + query,
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
    return response.json().catch(function() { throw new ApiError(response, "Invalid JSON"); });
  });
}

function deleteURL(url='', args?: {[k: string]: string}) {
  let query = ''
  if(args) {
    query = encodeGetParams(args);
  }
  const xsrf = getCookie('_xsrf');
  return fetch(
    url + '?' + (xsrf !== undefined ? '_xsrf=' + encodeURIComponent(xsrf) + '&' : '') + query,
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

function postJSON(url='', data={}, args?: {[k: string]: string}) {
  let query = ''
  if(args) {
    query = encodeGetParams(args);
  }
  const xsrf = getCookie('_xsrf');
  return fetch(
    url + '?' + (xsrf !== undefined ? '_xsrf=' + encodeURIComponent(xsrf) + '&' : '') + query,
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
    return response.json().catch(function() { throw new ApiError(response, "Invalid JSON"); });
  });
}

function patchJSON(url='', data={}, args?: {[k: string]: string}) {
  let query = ''
  if(args) {
    query = encodeGetParams(args);
  }
  const xsrf = getCookie('_xsrf');
  return fetch(
    url + '?' + (xsrf !== undefined ? '_xsrf=' + encodeURIComponent(xsrf) + '&' : '') + query,
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
    } else {
      return null;
    }
  });
}

// Returns the byte length of a string encoded in UTF-8
// https://stackoverflow.com/q/5515869/711380
const lengthUTF8 = (function() {
  if(window.TextEncoder) {
    return function lengthUTF8(s: string) {
      return (new TextEncoder('utf-8').encode(s)).length;
    }
  } else {
    return function lengthUTF8(s: string) {
      let l = s.length;
      for(let i = s.length - 1; i >= 0; --i) {
        const code = s.charCodeAt(i);
        if(code > 0x7f && code <= 0x7ff) ++l;
        else if(code > 0x7ff && code <= 0xffff) l += 2;
        if (code >= 0xDC00 && code <= 0xDFFF) i--; // trailing surrogate
      }
      return l;
    }
  }
})();

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

let chunk_offsets: number[] = [];

// Get the document offset from a position
function describePos(node: HTMLElement, offset: number): number | null {
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
function locatePos(pos: number): [Node, number] {
  // Find the right chunk
  let chunk_start = 0;
  for(let i = 0; i < chunk_offsets.length; ++i) {
    if(chunk_offsets[i] > pos) {
      break;
    }
    chunk_start = chunk_offsets[i];
  }

  let offset = pos - chunk_start;
  let node = document.getElementById('doc-offset-' + chunk_start);
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

let current_selection = null;

// Describe the selection e.g. [14, 56]
function describeSelection(): [number, number] | null {
  const sel = window.getSelection();
  if(sel && sel.rangeCount != 0) {
    const range = sel.getRangeAt(0);
    if(!range.collapsed) {
      const start = describePos(range.startContainer, range.startOffset);
      const end = describePos(range.endContainer, range.endOffset);
      if(start !== null && end !== null) {
        return [start, end];
      }
    }
  }
  return null;
}

// Restore a described selection
function restoreSelection(saved: [number, number] | null) {
  const sel = window.getSelection();
  sel.removeAllRanges();
  if(saved !== null) {
    const range = document.createRange();
    const start = locatePos(saved[0]);
    const end = locatePos(saved[1]);
    range.setStart(start[0], start[1]);
    range.setEnd(end[0], end[1]);
    sel.addRange(range);
  }
}

function splitAtPos(pos: [HTMLElement, number], after: boolean): Node {
  const node = pos[0];
  let idx = pos[1];
  if(idx === 0) {
    // Leftmost index: return current node
    return node;
  } else if(idx >= lengthUTF8(node.textContent)) {
    // Rightmost index: return next node
    return nextElement(node);
  } else {
    // Find the character index from the byte index
    let idx_char = 0;
    while(idx > 0) {
      const code = node.textContent.charCodeAt(idx_char);
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
function highlightSelection(saved, id, clickedCallback, title: string) {
  console.log("Highlighting", saved);
  if(saved === null) {
    return;
  }
  const start = splitAtPos(locatePos(saved[0]), false);
  const end = splitAtPos(locatePos(saved[1]), true);

  let node = start;
  while(node != end) {
    const next = nextElement(node);
    if(node.nodeType == 3 && node.textContent) { // TEXT_NODE
      const span = document.createElement('a');
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

const project_name_input: HTMLInputElement = document.getElementById('project-name');
let project_name = project_name_input.value;

const project_description_input: HTMLInputElement = document.getElementById('project-description');
let project_description = project_description_input.value;

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
  const elems = document.getElementsByClassName('project-name');
  for(let i = 0; i < elems.length; ++i) {
    elems[i].textContent = project_name;
  }
  console.log("Project metadata updated");
}

function projectMetadataChanged() {
  if(project_name_input.value != project_name
   || project_description_input.value != project_description) {
    console.log("Posting project metadata update");
    const meta = {
      name: project_name_input.value,
      description: project_description_input.value
    };
    postJSON(
      '/api/project/' + project_id,
      meta
    )
    .then(function() {
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

let current_document = null;
let current_tag = null;
const documents_list = document.getElementById('documents-list');

function linkDocument(elem: HTMLElement, doc_id: number) {
  const url = '/project/' + project_id + '/document/' + doc_id;
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
    const first = documents_list.firstChild;
    if(first.classList
     && first.classList.contains('special-item-button')) {
      break;
    }
    documents_list.removeChild(first);
  }

  // Fill up the list again
  const before = documents_list.firstChild;
  const entries = Object.entries(documents);
  sortByKey(entries, function(e) { return e[1].name; });
  for(let i = 0; i < entries.length; ++i) {
    const doc = entries[i][1];
    const elem = document.createElement('li');
    elem.setAttribute('id', 'document-link-' + doc.id);
    elem.className = 'list-group-item document-link';
    elem.innerHTML =
      '<div class="d-flex justify-content-between align-items-center">' +
      '  <a class="document-link-a">' + escapeHtml(doc.name) + '</a>' +
      '  <a href="javascript:editDocument(' + doc.id + ');" class="btn btn-primary btn-sm">' + gettext("Edit") + '</a>' +
      '</div>';
    documents_list.insertBefore(elem, before);
    const links = elem.getElementsByTagName('a');
    linkDocument(links[0], doc.id);
  }
  if(entries.length == 0) {
    const elem = document.createElement('div');
    elem.className = 'list-group-item disabled';
    elem.textContent = gettext("There are no documents in this project yet.");
    documents_list.insertBefore(elem, before);
  }
  console.log("Documents list updated");
}

updateDocumentsList();

function addDocument(document) {
  documents['' + document.id] = document;
  if(document.id === current_document) {
    // Text direction is the only meaningful thing that can be mutated
    if(document.text_direction === 'RIGHT_TO_LEFT') {
      document_contents.style.direction = 'rtl';
    } else {
      document_contents.style.direction = 'ltr';
    }
  }
  updateDocumentsList();
}

function removeDocument(document_id: number) {
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

const document_add_modal = document.getElementById('document-add-modal');

export function createDocument(): void {
  document.getElementById('document-add-form').reset();
  $(document_add_modal).modal();
}

function basename(filename: string): string {
  if(filename) {
    const idx = Math.max(filename.lastIndexOf('/'), filename.lastIndexOf('\\'));
    if(idx > -1) {
      filename = filename.substring(idx + 1);
    }
  }
  return filename;
}

document.getElementById('document-add-form').addEventListener('submit', function(e) {
  e.preventDefault();
  console.log("Uploading document...");

  const form_data = new FormData();
  let name = document.getElementById('document-add-name').value;
  if(!name) {
    name = basename(document.getElementById('document-add-file').value);
  }
  form_data.append('name', name);
  form_data.append('description',
                   document.getElementById('document-add-description').value);
  form_data.append('file',
                   document.getElementById('document-add-file').files[0]);
  form_data.append('text_direction',
                   document.getElementById('document-add-form').elements['document-add-direction'].value);
  form_data.append('_xsrf', getCookie('_xsrf'));

  const xhr = new XMLHttpRequest();
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
      let error = null;
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

const document_change_modal = document.getElementById('document-change-modal');

export function editDocument(doc_id: number): void {
  document.getElementById('document-change-form').reset();
  document.getElementById('document-change-id').value = '' + doc_id;
  document.getElementById('document-change-name').value = '' + documents['' + doc_id].name;
  document.getElementById('document-change-description').value = '' + documents['' + doc_id].description;
  document.getElementById('document-change-form').elements['document-change-direction'].value = documents['' + doc_id].text_direction;
  $(document_change_modal).modal();
}

document.getElementById('document-change-form').addEventListener('submit', function(e) {
  e.preventDefault();
  console.log("Changing document...");

  const update = {
    name: document.getElementById('document-change-name').value,
    description: document.getElementById('document-change-description').value,
    text_direction: document.getElementById('document-change-form').elements['document-change-direction'].value
  };
  if(!update.name || update.name.length == 0) {
    alert(gettext("Document name cannot be empty"));
    return;
  }

  const doc_id = document.getElementById('document-change-id').value;
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

  const doc_id = document.getElementById('document-change-id').value;
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

const tags_list = document.getElementById('tags-list');
const tags_modal_list = document.getElementById('highlight-add-tags');

function linkTag(elem: HTMLElement, tag_path: string) {
  const url = '/project/' + project_id + '/highlights/' + encodeURIComponent(tag_path);
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

function removeTag(tag_id: number) {
  // Remove from list of tags
  delete tags['' + tag_id];
  // Remove from all highlights
  const hl_entries = Object.entries(highlights);
  for(let i = 0; i < hl_entries.length; ++i) {
    const hl = hl_entries[i][1];
    hl.tags = hl.tags.filter(function(v) { return v != tag_id; });
  }
  updateTagsList();
}

function mergeTags(tag_src: number, tag_dest: number) {
  for(const id in highlights) {
    const hl_tags = highlights[id].tags;

    if(hl_tags.includes(tag_src)) {
      // Remove src tag
      const idx = hl_tags.indexOf(tag_src);
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
  const entries = Object.entries(tags);
  sortByKey(entries, function(e) { return e[1].path; });

  // The list in the left panel
  {
    // Empty the list
    while(tags_list.firstChild) {
      const first = tags_list.firstChild;
      if(first.classList
       && first.classList.contains('special-item-button')) {
        break;
      }
      tags_list.removeChild(first);
    }
    // Fill up the list again
    // TODO: Show this as a tree
    const tree = {};
    const before = tags_list.firstChild;
    for(let i = 0; i < entries.length; ++i) {
      const tag = entries[i][1];
      const elem = document.createElement('li');
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
      const elem = document.createElement('div');
      elem.className = 'list-group-item disabled';
      elem.textContent = gettext("There are no tags in this project yet.");
      tags_list.insertBefore(elem, before);
    }
  }

  // The list in the highlight modal
  {
    // Empty the list
    while(tags_modal_list.firstChild) {
      const first = tags_modal_list.firstChild;
      if(first.classList
       && first.classList.contains('special-item-button')) {
        break;
      }
      tags_modal_list.removeChild(first);
    }
    // Fill up the list again
    // TODO: Show this as a tree
    const tree = {};
    const before = tags_modal_list.firstChild;
    for(let i = 0; i < entries.length; ++i) {
      const tag = entries[i][1];
      const elem = document.createElement('li');
      elem.className = 'tag-name form-check';
      elem.innerHTML =
        '<input type="checkbox" class="form-check-input" value="' + tag.id + '" name="highlight-add-tags" id="highlight-add-tags-' + tag.id + '" />' +
        '<label for="highlight-add-tags-' + tag.id + '" class="form-check-label">' + escapeHtml(tag.path) + '</label>';
      tags_modal_list.insertBefore(elem, before);
    }
    if(entries.length == 0) {
      const elem = document.createElement('li');
      elem.textContent = gettext("no tags");
      tags_modal_list.insertBefore(elem, before);
    }
  }

  console.log("Tags list updated");

  // Re-set all highlights, to update titles
  const hl_entries = Object.entries(highlights);
  for(let i = 0; i < hl_entries.length; ++i) {
    setHighlight(hl_entries[i][1]);
  }

  console.log("Highlights updated");
}

updateTagsList();

function updateTagCount(id: number, delta: number) {
  const tag = tags['' + id];
  tag.count += delta;
  const elem = document.getElementById('tag-' + id + '-count');
  elem.textContent = tag.count;
}

const tag_add_modal = document.getElementById('tag-add-modal');

export function createTag(): void {
  document.getElementById('tag-add-form').reset();
  document.getElementById('tag-add-id').value = '';
  document.getElementById('tag-add-label-new').style.display = '';
  document.getElementById('tag-add-label-change').style.display = 'none';
  document.getElementById('tag-add-cancel').style.display = '';
  document.getElementById('tag-add-delete').style.display = 'none';
  document.getElementById('tag-add-merge').style.display = 'none';
  $(tag_add_modal).modal();
}

export function editTag(tag_id: number): void {
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

  const tag_id = document.getElementById('tag-add-id').value;
  if(tag_id) {
    tag_id = parseInt(tag_id);
  } else {
    tag_id = null;
  }
  const tag_path = document.getElementById('tag-add-path').value;
  if(!tag_path) {
    alert(gettext("Invalid tag name"));
    return;
  }
  let req;
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
  const tag_id_str = document.getElementById('tag-add-id').value;
  if(tag_id_str) {
    const tag_id = parseInt(tag_id_str);
    if(!window.confirm(gettext("Are you sure you want to delete the tag '%(tag)s'?", {tag: tags[tag_id].path}))) {
      e.preventDefault();
      return;
    }
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
  e.preventDefault();

  const tag_id_str = document.getElementById('tag-add-id').value;
  if(!tag_id_str)
    return;
  const tag_id = parseInt(tag_id_str);

  document.getElementById('tag-merge-form').reset();

  // Set source tag
  document.getElementById('tag-merge-src-id').value = '' + tag_id;
  document.getElementById('tag-merge-src-name').value = tags['' + tag_id].path;

  // Empty target tag <select>
  const target = document.getElementById('tag-merge-dest');
  target.innerHTML = '';

  // Fill target tag <select>
  const entries = Object.entries(tags);
  sortByKey(entries, function(e) { return e[1].path; });
  for(let i = 0; i < entries.length; ++i) {
    if(entries[i][0] == '' + tag_id) {
      // Can't merge into itself
      continue;
    }
    const option = document.createElement('option');
    option.setAttribute('value', entries[i][0]);
    option.innerText = entries[i][1].path;
    target.appendChild(option);
  }

  $(document.getElementById('tag-merge-modal')).modal();
});

// Merge modal submit button
document.getElementById('tag-merge-form').addEventListener('submit', function(e) {
  e.preventDefault();

  const tag_src_str = document.getElementById('tag-merge-src-id').value;
  if(!tag_src_str)
    return;
  const tag_src = parseInt(tag_src_str);

  const tag_dest_str = document.getElementById('tag-merge-dest').value;
  if(!tag_dest_str)
    return;
  const tag_dest = parseInt(tag_dest_str);

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
  const id = '' + highlight.id;
  if(highlights[id]) {
    removeHighlight(id);
  }
  highlights[id] = highlight;
  let tag_names = highlight.tags.map(function(id) { return tags[id].path; });
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
function removeHighlight(id: number) {
  id = '' + id;
  if(!highlights[id]) {
    return;
  }

  delete highlights[id];
  console.log("Highlight removed:", id);

  // Loop over highlight-<id> elements
  const elements = document.getElementsByClassName('highlight-' + id);
  for(let i = 0; i < elements.length; ++i) {
    // Move children up and delete this element
    const node = elements[i];
    while(node.firstChild) {
      node.parentNode.insertBefore(node.firstChild, node);
    }
    node.parentNode.removeChild(node);
  }
}

// Backlight
const backlight_checkbox = document.getElementById('backlight');
backlight_checkbox.addEventListener('change', function() {
  const classes = document.getElementById('document-view').classList;
  if(backlight_checkbox.checked == classes.contains('backlight')) {
    // all good
  } else if(backlight_checkbox.checked) {
    classes.add('backlight');
  } else {
    classes.remove('backlight');
  }
});


/*
 * Add highlight
 */

const highlight_add_modal = document.getElementById('highlight-add-modal');

// Updates current_selection and visibility of the controls
function selectionChanged() {
  current_selection = describeSelection();
  const hlinfo = document.getElementById('hlinfo');
  if(current_selection !== null) {
    const current_range = window.getSelection().getRangeAt(0);
    if(current_range.endOffset > 0) {
      const last_char_range = document.createRange();
      last_char_range.setStart(current_range.endContainer, current_range.endOffset - 1);
      last_char_range.setEnd(current_range.endContainer, current_range.endOffset);
      const rect = last_char_range.getClientRects().item(0);
      const scrollPos = getScrollPos();
      hlinfo.style.left = ((rect.x || rect.left) + rect.width) + 'px';
      hlinfo.style.top = ((rect.y || rect.top) + rect.height + scrollPos.y + 20) + 'px';
      hlinfo.style.display = 'block';
    } else {
      // We are in a weird situation where the end of the selection is in
      // an empty node. We just don't move the popup, seems to work in practice
    }
  } else {
    hlinfo.style.display = 'none';
  }
}
document.addEventListener('selectionchange', selectionChanged);

export function createHighlight(selection: [number, number]): void {
  document.getElementById('highlight-add-id').value = '';
  document.getElementById('highlight-add-start').value = selection[0];
  document.getElementById('highlight-add-end').value = selection[1];
  document.getElementById('highlight-add-form').reset();
  $(highlight_add_modal).modal().drags({handle: '.modal-header'});
}

function editHighlight() {
  document.getElementById('highlight-add-form').reset();
  const id = this.getAttribute('data-highlight-id');
  document.getElementById('highlight-add-id').value = id;
  document.getElementById('highlight-add-start').value = highlights[id].start_offset;
  document.getElementById('highlight-add-end').value = highlights[id].end_offset;
  const hl_tags = highlights['' + id].tags;
  for(let i = 0; i < hl_tags.length; ++i) {
    document.getElementById('highlight-add-tags-' + hl_tags[i]).checked = true;
  }
  $(highlight_add_modal).modal().drags({handle: '.modal-header'});
}

// Save highlight button
document.getElementById('highlight-add-form').addEventListener('submit', function(e) {
  e.preventDefault();
  const highlight_id = document.getElementById('highlight-add-id').value;
  const selection = [
    parseInt(document.getElementById('highlight-add-start').value),
    parseInt(document.getElementById('highlight-add-end').value)
  ];
  const hl_tags = [];
  const entries = Object.entries(tags);
  for(let i = 0; i < entries.length; ++i) {
    const id = entries[i][1].id;
    if(document.getElementById('highlight-add-tags-' + id).checked) {
      hl_tags.push(id);
    }
  }
  let req;
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
document.getElementById('highlight-delete').addEventListener('click', function() {
  let highlight_id = document.getElementById('highlight-add-id').value;
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

function addMember(login: string, privileges: string) {
  members[login] = {privileges: privileges};
}

function removeMember(login: string) {
  delete members[login];
}

const members_modal = document.getElementById('members-modal');
const members_initial = {};
const members_displayed = {};

function _memberRow(login: string, user: {privileges: string}, can_edit: boolean, is_self: boolean) {
  const elem = document.createElement('div');
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

  elem.querySelector('button').addEventListener('click', function() {
    elem.parentNode.removeChild(elem);
    delete members_displayed[login];
  });

  return elem;
}

export function showMembers(): void {
  document.getElementById('members-add').reset();

  can_edit = members[user_login].privileges == 'ADMIN';

  if(can_edit) {
    document.getElementById('members-add-fields').removeAttribute('disabled');
  } else {
    document.getElementById('members-add-fields').setAttribute('disabled', 1);
  }

  const entries = Object.entries(members);
  sortByKey(entries, function(e) { return e[0]; });
  console.log(
    "Members:",
    entries.map(function(e) { return e[0] + " (" + e[1].privileges + ")"; })
    .join(", ")
  );

  // Empty the list
  const current_members = document.getElementById('members-current');
  current_members.innerHTML = '';

  // Fill it back up
  for(let i = 0; i < entries.length; ++i) {
    const login = entries[i][0];
    const user = entries[i][1];
    const elem = _memberRow(login, user, can_edit, login == user_login);

    current_members.appendChild(elem);
  }

  // Store current state so that we can compare later
  members_initial = Object.assign({}, members);
  members_displayed = Object.assign({}, members);

  $(members_modal).modal();
}

document.getElementById('members-add').addEventListener('submit', function(e) {
  e.preventDefault();

  const login = document.getElementById('member-add-name').value.toLowerCase();
  if(!login) { return; }
  const privileges = document.getElementById('member-add-privileges').value;

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
      const elem = _memberRow(login, {privileges: privileges});
      const current_members = document.getElementById('members-current');
      current_members.insertBefore(elem, current_members.firstChild);
      members_displayed[login] = true;

      document.getElementById('members-add').reset();
    } else {
      alert(gettext("This user doesn't exist!"));
    }
  })
});

function sendMembersPatch() {
  const patch = {};

  const members_before = Object.assign({}, members_initial);

  const rows = document.getElementById('members-current').querySelectorAll('.members-item');
  for(let i = 0; i < rows.length; ++i) {
    const row = rows[i];
    const login = row.querySelector('.members-item-login').textContent;
    const privileges = row.querySelector('select').value;

    // Add to patch, if different from stored version
    if(!members_before[login] || members_before[login].privileges != privileges) {
      patch[login] = {privileges: privileges};
    }

    // Remove from object, so what's left are the removed members
    delete members_before[login];
  }

  // Remove the members that are left
  const entries = Object.entries(members_before);
  for(let i = 0; i < entries.length; ++i) {
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

const document_contents = document.getElementById('document-contents');
const export_button = document.getElementById('export-button');

function loadDocument(document_id: number | null) {
  if(document_id === null) {
    document_contents.style.direction = 'ltr';
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
    for(let i = 0; i < result.contents.length; ++i) {
      const chunk = result.contents[i];
      const elem = document.createElement('div');
      elem.setAttribute('id', 'doc-offset-' + chunk.offset);
      elem.innerHTML = chunk.contents;
      document_contents.appendChild(elem);
      chunk_offsets.push(chunk.offset);
    }
    if(result.text_direction === 'RIGHT_TO_LEFT') {
      document_contents.style.direction = 'rtl';
    } else {
      document_contents.style.direction = 'ltr';
    }
    current_document = document_id;
    const document_links = document.getElementsByClassName('document-link-current');
    for(let i = document_links.length - 1; i >= 0; --i) {
      document_links[i].classList.remove('document-link-current');
    }
    document.getElementById('document-link-' + current_document).classList.add('document-link-current');
    current_tag = null;
    const tag_links = document.getElementsByClassName('tag-current');
    for(let i = tag_links.length - 1; i >= 0; --i) {
      tag_links[i].classList.remove('tag-current');
    }
    console.log("Loaded document", document_id);
    for(let i = 0; i < result.highlights.length; ++i) {
      setHighlight(result.highlights[i]);
    }
    console.log("Loaded " + result.highlights.length + " highlights");

    // Update export button
    export_button.style.display = '';
    const items = export_button.getElementsByClassName('dropdown-item');
    for(let i = 0; i < items.length; ++i) {
      const ext = items[i].getAttribute('data-extension');
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

function loadTag(tag_path: string, page?: number) {
  if(page === undefined) {
    page = 1;
  }
  showSpinner();
  getJSON(
    '/api/project/' + project_id + '/highlights/' + encodeURIComponent(tag_path) + '?page=' + page
  )
  .then(function(result) {
    console.log("Loaded highlights for tag", tag_path || "''");
    document_contents.style.direction = 'ltr';
    current_tag = tag_path;
    current_document = null;
    const document_links = document.getElementsByClassName('document-link-current');
    for(let i = document_links.length - 1; i >= 0; --i) {
      document_links[i].classList.remove('document-link-current');
    }
    // No need to clear the 'tag-current', we are calling updateTagsList() below
    document_contents.innerHTML = '';
    highlights = {};
    for(let i = 0; i < result.highlights.length; ++i) {
      const hl = result.highlights[i];
      const content = document.createElement('div');
      if(hl.text_direction === 'RIGHT_TO_LEFT') {
        content.style.direction = 'rtl';
      } else {
        content.style.direction = 'ltr';
      }
      content.innerHTML = result.highlights[i].content;
      const elem = document.createElement('div');
      elem.className = 'highlight-entry';
      elem.setAttribute('id', 'highlight-entry-' + hl.id);
      elem.appendChild(content);
      elem.appendChild(document.createTextNode(' '));

      const doclink = document.createElement('a');
      doclink.className = 'badge badge-light';
      doclink.textContent = documents['' + hl.document_id].name;
      linkDocument(doclink, hl.document_id);
      elem.appendChild(doclink);
      elem.appendChild(document.createTextNode(' '));

      const tag_names = hl.tags.map(function(tag) { return tags['' + tag].path; });
      tag_names.sort();
      for(let j = 0; j < tag_names.length; ++j) {
        if(j > 0) {
          elem.appendChild(document.createTextNode(' '));
        }
        const taglink = document.createElement('a');
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
      let item;
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
        const link = document.createElement('a');
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
      const pagination_ul = document.createElement('ul');
      pagination_ul.className = 'pagination justify-content-center';
      const min_page = Math.max(2, page - 2);
      const max_page = Math.min(result.pages - 1, page + 2);

      // Previous button
      pagination_ul.appendChild(makePageLink(page - 1, "Previous", false, page > 1));
      // Page 1
      pagination_ul.appendChild(makePageLink(1, 1, 1 === page, 1 !== page));
      // "..." between 1 and other pages, if appropriate
      if(min_page > 2) {
        pagination_ul.appendChild(makePageLink(page, "...", false, false));
      }
      // Other pages
      for(let i = min_page; i <= max_page; ++i) {
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
    const items = export_button.getElementsByClassName('dropdown-item');
    for(let i = 0; i < items.length; ++i) {
      const ext = items[i].getAttribute('data-extension');
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
    {
      const document_url_re = new RegExp('/project/([0-9]+)/document/([0-9]+)');
      // Don't use RegExp literals https://github.com/python-babel/babel/issues/640
      const m = window.location.pathname.match(document_url_re);
      if(m) {
        loadDocument(parseInt(m[2]));
        return;
      }
    }
    // Or a tag
    {
      const tag_url_re = new RegExp('/project/([0-9]+)/highlights/([^/]*)');
      const m = window.location.pathname.match(tag_url_re);
      if(m) {
        loadTag(decodeURIComponent(m[2]));
        return;
      }
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
let windowLastActive = new Date();
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

let lastPoll = null;
let polling = true;

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
    if(result.reload) {
      console.log("Server sent signal to reload");
      window.location.reload();
      return;
    }
    for(let i = 0; i < result.events.length; ++i) {
      const event = result.events[i];
      if(event.type === 'project_meta') {
        setProjectMetadata({
          project_name: event.project_name,
          description: event.description
        });
      } else if(event.type === 'document_add') {
        addDocument({
          id: event.document_id,
          name: event.document_name,
          description: event.description,
          text_direction: event.text_direction
        });
      } else if(event.type === 'document_delete') {
        removeDocument(event.document_id);
      } else if(event.type === 'highlight_add') {
        setHighlight({
          id: event.highlight_id,
          start_offset: event.start_offset,
          end_offset: event.end_offset,
          tags: event.tags
        });
      } else if(event.type === 'highlight_delete') {
        removeHighlight(event.highlight_id);
      } else if(event.type === 'tag_add') {
        addTag({
          id: event.tag_id,
          path: event.tag_path,
          description: event.description
        });
      } else if(event.type === 'tag_delete') {
        removeTag(event.tag_id);
      } else if(event.type === 'tag_merge') {
        mergeTags(event.src_tag_id, event.dest_tag_id);
      } else if(event.type === 'member_add') {
        addMember(event.member, event.privileges);
      } else if(event.type === 'member_remove') {
        removeMember(event.member);
      }

      if('tag_count_changes' in event) {
        const entries = Object.entries(event.tag_count_changes);
        for(let i = 0; i < entries.length; ++i) {
          updateTagCount(entries[i][0], entries[i][1]);
        }
      }
      last_event = event.id;
    }

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
