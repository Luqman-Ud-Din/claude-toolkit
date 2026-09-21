#!/usr/bin/env python3
"""Template scanner for audit-accessibility-and-i18n.

Usage:
    python template_scan.py <repo_root> [--out templates.json] [--md templates.md] [--min-string-len 2]

Scans Angular (*.component.html, inline `template:` strings), React (*.tsx/*.jsx),
Vue (<template> of *.vue), plain HTML and server templates (*.cshtml, *.razor,
*.ejs, *.hbs, *.jinja, *.html with Django/Jinja/Thymeleaf tags), and CSS
(*.css/*.scss/*.less) for:

  input-no-label            input/select/textarea with no label association      WCAG 1.3.1 / 3.3.2 / 4.1.2
  placeholder-only-label    ...where a placeholder is the only "label"            WCAG 3.3.2
  img-no-alt                img without alt (alt="" counts as decorative = ok)    WCAG 1.1.1
  dialog-no-focus-trap      role=dialog / <dialog> / .modal with no focus-trap marker in the file   WCAG 2.1.2 / 2.4.3
  dialog-no-name            dialog without aria-label / aria-labelledby           WCAG 4.1.2
  click-on-non-interactive  click handler on div/span/li/... with no role/tabindex/key handler       WCAG 2.1.1
  icon-button-no-name       <button> containing only an icon and no aria-label    WCAG 4.1.2
  positive-tabindex         tabindex > 0                                          WCAG 2.4.3
  html-no-lang              <html> without lang                                   WCAG 3.1.1
  iframe-no-title           <iframe> without title                                WCAG 4.1.2
  a-no-href                 <a> with a click handler and no href/routerLink       WCAG 2.1.1 / 4.1.2
  outline-none              CSS outline:none/0 in a file with no :focus-visible   WCAG 2.4.7
  physical-css-property     margin-left/right, text-align:left..., float          i18n / RTL
  hard-coded-string         user-facing text or attribute not routed through the i18n mechanism (count per file)

Recognized i18n markers: Angular `i18n`/`i18n-*` attrs, `| translate`, `| transloco`, `translate` attr,
React `t(`, `<Trans`, `<FormattedMessage`, Vue `$t(`/`t(`/`v-t`, Django `{% trans %}`/`{% blocktrans %}`,
Thymeleaf `th:text="#{...}"`, Razor `@Localizer[...]`, EJS/HBS `t(`/`__(`.
Component-library labels (mat-label, ion-label, label= attrs, asp-for + label asp-for) are honoured.
Every row is a candidate for the manual pass. Read-only.
"""
import argparse
import json
import os
import re
import sys

import importlib.util

def _audit_core_skills_dir():
    """Resolve the explicit core installation, or the original sibling layout."""
    env = os.environ.get("AUDIT_CORE_ROOT")
    if env:
        skills = os.path.join(env, "skills")
        if os.path.isdir(os.path.join(skills, "audit-code-scan")):
            return skills
        sys.exit("AUDIT_CORE_ROOT does not contain audit-core skills: " + env)
    sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(sibling, "audit-code-scan")):
        return sibling
    sys.exit("audit-core is unavailable. Enable audit-core and restart Claude Code, "
             "or set AUDIT_CORE_ROOT to its plugin directory when running manually.")

_SKILLS = _audit_core_skills_dir()


def _load_atomic(skill, module, alias):
    """Load an atomic skill's script by path under a unique module name."""
    path = os.path.join(_SKILLS, skill, "scripts", module + ".py")
    if not os.path.exists(path):
        sys.exit(f"{skill} must be reachable from this skill (audit-core plugin or sibling layout; expected {path})")
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


repo_walk = _load_atomic("audit-code-scan", "repo_walk", "audit_code_scan_repo_walk")

MARKUP_EXT = (".html", ".htm", ".cshtml", ".razor", ".ejs", ".hbs", ".handlebars", ".jinja", ".jinja2", ".twig", ".vue", ".tsx", ".jsx")
CODE_EXT = (".ts",)
CSS_EXT = (".css", ".scss", ".less", ".sass")

