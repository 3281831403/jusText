# -*- coding: utf-8 -*-

"""
Copyright (c) 2011 Jan Pomikalek

This software is licensed as described in the file LICENSE.rst.
"""

from __future__ import absolute_import
from __future__ import division, print_function, unicode_literals

import codecs
import re
import lxml.html
import lxml.sax

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

from lxml.html.clean import Cleaner
from xml.sax.handler import ContentHandler
from .paragraph import Paragraph
from ._compat import unicode
from .utils import is_blank


MAX_LINK_DENSITY_DEFAULT = 0.2
LENGTH_LOW_DEFAULT = 70
LENGTH_HIGH_DEFAULT = 200
STOPWORDS_LOW_DEFAULT = 0.30
STOPWORDS_HIGH_DEFAULT = 0.32
NO_HEADINGS_DEFAULT = False
# Short and near-good headings within MAX_HEADING_DISTANCE characters before
# a good paragraph are classified as good unless --no-headings is specified.
MAX_HEADING_DISTANCE_DEFAULT = 200
PARAGRAPH_TAGS = frozenset({
    'body', 'blockquote', 'caption', 'center', 'col', 'colgroup', 'dd',
    'div', 'dl', 'dt', 'fieldset', 'form', 'legend', 'optgroup', 'option',
    'p', 'pre', 'table', 'td', 'textarea', 'tfoot', 'th', 'thead', 'tr',
    'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
})
DEFAULT_ENCODING = 'utf8'
DEFAULT_ENC_ERRORS = 'replace'
CHARSET_META_TAG_PATTERN = re.compile(br"""<meta[^>]+charset=["']?([^'"/>\s]+)""", re.IGNORECASE)
XML_ENCODING_DECLARATION_PATTERN = re.compile(
    br"""^\s*<\?xml[^>]*?encoding\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
XML_DECLARATION_TEXT_PATTERN = re.compile(r"""^\s*<\?xml[^>]*?\?>""", re.IGNORECASE)
# Only the beginning of the document is inspected for a <meta> charset, so
# that a charset-looking string in the body is never mistaken for the page
# encoding. HTML5 uses the same 1024 byte prescan window.
HTML_ENCODING_SNIFF_BYTES = 1024
BYTE_ORDER_MARKS = (
    # UTF-32 must be checked before UTF-16, its BOM starts the same way
    (codecs.BOM_UTF32_LE, 'utf-32'),
    (codecs.BOM_UTF32_BE, 'utf-32'),
    (codecs.BOM_UTF8, 'utf-8-sig'),
    (codecs.BOM_UTF16_LE, 'utf-16'),
    (codecs.BOM_UTF16_BE, 'utf-16'),
)
GOOD_OR_BAD = {'good', 'bad'}


class JustextError(Exception):
    "Base class for jusText exceptions."


class JustextInvalidOptions(JustextError):
    pass


def _strip_bom(text):
    """Removes a decoded byte order mark from the beginning of `text`."""
    if text.startswith('\ufeff'):
        return text[1:]
    return text


def _try_decode(html, encoding, errors):
    """
    Decodes `html` using `encoding` or returns `None` if the encoding is
    unknown. Decoding errors are propagated to the caller.
    """
    try:
        codecs.lookup(encoding)
    except LookupError:
        return None
    return html.decode(encoding, errors)


def _detect_bom_encoding(html):
    """Returns the encoding declared by a byte order mark or `None`."""
    for bom, encoding in BYTE_ORDER_MARKS:
        if html.startswith(bom):
            return encoding
    return None


def _detect_xml_declaration_encoding(html):
    """Returns the encoding from an XML declaration at the start or `None`."""
    match = XML_ENCODING_DECLARATION_PATTERN.match(html)
    if not match:
        return None
    try:
        return match.group(1).decode("ascii")
    except UnicodeDecodeError:
        return None


def _detect_meta_charset_encoding(html):
    """
    Returns the encoding from a <meta> charset declared at the beginning of
    the document or `None`. Only the first `HTML_ENCODING_SNIFF_BYTES` bytes
    are inspected so a charset mentioned later in the document (e.g. in the
    body text) is never mistaken for the page encoding.
    """
    match = CHARSET_META_TAG_PATTERN.search(html[:HTML_ENCODING_SNIFF_BYTES])
    if not match:
        return None
    try:
        return match.group(1).decode("ascii")
    except UnicodeDecodeError:
        return None


def html_to_dom(html, default_encoding=DEFAULT_ENCODING, encoding=None, errors=DEFAULT_ENC_ERRORS):
    """Converts HTML to DOM."""
    if isinstance(html, unicode):
        decoded_html = _strip_bom(html)
    else:
        decoded_html = decode_html(html, default_encoding, encoding, errors)

    # lxml refuses to parse a Unicode string carrying an encoding declaration,
    # the text is already decoded at this point so the declaration is dropped
    decoded_html = XML_DECLARATION_TEXT_PATTERN.sub('', decoded_html, 1)

    return lxml.html.fromstring(decoded_html, parser=lxml.html.HTMLParser())


def decode_html(html, default_encoding=DEFAULT_ENCODING, encoding=None, errors=DEFAULT_ENC_ERRORS):
    """
    Converts a `html` containing an HTML page into Unicode.

    The encoding is determined by the first of the following sources that
    yields one, no guessing is performed:

    1. the explicit `encoding` parameter,
    2. a byte order mark,
    3. an XML encoding declaration,
    4. a <meta> charset declared at the beginning of the document,
    5. UTF-8,
    6. `default_encoding`.

    Raises `JustextError` when none of the encodings can decode the document.
    """
    if isinstance(html, unicode):
        return _strip_bom(html)

    try:
        codecs.lookup_error(errors)
    except LookupError:
        raise JustextError("Unknown encoding error handler: %s" % errors)

    # 1. explicit encoding takes precedence over everything else
    if encoding:
        try:
            decoded = _try_decode(html, encoding, errors)
        except UnicodeError as e:
            raise JustextError(
                "Unable to decode the HTML to Unicode using '%s': %s" % (encoding, unicode(e)))
        if decoded is None:
            raise JustextError("Unknown character encoding: %s" % encoding)
        return _strip_bom(decoded)

    # 2. byte order mark
    bom_encoding = _detect_bom_encoding(html)
    if bom_encoding:
        try:
            # the utf-16/utf-32 codecs consume the BOM themselves, utf-8-sig
            # does too; the result never starts with U+FEFF
            return _strip_bom(html.decode(bom_encoding, errors))
        except UnicodeError as e:
            raise JustextError(
                "Unable to decode the HTML to Unicode using '%s': %s" % (bom_encoding, unicode(e)))

    # 3. XML encoding declaration
    declared_encoding = _detect_xml_declaration_encoding(html)
    if declared_encoding:
        try:
            decoded = _try_decode(html, declared_encoding, errors)
        except UnicodeError as e:
            raise JustextError(
                "Unable to decode the HTML to Unicode using declared encoding '%s': %s"
                % (declared_encoding, unicode(e)))
        if decoded is not None:
            return _strip_bom(decoded)

    # 4. <meta> charset at the beginning of the document
    declared_encoding = _detect_meta_charset_encoding(html)
    if declared_encoding:
        try:
            decoded = _try_decode(html, declared_encoding, errors)
        except UnicodeError as e:
            raise JustextError(
                "Unable to decode the HTML to Unicode using declared encoding '%s': %s"
                % (declared_encoding, unicode(e)))
        if decoded is not None:
            return _strip_bom(decoded)

    # 5. UTF-8 - always strict, a successful replacement decode would hide the
    # fact that the document isn't UTF-8 and prevent using `default_encoding`
    try:
        return _strip_bom(html.decode("utf-8"))
    except UnicodeDecodeError:
        pass

    # 6. default encoding
    try:
        return _strip_bom(html.decode(default_encoding, errors))
    except (LookupError, UnicodeError) as e:
        raise JustextError("Unable to decode the HTML to Unicode: " + unicode(e))


def preprocessor(dom):
    "Removes unwanted parts of DOM."
    options = {
        "processing_instructions": False,
        "remove_unknown_tags": False,
        "safe_attrs_only": False,
        "page_structure": False,
        "annoying_tags": False,
        "frames": False,
        "meta": False,
        "links": False,
        "javascript": False,
        "scripts": True,
        "comments": True,
        "style": True,
        "embedded": True,
        "forms": True,
        "kill_tags": ("head",),
    }
    cleaner = Cleaner(**options)

    return cleaner.clean_html(dom)


# super(...).__init__() breaks Python 2.7 - TypeError: super() argument 1 must be type, not classobj
# noinspection PyMissingConstructor
class ParagraphMaker(ContentHandler):
    """
    A class for converting a HTML page represented as a DOM object into a list
    of paragraphs.
    """

    @classmethod
    def make_paragraphs(cls, root):
        """Converts DOM into paragraphs."""
        handler = cls()
        lxml.sax.saxify(root, handler)
        return handler.paragraphs

    def __init__(self):
        self.path = PathInfo()
        self.paragraphs = []
        self.paragraph = None
        self.link = False
        self.br = False
        self._start_new_pragraph()

    def _start_new_pragraph(self):
        if self.paragraph and self.paragraph.contains_text():
            self.paragraphs.append(self.paragraph)

        self.paragraph = Paragraph(self.path)

    def startElementNS(self, name, qname, attrs):
        name = name[1]
        self.path.append(name)

        if name in PARAGRAPH_TAGS or (name == "br" and self.br):
            if name == "br":
                # the <br><br> is a paragraph separator and should
                # not be included in the number of tags within the
                # paragraph
                self.paragraph.tags_count -= 1
            self._start_new_pragraph()
        else:
            self.br = bool(name == "br")
            if self.br:
                self.paragraph.append_text(' ')
            elif name == 'a':
                self.link = True
            self.paragraph.tags_count += 1

    def endElementNS(self, name, qname):
        name = name[1]
        self.path.pop()

        if name in PARAGRAPH_TAGS:
            self._start_new_pragraph()
        if name == 'a':
            self.link = False

    def endDocument(self):
        self._start_new_pragraph()

    def characters(self, content):
        if is_blank(content):
            return

        text = self.paragraph.append_text(content)

        if self.link:
            self.paragraph.chars_count_in_links += len(text)
        self.br = False


class PathInfo(object):
    def __init__(self):
        # list of triples (tag name, order, children)
        self._elements = []

    @property
    def dom(self):
        return ".".join(e[0] for e in self._elements)

    @property
    def xpath(self):
        return "/" + "/".join("%s[%d]" % e[:2] for e in self._elements)

    def append(self, tag_name):
        children = self._get_children()
        order = children.get(tag_name, 0) + 1
        children[tag_name] = order

        xpath_part = (tag_name, order, {})
        self._elements.append(xpath_part)

        return self

    def _get_children(self):
        if not self._elements:
            return {}

        return self._elements[-1][2]

    def pop(self):
        self._elements.pop()
        return self


@lru_cache(maxsize=128)  # 100 stoplists
def define_stoplist(stoplist):
    "Lower-case all words in stoplist and create frozen set."
    stoplist = frozenset(w.lower() for w in stoplist)
    return stoplist


def classify_paragraphs(paragraphs, stoplist, length_low=LENGTH_LOW_DEFAULT,
        length_high=LENGTH_HIGH_DEFAULT, stopwords_low=STOPWORDS_LOW_DEFAULT,
        stopwords_high=STOPWORDS_HIGH_DEFAULT, max_link_density=MAX_LINK_DENSITY_DEFAULT,
        no_headings=NO_HEADINGS_DEFAULT):
    "Context-free paragraph classification."

    stoplist = define_stoplist(stoplist)
    for paragraph in paragraphs:
        length = len(paragraph)
        stopword_density = paragraph.stopwords_density(stoplist)
        link_density = paragraph.links_density()
        paragraph.heading = bool(not no_headings and paragraph.is_heading)

        if link_density > max_link_density:
            paragraph.cf_class = 'bad'
        elif ('\xa9' in paragraph.text) or ('&copy' in paragraph.text):
            paragraph.cf_class = 'bad'
        elif 'select' in paragraph.dom_path:
            paragraph.cf_class = 'bad'
        elif length < length_low:
            if paragraph.chars_count_in_links > 0:
                paragraph.cf_class = 'bad'
            else:
                paragraph.cf_class = 'short'
        elif stopword_density >= stopwords_high:
            if length > length_high:
                paragraph.cf_class = 'good'
            else:
                paragraph.cf_class = 'neargood'
        elif stopword_density >= stopwords_low:
            paragraph.cf_class = 'neargood'
        else:
            paragraph.cf_class = 'bad'


def _get_neighbour(i, paragraphs, ignore_neargood, inc, boundary):
    while i + inc != boundary:
        i += inc
        c = paragraphs[i].class_type
        if c in GOOD_OR_BAD:
            return c
        if c == 'neargood' and not ignore_neargood:
            return c
    return 'bad'


def get_prev_neighbour(i, paragraphs, ignore_neargood):
    """
    Return the class of the paragraph at the top end of the short/neargood
    paragraphs block. If ignore_neargood is True, than only 'bad' or 'good'
    can be returned, otherwise 'neargood' can be returned, too.
    """
    return _get_neighbour(i, paragraphs, ignore_neargood, -1, -1)


def get_next_neighbour(i, paragraphs, ignore_neargood):
    """
    Return the class of the paragraph at the bottom end of the short/neargood
    paragraphs block. If ignore_neargood is True, than only 'bad' or 'good'
    can be returned, otherwise 'neargood' can be returned, too.
    """
    return _get_neighbour(i, paragraphs, ignore_neargood, 1, len(paragraphs))


def revise_paragraph_classification(paragraphs, max_heading_distance=MAX_HEADING_DISTANCE_DEFAULT):
    """
    Context-sensitive paragraph classification. Assumes that classify_pragraphs
    has already been called.
    """

    # good headings
    for i, paragraph in enumerate(paragraphs):
        # copy classes
        paragraph.class_type = paragraph.cf_class
        if not (paragraph.heading and paragraph.class_type == 'short'):
            continue
        j = i + 1
        distance = 0
        while j < len(paragraphs) and distance <= max_heading_distance:
            if paragraphs[j].class_type == 'good':
                paragraph.class_type = 'neargood'
                break
            distance += len(paragraphs[j].text)
            j += 1

    # classify short
    new_classes = {}
    for i, paragraph in enumerate(paragraphs):
        if paragraph.class_type != 'short':
            continue
        prev_neighbour = get_prev_neighbour(i, paragraphs, ignore_neargood=True)
        next_neighbour = get_next_neighbour(i, paragraphs, ignore_neargood=True)
        if prev_neighbour == 'good' and next_neighbour == 'good':
            new_classes[i] = 'good'
        elif prev_neighbour == 'bad' and next_neighbour == 'bad':
            new_classes[i] = 'bad'
        # it must be set(['good', 'bad'])
        elif (prev_neighbour == 'bad' and get_prev_neighbour(i, paragraphs, ignore_neargood=False) == 'neargood') or \
             (next_neighbour == 'bad' and get_next_neighbour(i, paragraphs, ignore_neargood=False) == 'neargood'):
            new_classes[i] = 'good'
        else:
            new_classes[i] = 'bad'

    for i, c in new_classes.items():
        paragraphs[i].class_type = c

    # revise neargood
    for i, paragraph in enumerate(paragraphs):
        if paragraph.class_type != 'neargood':
            continue
        prev_neighbour = get_prev_neighbour(i, paragraphs, ignore_neargood=True)
        next_neighbour = get_next_neighbour(i, paragraphs, ignore_neargood=True)
        if (prev_neighbour, next_neighbour) == ('bad', 'bad'):
            paragraph.class_type = 'bad'
        else:
            paragraph.class_type = 'good'

    # more good headings
    for i, paragraph in enumerate(paragraphs):
        if not (paragraph.heading and paragraph.class_type == 'bad' and paragraph.cf_class != 'bad'):
            continue
        j = i + 1
        distance = 0
        while j < len(paragraphs) and distance <= max_heading_distance:
            if paragraphs[j].class_type == 'good':
                paragraph.class_type = 'good'
                break
            distance += len(paragraphs[j].text)
            j += 1


def justext(html_text, stoplist, length_low=LENGTH_LOW_DEFAULT,
        length_high=LENGTH_HIGH_DEFAULT, stopwords_low=STOPWORDS_LOW_DEFAULT,
        stopwords_high=STOPWORDS_HIGH_DEFAULT, max_link_density=MAX_LINK_DENSITY_DEFAULT,
        max_heading_distance=MAX_HEADING_DISTANCE_DEFAULT, no_headings=NO_HEADINGS_DEFAULT,
        encoding=None, default_encoding=DEFAULT_ENCODING,
        enc_errors=DEFAULT_ENC_ERRORS, preprocessor=preprocessor):
    """
    Converts an HTML page into a list of classified paragraphs. Each paragraph
    is represented as instance of class ˙˙justext.paragraph.Paragraph˙˙.
    """
    dom = html_to_dom(html_text, default_encoding, encoding, enc_errors)
    dom = preprocessor(dom)

    paragraphs = ParagraphMaker.make_paragraphs(dom)

    classify_paragraphs(paragraphs, stoplist, length_low, length_high,
        stopwords_low, stopwords_high, max_link_density, no_headings)
    revise_paragraph_classification(paragraphs, max_heading_distance)

    return paragraphs
