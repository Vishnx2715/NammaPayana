"""
Phase 2 XSS Elimination Tests
Verifies that escapeHtml() is defined and wired into all innerHTML sinks
that render API-sourced strings.
"""
import os
import re

BASE = os.path.join(os.path.dirname(__file__), '..')


def _read(relative_path):
    with open(os.path.join(BASE, relative_path), encoding='utf-8') as f:
        return f.read()


def test_escape_html_defined_in_app_js():
    """escapeHtml() function must be present in app.js."""
    content = _read('static/js/app.js')
    assert 'function escapeHtml' in content, \
        "escapeHtml() function definition not found in app.js"


def test_no_raw_name_en_in_innerhtml_app_js():
    """
    .name_en should not appear bare (unescaped) inside template literals
    that are assigned to innerHTML. Allowed patterns:
      escapeHtml(... .name_en ...)
      escapeHtml(d.name_en)
      .map(a => escapeHtml(a.name_en))
    Forbidden: ${d.name_en} or ${ ... name_en} without escapeHtml wrapping.
    """
    content = _read('static/js/app.js')
    # Find template literal expressions containing .name_en but NOT wrapped in escapeHtml(
    # Pattern: ${ ... .name_en ... } where the expression does not contain 'escapeHtml'
    pattern = re.compile(r'\$\{[^}]*\.name_en[^}]*\}')
    bare_matches = []
    for m in pattern.finditer(content):
        expr = m.group(0)
        if 'escapeHtml' not in expr:
            bare_matches.append(expr)
    assert bare_matches == [], \
        f"Found unescaped .name_en in innerHTML template literals: {bare_matches}"


def test_no_raw_description_in_innerhtml_app_js():
    """
    .description should not appear bare inside template literals
    assigned to innerHTML without escapeHtml() wrapping.
    """
    content = _read('static/js/app.js')
    pattern = re.compile(r'\$\{[^}]*\.description[^}]*\}')
    bare_matches = []
    for m in pattern.finditer(content):
        expr = m.group(0)
        if 'escapeHtml' not in expr:
            bare_matches.append(expr)
    assert bare_matches == [], \
        f"Found unescaped .description in innerHTML template literals: {bare_matches}"


def test_escape_html_used_in_auth_js_or_textcontent_used():
    """
    auth.js must either define/reference escapeHtml() OR use textContent
    for user-supplied display data (safe DOM insertion).
    """
    content = _read('static/js/auth.js')
    has_escape_html = 'escapeHtml' in content
    has_textcontent = 'textContent' in content
    assert has_escape_html or has_textcontent, \
        "auth.js must use escapeHtml() or textContent for safe output"


def test_no_avatar_url_in_innerhtml_auth_js():
    """
    avatar_url must NOT be inserted via innerHTML in auth.js.
    It should be set via img.src after https:// validation.
    """
    content = _read('static/js/auth.js')
    # Look for innerHTML template literal expressions containing 'avatar_url'
    # Match innerHTML = `...` or innerHTML += `...` on a single logical line
    # Only flag if avatar_url appears in the same template literal
    pattern = re.compile(r'innerHTML\s*[+]?=\s*`[^`]*avatar_url[^`]*`')
    matches = pattern.findall(content)
    assert matches == [], \
        f"avatar_url found inside innerHTML template literal assignment in auth.js: {matches}"


def test_map_js_uses_escape_or_textcontent():
    """
    map.js must call escapeHtml() for API-sourced strings inserted into
    Leaflet popup / tooltip HTML.
    """
    content = _read('static/js/map.js')
    assert 'escapeHtml(' in content, \
        "map.js must call escapeHtml() for API-sourced popup/tooltip content"
