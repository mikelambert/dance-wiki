# -*- coding: utf-8 -*-
# encoding=utf-8

import model
import util

from google.appengine.api import memcache

DEFAULT_HELP = """This wiki is using [Daring Fireball's Markdown syntax](https://daringfireball.net/projects/markdown/syntax). The below documentation will help you get started. You may also checkout a neat [Markdown Tutorial](http://www.markdowntutorial.com/) that will teach you the syntax in a few minutes.

Paragraphs, Headers, Blockquotes
--------------------------------

A paragraph is simply one or more consecutive lines of text, separated by one or more blank lines. (A blank line is any line that looks like a blank line — a line containing nothing but spaces or tabs is considered blank.) Normal paragraphs should not be indented with spaces or tabs.

Markdown offers two styles of headers: Setext and atx. Setext-style headers for `<h1>` and `<h2>` are created by “underlining” with equal signs (=) and hyphens (-), respectively. To create an atx-style header, you put 1-6 hash marks (#) at the beginning of the line — the number of hashes equals the resulting HTML header level.


    A First Level Header
    ====================

    A Second Level Header
    ---------------------

    Now is the time for all good men to come to
    the aid of their country. This is just a
    regular paragraph.

    The quick brown fox jumped over the lazy
    dog's back.

    ### Header 3

    > This is a blockquote.
    >
    > This is the second paragraph in the blockquote.
    >
    > ## This is an H2 in a blockquote

Output:
____
A First Level Header
====================

A Second Level Header
---------------------

Now is the time for all good men to come to
the aid of their country. This is just a
regular paragraph.

The quick brown fox jumped over the lazy
dog's back.

### Header 3

> This is a blockquote.
>
> This is the second paragraph in the blockquote.
>
> ## This is an H2 in a blockquote
____

Phrase Emphasis
---------------

Markdown uses asterisks and underscores to indicate spans of emphasis.

Markdown:

    Some of these words *are emphasized*.
    Some of these words _are emphasized also_.

    Use two asterisks for **strong emphasis**.
    Or, if you prefer, __use two underscores instead__.

Output:
____
Some of these words *are emphasized*.
Some of these words _are emphasized also_.

Use two asterisks for **strong emphasis**.
Or, if you prefer, __use two underscores instead__.
____

Lists
====

Unordered (bulleted) lists use asterisks, pluses, and hyphens (*, +, and -) as list markers. These three markers are interchangable; this:

    *   Candy.
    *   Gum.
    *   Booze.

this:

    +   Candy.
    +   Gum.
    +   Booze.

and this:

    -   Candy.
    -   Gum.
    -   Booze.

all produce the same output:
____
-   Candy.
-   Gum.
-   Booze.
____

Ordered (numbered) lists use regular numbers, followed by periods, as list markers:

    1.  Red
    2.  Green
    3.  Blue

Output:
____
1.  Red
2.  Green
3.  Blue
____

If you put blank lines between items, you’ll get <p> tags for the list item text. You can create multi-paragraph list items by indenting the paragraphs by 4 spaces or 1 tab:

    *   A list item.

        With multiple paragraphs.

    *   Another item in the list.

Output:
____
*   A list item.

    With multiple paragraphs.

*   Another item in the list.
____

Links
-------
Markdown supports two styles for creating links: inline and reference. With both styles, you use square brackets to delimit the text you want to turn into a link.

Inline-style links use parentheses immediately after the link text. For example:

    This is an [example link](http://example.com/).

Output:
____
This is an [example link](http://example.com/).
____

Optionally, you may include a title attribute in the parentheses:

    This is an [example link](http://example.com/ "With a Title").

Output:
____
This is an [example link](http://example.com/ "With a Title").
____

Reference-style links allow you to refer to your links by names, which you define elsewhere in your document:

    I get 10 times more traffic from [Google][1] than from [Yahoo][2] or [MSN][3].

    [1]: http://google.com/        "Google"
    [2]: http://search.yahoo.com/  "Yahoo Search"
    [3]: http://search.msn.com/    "MSN Search"

Output:
____
I get 10 times more traffic from [Google][1] than from [Yahoo][2] or [MSN][3].

[1]: http://google.com/        "Google"
[2]: http://search.yahoo.com/  "Yahoo Search"
[3]: http://search.msn.com/    "MSN Search"
____

The title attribute is optional. Link names may contain letters, numbers and spaces, but are not case sensitive:

    I start my morning with a cup of coffee and [The New York Times][NY Times].

    [ny times]: http://www.nytimes.com/

Output:
____
I start my morning with a cup of coffee and [The New York Times][NY Times].

[ny times]: http://www.nytimes.com/
____

Images
---------
Image syntax is very much like link syntax.

Inline (titles are optional):

    ![alt text](/path/to/img.jpg "Title")

Reference-style:

    ![alt text][id]

    [id]: /path/to/img.jpg "Title"

Both of the above examples produce the same output:
____
![alt text](/gae-wiki-static/scripts/images/markitup.png "Title")
____

Code
-------

In a regular paragraph, you can create code span by wrapping text in backtick quotes. Any ampersands (&) and angle brackets (< or >) will automatically be translated into HTML entities. This makes it easy to use Markdown to write about HTML example code:

    I strongly recommend against using any `<blink>` tags.

    I wish SmartyPants used named entities like `&mdash;` instead of decimal-encoded entites like `&#8212;`.

Output:
____
I strongly recommend against using any `<blink>` tags.

I wish SmartyPants used named entities like `&mdash;` instead of decimal-encoded entites like `&#8212;`.
____

To specify an entire block of pre-formatted code, indent every line of the block by 4 spaces or 1 tab. Just like with code spans, &, <, and > characters will be escaped automatically.

Markdown:

    If you want your page to validate under XHTML 1.0 Strict, you've got to put paragraph tags in your blockquotes:
        <blockquote>
            <p>For example.</p>
        </blockquote>

Output:
____
If you want your page to validate under XHTML 1.0 Strict,
you've got to put paragraph tags in your blockquotes:

    <blockquote>
        <p>For example.</p>
    </blockquote>
____
"""

def get_page():
    """Returns the page that hosts the help."""
    page = model.WikiContent.gql('WHERE title = :1', "gaewiki:syntax").get()
    if page is None:
        page = model.WikiContent(title="gaewiki:syntax", body=DEFAULT_HELP.decode('utf-8'))
        page.put()
    return page

def get_all():
    help_page = memcache.get('gaewiki:syntax')
    if help_page is None:
        help_page = util.parse_page(get_page().body)
        memcache.set('gaewiki:syntax', help_page)
    return help_page['text']