TAG_RE = re.compile(r"<([A-Za-z][\w.:-]*)\b([^<>]*?)/?>", re.S)
FOCUS_TRAP_MARKERS = re.compile(r"cdkTrapFocus|cdkFocusInitial|focus-trap|FocusTrap|FocusLock|trapFocus|useFocusTrap|v-focus-trap|\binert\b|aria-modal=\"true\"|\.showModal\(|initialFocus|returnFocus|autoFocus|autofocus|focusTrap", re.I)
NATIVE_DIALOG_LIBS = re.compile(r"@headlessui/|@radix-ui/|radix-vue|@mui/material|@chakra-ui|react-aria|@angular/material/dialog|MatDialog|ion-modal|v-dialog|el-dialog|q-dialog|p-dialog|<Dialog\b|<Modal\b|ModalController|ionModal", re.I)
INTERACTIVE_TAGS = {"div", "span", "li", "td", "tr", "p", "section", "article", "img", "svg", "label", "i", "h1", "h2", "h3", "h4"}
ICON_ONLY = re.compile(r"^\s*(<(i|svg|mat-icon|ion-icon|fa-icon|Icon|[A-Z]\w*Icon|img|span class=\"(icon|fa|material)[^\"]*\")\b[^>]*>(.*?</\w[\w-]*>)?\s*)+$", re.S)
I18N_ATTR = re.compile(r"(^|\s)(i18n|translate|v-t|data-i18n)(=|\s|$)")
TRANSLATED_TEXT = re.compile(r"\|\s*(translate|transloco|i18n)\b|\$t\(|\bt\(|\b__\(|<Trans\b|<FormattedMessage\b|\{%\s*(trans|blocktrans)|#\{|@Localizer|@SharedLocalizer|Localizer\[|\bgettext\(|\{\{\s*t\s")
KEY_LIKE = re.compile(r"^[A-Z0-9_.\-]+$")
WORD = re.compile(r"[^\W\d_]{2,}")
ATTR_TEXT_NAMES = ("placeholder", "title", "alt", "aria-label", "aria-placeholder", "label", "aria-description", "helper-text", "hint")


def read(p):
    return repo_walk.read_text(p)


def attr(attrs, name):
    """Return the literal value of attribute `name` or None. Handles quotes and JSX braces."""
    m = re.search(r"(?:^|\s)" + re.escape(name) + r"\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{([^}]*)\}|([^\s>]+))", attrs)
    if not m:
        return None
    return next((g for g in m.groups() if g is not None), "")


def has_attr(attrs, *names):
    return any(re.search(r"(?:^|\s)" + re.escape(n) + r"(\s*=|\s|$)", attrs) for n in names)


def bound(attrs, name):
    """True if the attribute is bound/dynamic in any framework syntax."""
    return has_attr(attrs, "[" + name + "]", "[attr." + name + "]", ":" + name, "v-bind:" + name, "th:" + name,
                    "asp-" + name, "x-bind:" + name) or re.search(r"(?:^|\s)" + re.escape(name) + r"\s*=\s*\{", attrs) is not None \
        or re.search(r"(?:^|\s)" + re.escape(name) + r"\s*=\s*\"[^\"]*(\{\{|\{%|<%|@\(|@\w+)", attrs) is not None


def extract_markup(path, text):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".vue":
        m = re.search(r"<template\b[^>]*>(.*)</template>", text, re.S)
        return [(m.group(1), text[:m.start(1)].count("\n")) ] if m else []
    if ext in CODE_EXT:
        return [(m.group(1), text[:m.start(1)].count("\n")) for m in re.finditer(r"template\s*:\s*`((?:[^`\\]|\\.)*)`", text, re.S)]
    if ext in (".tsx", ".jsx"):
        return [(text, 0)]
    return [(text, 0)]


