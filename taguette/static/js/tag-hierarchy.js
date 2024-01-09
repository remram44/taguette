$(document).ready(function () {
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
                generateTagHierarchyItem(item.children, parentContainer, level + 1);
            }
        });
    }

    generateTagHierarchyItem(tags, $('.hs-menu-inner'), 1);

    $('#tag-hierarchy-select').hierarchySelect({
        width: 'auto'
    });

});