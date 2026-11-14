# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division, print_function, unicode_literals

import codecs
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HTML = (
    '<html><head><title>Test</title></head><body>'
    '<h1>Nadpis s diakritikou</h1>'
    '<p>' + ('Toto je text s ľščťžýáíéäňúô a Ł€ znakmi. ' * 10) + '</p>'
    '<p>Another paragraph of English text that is long enough to be '
    'classified as good by the algorithm because it contains several '
    'common English stop words.</p>'
    '</body></html>'
)


def run_cli(*args, **kwargs):
    return subprocess.Popen(
        [sys.executable, '-m', 'justext'] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
        **kwargs
    ).communicate()


def test_file_input_in_utf8_cp1250_utf16_gives_same_output(tmp_path):
    utf8 = tmp_path / "page-utf8.html"
    utf8.write_bytes(HTML.encode("utf8"))
    cp1250 = tmp_path / "page-cp1250.html"
    cp1250.write_bytes(HTML.encode("cp1250"))
    utf16 = tmp_path / "page-utf16.html"
    utf16.write_bytes(codecs.BOM_UTF16_LE + HTML.encode("utf-16-le"))

    outputs = []
    for path, extra in ((utf8, ()), (cp1250, ("--encoding=cp1250",)), (utf16, ())):
        out, err = run_cli("-s", "English", "--format=detailed", *(extra + (str(path),)))
        assert err == b""
        outputs.append(out)

    assert outputs[0] == outputs[1] == outputs[2]
    assert "Nadpis s diakritikou".encode("utf8") in outputs[0]


def test_undecodable_input_exits_with_1_and_no_traceback(tmp_path):
    page = tmp_path / "broken.html"
    page.write_bytes(b'<html><body><p>\xff\xfe broken</p></body></html>')

    out, err = run_cli("-s", "English", "--enc-errors=strict", str(page))

    assert out == b""
    assert b"Traceback" not in err
    assert b"Unable to decode" in err


def test_unknown_encoding_exits_with_1_and_no_traceback(tmp_path):
    page = tmp_path / "page.html"
    page.write_bytes(HTML.encode("utf8"))

    out, err = run_cli("-s", "English", "--encoding=iso-fake-2", str(page))

    assert out == b""
    assert b"Traceback" not in err
