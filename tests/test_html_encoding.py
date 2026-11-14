# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division, print_function, unicode_literals

import codecs
import unittest
import pytest

import justext
from justext.core import JustextError, decode_html, html_to_dom


class TestHtmlEncoding(unittest.TestCase):

    def assert_strings_equal(self, s1, s2):
        assert type(s1) == type(s2)
        assert s1 == s2

    def test_unicode(self):
        html = "ľščťžýáíéäňúô Ł€"
        decoded_html = decode_html(html)

        self.assert_strings_equal(html, decoded_html)

    def test_utf8_bytes(self):
        html = "ľščťžýáíéäňúô Ł€"
        decoded_html = decode_html(html.encode("utf8"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_1(self):
        html = '<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-2"/> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_2(self):
        html = '<meta content=text/html; charset=iso-8859-2 http-equiv="Content-Type"/> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_3(self):
        html = '<meta content=\'text/html; charset=iso-8859-2\' http-equiv="Content-Type"/> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_4(self):
        html = '<meta charset=iso-8859-2/> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_5(self):
        html = '<meta charset="iso-8859-2"/> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_6(self):
        html = '<meta charset=iso-8859-2/> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_7(self):
        html = '<meta charset=iso-8859-2> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_8(self):
        html = '<meta charset=iso-8859-2> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_9(self):
        html = '<meta content=text/html; charset=iso-8859-2 http-equiv="Content-Type"/> ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_charset_outside_1(self):
        html = '<meta charset="iso-8859-2"/> charset="iso-fake-29" ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_charset_outside_2(self):
        html = '<meta content=text/html; charset=iso-8859-2 http-equiv="Content-Type"/> charset="iso-fake-29" ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_meta_detection_charset_outside_3(self):
        html = '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; CHARSET=ISO-8859-2"> charset="iso-fake-29" ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"))

        self.assert_strings_equal(html, decoded_html)

    def test_unknown_encoding_in_strict_mode(self):
        html = 'ľščťžäňôě'
        with pytest.raises(JustextError):
            decode_html(html.encode("iso-8859-2"), errors='strict')

    def test_unknown_encoding_with_default_error_handler(self):
        html = 'ľščťžäňôě'
        decoded = decode_html(html.encode("iso-8859-2"), default_encoding="iso-8859-2")
        self.assertEqual(decoded, html)

    def test_default_encoding(self):
        html = 'ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"), default_encoding="iso-8859-2")

        self.assert_strings_equal(html, decoded_html)

    def test_given_encoding(self):
        html = 'ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"), encoding="iso-8859-2")

        self.assert_strings_equal(html, decoded_html)

    def test_given_wrong_encoding(self):
        html = 'ľščťžäňôě'
        decoded_html = decode_html(html.encode("iso-8859-2"), encoding="ASCII")

        self.assert_strings_equal("\ufffd" * len(html), decoded_html)

    def test_fake_encoding_in_meta(self):
        html = '<meta charset="iso-fake-2"/> ľščťžäňôě'

        with pytest.raises(JustextError):
            decode_html(html.encode("iso-8859-2"), errors='strict')


class TestEncodingDetectionOrder(unittest.TestCase):

    """The encoding is resolved by an explicit chain, no guessing."""

    def test_utf8_bom_is_stripped(self):
        html = '<html><body>ľščťž</body></html>'

        decoded = decode_html(codecs.BOM_UTF8 + html.encode("utf8"))

        assert decoded == html

    def test_utf16_bom_is_decoded_and_stripped(self):
        html = '<html><body>ľščťž</body></html>'

        for bom, encoding in (
                (codecs.BOM_UTF16_LE, "utf-16-le"),
                (codecs.BOM_UTF16_BE, "utf-16-be"),
                (codecs.BOM_UTF32_LE, "utf-32-le"),
                (codecs.BOM_UTF32_BE, "utf-32-be")):
            decoded = decode_html(bom + html.encode(encoding))
            assert decoded == html, encoding

    def test_explicit_encoding_wins_over_bom(self):
        html = 'ľščťž'
        data = codecs.BOM_UTF8 + html.encode("utf8")

        # the BOM says UTF-8, the explicit parameter must be obeyed anyway
        decoded = decode_html(data, encoding="cp1250")

        assert decoded == data.decode("cp1250")
        assert decoded != html

    def test_bom_wins_over_default_encoding(self):
        html = 'ľščťž'
        data = codecs.BOM_UTF16_LE + html.encode("utf-16-le")

        decoded = decode_html(data, default_encoding="ascii")

        assert decoded == html

    def test_explicit_encoding_wins_over_meta(self):
        html = '<meta charset="iso-8859-2"/> ľščťž'

        decoded = decode_html(html.encode("cp1250"), encoding="cp1250")

        assert decoded == html

    def test_bom_wins_over_xml_declaration(self):
        html = '<?xml version="1.0" encoding="windows-1250"?><p>ľščťž</p>'

        decoded = decode_html(codecs.BOM_UTF8 + html.encode("utf8"))

        assert decoded == html

    def test_xml_declaration_is_used(self):
        html = '<?xml version="1.0" encoding="windows-1250"?><p>ľščťž</p>'

        decoded = decode_html(html.encode("cp1250"))

        assert decoded == html

    def test_xml_declaration_wins_over_meta(self):
        html = ('<?xml version="1.0" encoding="windows-1250"?>'
                '<meta charset="utf-8"/><p>ľščťž</p>')

        decoded = decode_html(html.encode("cp1250"))

        assert decoded == html

    def test_meta_charset_after_body_text_is_ignored(self):
        html = ('<html><body><p>' + "ľščťž " * 600 +
                '<meta charset="windows-1250"> text in the body</p>'
                '</body></html>')

        decoded = decode_html(html.encode("utf8"))

        assert decoded == html

    def test_meta_charset_at_the_beginning_is_used(self):
        html = '<meta charset="windows-1250"/><p>ľščťž</p>'

        decoded = decode_html(html.encode("cp1250"))

        assert decoded == html

    def test_undecodable_input_raises_justext_error(self):
        with pytest.raises(JustextError):
            decode_html(b'<p>\xff\xfe broken</p>', errors='strict')

    def test_unknown_explicit_encoding_raises_justext_error(self):
        with pytest.raises(JustextError):
            decode_html(b'<p>text</p>', encoding="iso-fake-2")


class TestSameContentInDifferentEncodings(unittest.TestCase):

    HTML = (
        '<html><head><title>Test</title></head><body>'
        '<h1>Nadpis s diakritikou</h1>'
        '<p>' + ('Toto je text s ľščťžýáíéäňúô a Ł€ znakmi. ' * 10) + '</p>'
        '<p>Another paragraph of English text that is long enough to be '
        'classified as good by the algorithm because it contains several '
        'common English stop words.</p>'
        '</body></html>'
    )

    def _paragraphs(self, data, **kwargs):
        stoplist = justext.get_stoplist("English")
        return [
            (p.text, p.class_type, p.cf_class, p.heading)
            for p in justext.justext(data, stoplist, **kwargs)
        ]

    def test_paragraphs_identical_for_utf8_cp1250_utf16(self):
        expected = self._paragraphs(self.HTML.encode("utf8"))

        assert self._paragraphs(self.HTML.encode("cp1250"), encoding="cp1250") == expected
        assert self._paragraphs(codecs.BOM_UTF8 + self.HTML.encode("utf8")) == expected
        assert self._paragraphs(codecs.BOM_UTF16_LE + self.HTML.encode("utf-16-le")) == expected
        assert self._paragraphs(codecs.BOM_UTF16_BE + self.HTML.encode("utf-16-be")) == expected

    def test_html_to_dom_handles_unicode_with_xml_declaration(self):
        html = ('<?xml version="1.0" encoding="windows-1250"?>'
                '<html><body><p>ľščťž</p></body></html>')

        assert html_to_dom(html) is not None
        assert html_to_dom(html.encode("cp1250")) is not None
