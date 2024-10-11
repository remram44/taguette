const tag_hierarchy_select = $('#tag-hierarchy-select');
const tag_hierarchy_merge_select = $('#tag-hierarchy-merge-select');
const hs_menu_inner = $('.hs-menu-inner');
const hs_menu_inner_merge = $('.hs-menu-inner-merge');

const DEFAULT_LEVEL = 1;

function addDefaultValue(parentContainer) {
    const li = $("<li>");
    const a = $("<a>").addClass("dropdown-item")
        .attr("data-value", '')
        .attr("data-default-selected", '')
        .attr("data-level", DEFAULT_LEVEL)
        .text('None');
    li.append(a);

    parentContainer.append(li);
}

function generateTagHierarchyItem(data, parentContainer, level) {

    $.each(data, function (index, item) {
        const li = $("<li>");
        const a = $("<a>").addClass("dropdown-item")
            .attr("data-value", item.id)
            .attr("data-level", level)
            .attr("href", "#")
            .text(item.path);

        li.append(a);

        parentContainer.append(li);

        if (item.children && item.children.length > 0) {
            generateTagHierarchyItem(item.children, parentContainer, level + DEFAULT_LEVEL);
        }
    });
}

function initTagHierarchySelect() {

    initHierarchySelect(hs_menu_inner, tag_hierarchy_select)
}

function initMergeTagHierarchySelect() {

    initHierarchySelect(hs_menu_inner_merge, tag_hierarchy_merge_select, false);
}

function initHierarchySelect(menu, select, withDefault = true) {

    menu.html('');

    if(withDefault) {
        addDefaultValue(menu);
    }

    generateTagHierarchyItem(tags, menu, DEFAULT_LEVEL);

    select.hierarchySelect({
        width: 'auto'
    });
}