def strip_non_content(markup, jsx):
    t = re.sub(r"<!--.*?-->", lambda m: " " * len(m.group(0)), markup, flags=re.S)
    t = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", lambda m: " " * len(m.group(0)), t, flags=re.S | re.I)
    t = re.sub(r"\{#.*?#\}", lambda m: " " * len(m.group(0)), t, flags=re.S)
    t = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|<%.*?%>|@\{.*?\}", lambda m: " " * len(m.group(0)), t, flags=re.S)
    if jsx:
        # blank brace expressions that contain no JSX tags ({t('x')}, {avatar}, props objects)
        for _ in range(6):
            t2 = re.sub(r"\{[^{}<>]*\}", lambda m: " " * len(m.group(0)), t)
            if t2 == t:
                break
            t = t2
        # conditional/list wrappers around JSX: `{open && (` ... `)}` and `{items.map(i => (` ... `))}`
        t = re.sub(r"\{[^<>{}]*\(\s*(?=<)", lambda m: " " * len(m.group(0)), t)
        t = re.sub(r"(?<=>)\s*\)+\s*\}", lambda m: " " * len(m.group(0)), t)
        # JS outside JSX: blank code lines that contain no tag
        t = re.sub(r"^(?!\s*<)[^<\n]*$", lambda m: " " * len(m.group(0)), t, flags=re.M)
    t = re.sub(r"^\s*@(if|else|for|switch|case|default|empty|defer|placeholder|loading|error)\b.*$", lambda m: " " * len(m.group(0)), t, flags=re.M)
    t = re.sub(r"^\s*\}\s*$", lambda m: " " * len(m.group(0)), t, flags=re.M)
    return t


