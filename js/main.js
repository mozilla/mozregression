
$(function() {
    /*
     * For each headline with an id attribute, add a permalink to it.
     *
     * This is done because kramdown write ids automatically to headers,
     * but do not add a user friendly way to use them.
     */
    $("h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]").each(function() {
        var section = $(this);
        var headerlink = $('<a class="headerlink" href="#'
                       + section.attr('id') +
                       '" title="Permalink to this headline">¶</a>');
        section.append(' ');
        section.append(headerlink);
        // only show the permalink on mouser over
        headerlink.hide();
        section.hover(function() {
            headerlink.show();
        }, function() {
            headerlink.hide();
        });
    });
});
