from bs4 import BeautifulSoup, NavigableString


def find_pos(node, offset, after):
    """Find a position in an HTML document.
    """
    indices = []
    while True:
        if getattr(node, 'contents', None):
            indices.append(0)
            node = node.contents[0]
        else:
            if isinstance(node, NavigableString):
                nb = len(node.string.encode('utf-8'))
                if (after and nb > offset) or (not after and nb >= offset):
                    break
                else:
                    offset -= nb
            while not node.next_sibling:
                indices.pop()
                node = node.parent
            indices[-1] += 1
            node = node.next_sibling
    return node, offset, indices


def delete_left(node, indices):
    """Delete the left part of an HTML tree.
    """
    for idx in indices:
        del node.contents[:idx]
        node = node.contents[0]


def delete_right(node, indices):
    """Delete the right part of an HTML tree.
    """
    for idx in indices:
        del node.contents[idx + 1:]
        node = node.contents[idx]


def extract(html, start, end):
    """Extract a snippet out of an HTML document.

    Locations are computed over UTF-8 bytes, and doesn't count HTML tags.

    Extraction is aware of tags, so:

    >>> '<p><u>Hello</u> there <i>World</i></p>'[17:27]
    'here <i>Wo'
    >>> extract('<p><u>Hello</u> there <i>World</i></p>', 7, 14)
    '<p>here <i>Wo</i></p>'
    """
    soup = BeautifulSoup(html, 'html5lib')

    # Trim the right side later, because that doesn't mess our start position
    e = find_pos(soup, end, False)
    e[0].replace_with(NavigableString(e[0].string[:e[1]]))
    delete_right(soup, e[2])

    # Trim the left side
    s = find_pos(soup, start, True)
    s[0].replace_with(NavigableString(s[0].string[s[1]:]))
    delete_left(soup, s[2])

    # Remove everything but body
    body = soup.body
    soup.clear()
    soup.append(body)

    # Remove the body tag itself to only have the contents
    soup.body.unwrap()

    # Back to text
    return str(soup)