def scan_markup(rel, markup, base_line, whole_file, jsx, min_len):
    issues, strings = [], []
    labels_for = set(re.findall(r"<label\b[^>]*?\b(?:for|htmlFor|th:for)\s*=\s*[\"']([^\"'{}]+)[\"']", markup))
    dynamic_label = bool(re.search(r"<label\b[^>]*?\b(?:for|htmlFor)\s*=\s*(\{|\"\{\{|\"<%|\"\{%)", markup)) or "asp-for" in markup
    stripped = strip_non_content(markup, jsx)

    def line_at(pos):
        return base_line + markup[:pos].count("\n") + 1

    for m in TAG_RE.finditer(markup):
        tag, attrs, pos = m.group(1), m.group(2) or "", m.start()
        low = tag.lower()
        # ---- inputs
        if low in ("input", "select", "textarea", "ion-input", "ion-select", "ion-textarea", "mat-select", "v-text-field", "v-select", "el-input", "q-input"):
            itype = (attr(attrs, "type") or "text").lower()
            if itype in ("hidden", "submit", "button", "reset", "image"):
                continue
            labelled = has_attr(attrs, "aria-label", "aria-labelledby", "[attr.aria-label]", "[attr.aria-labelledby]", "[aria-label]", ":aria-label", "v-bind:aria-label", "th:aria-label", "label", ":label", "[label]", "title") \
                or (attr(attrs, "id") in labels_for) or dynamic_label \
                or re.search(r"(?:^|\s)aria-label(ledby)?\s*=\s*\{", attrs) is not None
            if not labelled:
                before = markup[:pos]
                if before.count("<label") > before.count("</label>"):
                    labelled = True
                for wrapper, lab in (("mat-form-field", "<mat-label"), ("ion-item", "<ion-label"), ("el-form-item", "label="), ("v-input", "label=")):
                    o = before.rfind("<" + wrapper)
                    if o >= 0 and before.rfind("</" + wrapper) < o and (lab in markup[o:pos + 400]):
                        labelled = True
            if not labelled:
                kind = "placeholder-only-label" if has_attr(attrs, "placeholder", "[placeholder]", ":placeholder") else "input-no-label"
                issues.append(dict(kind=kind, wcag=["1.3.1", "3.3.2", "4.1.2"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        # ---- images
        if low in ("img", "ion-img", "image") or (jsx and tag == "Image"):
            if not (has_attr(attrs, "alt", "[alt]", ":alt", "th:alt", "[attr.alt]") or bound(attrs, "alt") or attr(attrs, "role") in ("presentation", "none") or has_attr(attrs, "aria-hidden")):
                issues.append(dict(kind="img-no-alt", wcag=["1.1.1"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        # ---- dialogs
        role = (attr(attrs, "role") or "").lower()
        cls = (attr(attrs, "class") or attr(attrs, "className") or "").lower()
        if role in ("dialog", "alertdialog") or low == "dialog" or (low == "div" and re.search(r"\bmodal\b", cls) and not re.search(r"backdrop|overlay|footer|header|body|content", cls)):
            if not FOCUS_TRAP_MARKERS.search(whole_file) and not NATIVE_DIALOG_LIBS.search(whole_file):
                issues.append(dict(kind="dialog-no-focus-trap", wcag=["2.1.2", "2.4.3"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
            if not (has_attr(attrs, "aria-label", "aria-labelledby", "[attr.aria-label]", "[attr.aria-labelledby]", ":aria-labelledby", ":aria-label") or re.search(r"aria-label(ledby)?\s*=\s*\{", attrs)):
                issues.append(dict(kind="dialog-no-name", wcag=["4.1.2"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        # ---- click on non-interactive
        if low in INTERACTIVE_TAGS and re.search(r"(?:^|\s)(\(click\)|@click(\.\w+)?|v-on:click|onClick|x-on:click|th:onclick|onclick)\s*=", attrs):
            if not (has_attr(attrs, "role", "tabindex", "tabIndex", "[attr.tabindex]", ":tabindex") or re.search(r"\(keydown|\(keyup|@keydown|@keyup|onKeyDown|onKeyUp|onKeyPress|\(keypress", attrs)):
                issues.append(dict(kind="click-on-non-interactive", wcag=["2.1.1", "4.1.2"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        # ---- icon buttons
        if low in ("button", "ion-button"):
            end = markup.find("</" + tag + ">", m.end())
            inner = markup[m.end():end] if end > 0 else ""
            no_icons = re.sub(r"<(i|svg|mat-icon|ion-icon|fa-icon|Icon|[A-Z]\w*Icon)\b[^>]*>.*?</\1>", "", inner, flags=re.S)
            text_inner = re.sub(r"<[^>]+>", "", no_icons).strip()
            if inner and not text_inner and re.search(r"<(i|svg|mat-icon|ion-icon|fa-icon|Icon|[A-Z]\w*Icon|img|span)\b", inner) \
                    and not (has_attr(attrs, "aria-label", "aria-labelledby", "[attr.aria-label]", ":aria-label", "title", "[title]") or re.search(r"aria-label\s*=\s*\{", attrs)):
                issues.append(dict(kind="icon-button-no-name", wcag=["4.1.2", "2.4.4"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        # ---- tabindex, html lang, iframe, anchors
        ti = attr(attrs, "tabindex") or attr(attrs, "tabIndex")
        if ti and re.fullmatch(r"\s*[1-9]\d*\s*", ti):
            issues.append(dict(kind="positive-tabindex", wcag=["2.4.3"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        if low == "html" and not (has_attr(attrs, "lang", "[lang]", ":lang", "th:lang", "[attr.lang]") or bound(attrs, "lang")):
            issues.append(dict(kind="html-no-lang", wcag=["3.1.1"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        if low == "iframe" and not (has_attr(attrs, "title", "[title]", ":title") or bound(attrs, "title")):
            issues.append(dict(kind="iframe-no-title", wcag=["4.1.2"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        if low == "a" and re.search(r"(?:^|\s)(\(click\)|@click|onClick|v-on:click)\s*=", attrs) and not has_attr(attrs, "href", "[href]", ":href", "routerLink", "[routerLink]", "to", ":to", "th:href", "asp-page", "asp-action", "role"):
            issues.append(dict(kind="a-no-href", wcag=["2.1.1", "4.1.2"], file=rel, line=line_at(pos), snippet=m.group(0)[:160]))
        # ---- hard-coded attribute strings
        for name in ATTR_TEXT_NAMES:
            v = attr(attrs, name)
            if v is None or bound(attrs, name) or has_attr(attrs, "i18n-" + name) or name == "alt" and v == "":
                continue
            if v and WORD.search(v) and not re.search(r"\{\{|\{%|<%|#\{|@|\$t\(|\bt\(|__\(", v) and not KEY_LIKE.match(v.strip()) and len(WORD.findall(v)[0]) >= min_len:
                strings.append(dict(file=rel, line=line_at(pos), kind="attribute", attr=name, text=v.strip()[:80]))
    # ---- hard-coded text nodes
    for m in re.finditer(r">([^<>]+)<", stripped):
        raw = m.group(1)
        txt = re.sub(r"\s+", " ", raw).strip(" \t\r\n :.,;!?()[]-|/*'\"")
        if not txt or not WORD.search(txt) or KEY_LIKE.match(txt):
            continue
        if TRANSLATED_TEXT.search(raw):
            continue
        # enclosing tag attrs
        open_tag = None
        for t in TAG_RE.finditer(markup, 0, m.start(1)):
            open_tag = t
        if open_tag and (I18N_ATTR.search(open_tag.group(2) or "") or re.search(r"th:(text|utext)\s*=", open_tag.group(2) or "")):
            continue
        if open_tag and open_tag.group(1).lower() in ("code", "pre", "script", "style", "kbd", "samp", "var", "mat-icon", "ion-icon", "i", "fa-icon"):
            continue
        if len(WORD.findall(txt)[0]) < min_len:
            continue
        strings.append(dict(file=rel, line=line_at(m.start(1)), kind="text", text=txt[:80]))
    return issues, strings


def scan_css(rel, text):
    issues = []
    has_fv = ":focus-visible" in text or ":focus" in text and "outline" in text.split(":focus", 1)[1][:300]
    for m in re.finditer(r"outline\s*:\s*(none|0)\b", text):
        if not has_fv:
            issues.append(dict(kind="outline-none", wcag=["2.4.7"], file=rel, line=text[:m.start()].count("\n") + 1, snippet=m.group(0)))
    for m in re.finditer(r"^\s*((margin|padding|border)-(left|right)|text-align\s*:\s*(left|right)|float\s*:\s*(left|right)|(left|right)\s*:\s*-?\d)", text, re.M):
        issues.append(dict(kind="physical-css-property", wcag=[], file=rel, line=text[:m.start()].count("\n") + 1, snippet=text.splitlines()[text[:m.start()].count("\n")].strip()[:100], tag="i18n-rtl"))
    return issues


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--out"); ap.add_argument("--md")
    ap.add_argument("--min-string-len", type=int, default=2)
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    all_issues, all_strings = [], []
    for p in repo_walk.iter_files(root, exts=set(MARKUP_EXT + CODE_EXT + CSS_EXT), names=frozenset()):
        fn = os.path.basename(p)
        rel = repo_walk.rel(root, p)
        ext = os.path.splitext(fn)[1].lower()
        if re.search(r"\.(spec|test|stories)\.", fn) or fn.endswith(".d.ts"):
            continue
        if ext in CSS_EXT:
            all_issues += scan_css(rel, read(p))
        elif ext in MARKUP_EXT or ext in CODE_EXT:
            text = read(p)
            if ext in CODE_EXT and "template:" not in text:
                continue
            jsx = ext in (".tsx", ".jsx")
            for markup, base in extract_markup(p, text):
                iss, strs = scan_markup(rel, markup, base, text, jsx, a.min_string_len)
                all_issues += iss; all_strings += strs
    by_file = {}
    for s in all_strings:
        e = by_file.setdefault(s["file"], {"count": 0, "samples": []})
        e["count"] += 1
        if len(e["samples"]) < 5:
            e["samples"].append(s["text"])
    kinds = {}
    for i in all_issues:
        kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
    result = {"root": root, "issue_counts": kinds, "issues": all_issues,
              "hard_coded_strings": {"total": len(all_strings), "files": len(by_file),
                                     "by_file": dict(sorted(by_file.items(), key=lambda kv: -kv[1]["count"])), "items": all_strings}}
    md = ["| Kind | WCAG | Location | Snippet |", "|---|---|---|---|"]
    for i in all_issues:
        md.append(f"| {i['kind']} | {', '.join(i['wcag']) or i.get('tag','')} | `{i['file']}:{i['line']}` | `{i['snippet'].replace('|', '\\|')[:90]}` |")
    md += ["", "### Hard-coded strings by file", "| File | Strings | Sample |", "|---|---|---|"]
    for f, e in result["hard_coded_strings"]["by_file"].items():
        md.append(f"| {f} | {e['count']} | {', '.join(repr(s) for s in e['samples'][:3])} |")
    md.append(f"\n**Total:** {len(all_strings)} strings in {len(by_file)} files")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(md) + "\n")
    print(json.dumps({"issue_counts": kinds, "hard_coded_strings": {"total": len(all_strings), "files": len(by_file)}}, indent=2))
    print("\n".join(md))
    if a.out:
        print(f"written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
