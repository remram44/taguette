const treeview_tags = $('#treeview-tags');
const treeview_tags_highlight = $('#treeview-tags-highlight');

const DEFAULT_LEVEL_OPTION = 5

const SPLICE_DEFAULT_INDEX = 1;
const DEFAULT_COUNT = 0;


// Find a tag by its ID or path in the tag tree
const findTag = (id) => {
    // Recursive function to search for a tag
    const recursiveSearch = (tag) => {
        // Check if current tag matches the search criteria
        if (tag.id === parseInt(id) || tag.path === id) {
            return tag;
        }

        // Search in children if present
        if (tag.children) {
            for (const child of tag.children) {
                const found = recursiveSearch(child);
                if (found) {
                    return found;
                }
            }
        }

        return null;
    };

    // Iterate through all top-level tags
    for (const tag of tags) {
        const found = recursiveSearch(tag);
        if (found) {
            return found;
        }
    }

    return null;
}

// Main function to add or update a tag
function addTag(tag) {
    const existingTag = findTag(tag.id);

    if (existingTag) {
        updateExistingTag(existingTag, tag);
    } else {
        addNewTag(tag);
    }

    // Update the list of tags (presumably in the UI)
    updateTagsList();
}

// Function to add a new tag to the tag tree
function addNewTag(tag) {
    const newTag = {
        ...tag,
        count: DEFAULT_COUNT,
        count_document: DEFAULT_COUNT,
        children: []
    };

    if (tag.parent) {
        const parentTag = findTag(tag.parent);
        if (!parentTag) {
            return;
        }
        parentTag.children = parentTag.children || [];
        parentTag.children.push(newTag);
    } else {
        tags.push(newTag);
    }
}

// Function to update an existing tag
function updateExistingTag(existingTag, newTag) {
    if (newTag.parent) {
        handleExistingTagWithParent(existingTag, newTag);
    } else {
        handleExistingTagWithoutParent(existingTag, newTag);
    }
}

// Handle updating an existing a tag that has a parent
function handleExistingTagWithParent(existingTag, newTag) {
    const newParent = findTag(newTag.parent);
    if (!newParent) {
        return;
    }

    if (!existingTag.parent) {
        // If the existing tag had no parent, move it to the new parent
        findTagAndDelete(newTag.id);
        moveTagToNewParent(existingTag, newParent);
    } else if (newTag.parent !== existingTag.parent) {
        // If the tag is moving to a different parent
        const oldParent = findTag(existingTag.parent);
        removeTagFromParent(existingTag, oldParent);
        moveTagToNewParent(existingTag, newParent);
    }

    // Update the existing tag with new properties
    Object.assign(existingTag, newTag);
}

// Handle updating an existing tag that has no parent
function handleExistingTagWithoutParent(existingTag, newTag) {
    if (existingTag.parent) {
        // If the existing tag had a parent, remove it from the parent and add to top level
        const oldParent = findTag(existingTag.parent);
        removeTagFromParent(existingTag, oldParent);
        tags.push(existingTag);
    }
    // Update the existing tag with new properties
    Object.assign(existingTag, newTag);
}

// Move a tag to a new parent
function moveTagToNewParent(tag, newParent) {
    newParent.children = newParent.children || [];
    newParent.children.push(tag);
}

// Remove a tag from its parent
function removeTagFromParent(tag, parent) {
    if (!parent || !parent.children) return;
    const index = parent.children.findIndex(child => child.id === tag.id);
    if (index !== -1) {
        parent.children.splice(index, 1);
    }
}

const findTagAndDelete = (id) => {

    const tag = findTag(parseInt(id));

    if (tag.parent) {
        const parent = findTag(tag.parent);
        const indexToDelete = tag.children.findIndex(item => item.id === tag.id);
        parent.children.splice(indexToDelete, SPLICE_DEFAULT_INDEX);
    } else {
        const indexToDelete = tags.findIndex(item => item.id === tag.id);
        tags.splice(indexToDelete, SPLICE_DEFAULT_INDEX);
    }
}

// Create tags tree nodes
function convertToTreeNode(data, includeTags) {
    return data.map(item => {
        const node = {
            id: item.id,
            text: item.path,
            selectable: true,
            nodes: item.children.length > 0 ? convertToTreeNode(item.children, includeTags) : undefined
        };

        if (includeTags) {
            node.tags = [`${item.count}`];
        }

        return node;
    });
}

function initTagsTreeview(collapse = true,  filterTags = null) {

    if (filterTags == null) {
        filterTags = tags
    }

    const treeData = convertToTreeNode(filterTags, true);

    const options = {
        customContent: true,
        data: treeData,
        showBorder: true,
        levels: DEFAULT_LEVEL_OPTION,
        nodeContentSelector: 'a',
        nodeContentAttributes: {
            href: '#',
            class: 'tag-text',
            style: 'text-decoration: none;'
        },
        customizeNode: function(element, node, tree) {
            element.attr('id', `tag-node-${node.id}`);
        },
        customizeBadges: function(container, node, tree) {
            container.addClass('d-flex align-items-center');
            if (node.tags && node.tags.length > 0) {
                container.append($('<span>', {
                    class: 'badge badge-secondary rounded-pill ms-1',
                    text: node.tags[0]
                }));
                container.append($('<a>', {
                    href: 'javascript:void(0);',
                    class: 'btn btn-primary btn-sm  ms-2',
                    text: 'Edit',
                    click: function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        editTag(node.id);
                    }
                }));
            }
        },
        showTags: true
    };

    treeview_tags.treeview(options);

    if (collapse) {
        treeview_tags.treeview('collapseAll');
    }

    treeview_tags.on('nodeSelected', function (event, data) {
        const tag_path = data.text;
        const url = `${base_path}/project/${project_id}/highlights/${encodeURIComponent(tag_path)}`;
        event.preventDefault();
        window.history.pushState({tag_path: tag_path}, `Tag ${tag_path}`, url);
        loadTag(tag_path);
    });
}

function initTagsHighlightTreeview(collapse = true, filterTags = null) {

    if (filterTags == null) {
        filterTags = tags
    }

    const treeData = convertToTreeNode(filterTags, false);

    const options = {
        customContent: true,
        data: treeData,
        showBorder: true,
        nodeContentSelector: 'a',
        nodeContentAttributes: {
            href: '#',
            class: 'tag-text',
            style: 'text-decoration: none;'
        },
        customizeNode: function(element, node, tree) {
            element.attr('id', `tag-node-highlight-${node.id}`);
        },
        multiSelect: true,
    };

    treeview_tags_highlight.treeview(options);

    if (collapse) {
        treeview_tags_highlight.treeview('collapseAll');
    }
}
