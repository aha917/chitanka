#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
odt2sfb.py — Конвертор от OpenDocument Text (.odt) към формата SFB на Читанка.

Форматът SFB (Simple Format for Books), използван от chitanka.info, описва
СТРУКТУРАТА на текста, а не визуалното му оформление.  Основни правила, които
този скрипт спазва (вж. https://chitanka.info/docs/sfb и
https://wiki.chitanka.info/Форматиране/Нови_текстове):

  * „Един параграф от произведението = един ред във SFB-файла.“
  * Всеки текстов ред започва с ТАБУЛАТОР.
  * Блокови маркери (X> … X$) стоят самички на ред, без табулатор и без текст:
        I>/I$  информация (издание)      C>/C$  цитат
        E>/E$  епиграф (мото)            P>/P$  стихотворение
        D>/D$  посвещение                A>/A$  анотация
        S>/S$  знак/табелка              F>/F$  форматиран текст
  * Едноредови маркери — преди табулатора:
        |   заглавие (автор/заглавие на книгата, заглавие на стих.)
        >   секция (>, >>, >>> … според нивото)
        #   подзаглавие
        @   автор на епиграф/цитат/стихотворение
  * Параграфни (вградени) маркери:
        _текст_       акцент (обикновено курсив)      = {e}…{/e}
        __текст__     силен акцент (обикновено получер) = {s}…{/s}
        {sub}…{/sub}  долен индекс   {sup}…{/sup}  горен индекс
  * Бележки под линия: препратка „*“ (или „*1“, „*2“ при няколко в един
    параграф); текстът на бележката е в самостоятелен параграф веднага след
    съответния, ограден в квадратни скоби: [*1 Текст на бележката.]
  * Картинки: {img:име_на_файл}
  * Сюжетен разделител: звездички (по подразбиране „* * *“) с по един празен
    ред преди и след него.

Скриптът НЕ изисква външни библиотеки — чете .odt (ZIP) само със стандартния
Python (zipfile + xml.etree.ElementTree).

Употреба:
    python3 odt2sfb.py input.odt -o output.sfb
    python3 odt2sfb.py input.odt --author "Рей Бредбъри" --title "Вино от глухарчета"

Виж `python3 odt2sfb.py -h` за всички опции.
"""

import argparse
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

# --- ODF именни пространства -------------------------------------------------
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style":  "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text":   "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table":  "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw":   "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "fo":     "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "xlink":  "http://www.w3.org/1999/xlink",
    "svg":    "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
}


def ln(tag):
    """Локалното име на елемент, без именното пространство."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def qn(prefix, name):
    return "{%s}%s" % (NS[prefix], name)


# --- Вградени (параграфни) модификатори -------------------------------------
MOD_ORDER = ["emphasis", "strong", "sub", "sup"]
MOD_CODE = {"emphasis": "e", "strong": "s", "sub": "sub", "sup": "sup"}


def wrap_mods(text, mods, markup):
    """Огражда `text` с маркери за множеството модификатори `mods`."""
    if not mods or not text:
        return text
    # изнасяме водещите/крайните интервали извън маркерите
    stripped = text.strip()
    if not stripped:
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = stripped

    if markup != "braces":
        if mods == {"emphasis"}:
            return lead + "_" + core + "_" + trail
        if mods == {"strong"}:
            return lead + "__" + core + "__" + trail

    opener = "".join("{%s}" % MOD_CODE[m] for m in MOD_ORDER if m in mods)
    closer = "".join("{/%s}" % MOD_CODE[m] for m in reversed(MOD_ORDER) if m in mods)
    return lead + opener + core + closer + trail


# --- Разбор на стиловете -----------------------------------------------------
class Styles:
    """Събира дефинициите на стиловете от styles.xml и content.xml."""

    def __init__(self):
        self.styles = {}  # name -> dict(parent, family, display, tprops, pprops)
        self._tprops_cache = {}
        self._names_cache = {}

    def add_root(self, root):
        if root is None:
            return
        for container in root.iter():
            if ln(container.tag) not in ("styles", "automatic-styles", "master-styles"):
                continue
            for st in container:
                if ln(st.tag) != "style":
                    continue
                name = st.get(qn("style", "name"))
                if not name:
                    continue
                entry = {
                    "parent": st.get(qn("style", "parent-style-name")),
                    "family": st.get(qn("style", "family")),
                    "display": st.get(qn("style", "display-name")) or name,
                    "tprops": {},
                    "pprops": {},
                }
                for props in st:
                    if ln(props.tag) == "text-properties":
                        entry["tprops"] = self._read_tprops(props)
                    elif ln(props.tag) == "paragraph-properties":
                        entry["pprops"] = dict(props.attrib)
                self.styles[name] = entry

    @staticmethod
    def _read_tprops(props):
        out = {}
        fs = props.get(qn("fo", "font-style"))
        if fs is not None:
            out["italic"] = fs in ("italic", "oblique")
        fw = props.get(qn("fo", "font-weight"))
        if fw is not None:
            out["bold"] = fw == "bold" or (fw.isdigit() and int(fw) >= 600)
        tp = props.get(qn("style", "text-position"))
        if tp is not None:
            first = tp.split()[0] if tp.split() else ""
            if first == "sub":
                out["position"] = "sub"
            elif first in ("super",):
                out["position"] = "sup"
            elif first.endswith("%"):
                try:
                    val = float(first[:-1])
                    out["position"] = "sup" if val > 0 else ("sub" if val < 0 else None)
                except ValueError:
                    out["position"] = None
            else:
                out["position"] = None
        return out

    def _chain(self, name):
        chain, seen = [], set()
        while name and name in self.styles and name not in seen:
            seen.add(name)
            chain.append(name)
            name = self.styles[name]["parent"]
        return chain  # leaf -> root

    def text_props(self, name):
        """Изчислено множество текстови свойства (наследяване разрешено)."""
        if name in self._tprops_cache:
            return self._tprops_cache[name]
        merged = {}
        for n in reversed(self._chain(name)):  # root -> leaf, детето замества
            merged.update(self.styles[n]["tprops"])
        self._tprops_cache[name] = merged
        return merged

    def names(self, name):
        """Имена (техническо + за показване) по цялата верига — за евристики."""
        if name in self._names_cache:
            return self._names_cache[name]
        acc = []
        for n in self._chain(name):
            acc.append(n)
            disp = self.styles[n]["display"]
            if disp and disp != n:
                acc.append(disp)
        self._names_cache[name] = acc
        return acc


def props_to_mods(base, props):
    """Прилага множество текстови свойства върху текущите модификатори."""
    mods = set(base)
    if "italic" in props:
        mods.add("emphasis") if props["italic"] else mods.discard("emphasis")
    if "bold" in props:
        mods.add("strong") if props["bold"] else mods.discard("strong")
    if "position" in props:
        mods.discard("sub")
        mods.discard("sup")
        if props["position"] == "sub":
            mods.add("sub")
        elif props["position"] == "sup":
            mods.add("sup")
    return mods


# --- Класификация на параграфите по роля ------------------------------------
def classify_role(names):
    s = " ".join(names).lower()
    if any(k in s for k in ("epigraph", "епиграф", "motto", "мото")):
        return "E"
    if any(k in s for k in ("dedicat", "посвещ")):
        return "D"
    if any(k in s for k in ("annotat", "анотац")):
        return "A"
    if any(k in s for k in ("verse", "poem", "poetry", "стих", "поези")):
        return "P"
    if any(k in s for k in ("quot", "цитат", "blockquote", "block quote")):
        return "C"
    if any(k in s for k in ("preformat", "sourcecode", "source code",
                            "source-code", "monospace", "code block")):
        return "F"
    return None


def is_attribution(names):
    s = " ".join(names).lower()
    return any(k in s for k in ("attrib", "signature", "подпис",
                                "автор на цитат", "citation-author"))


def is_subheading(names):
    s = " ".join(names).lower()
    return any(k in s for k in ("subhead", "sub-head", "подзаглав"))


def title_kind(names):
    s = " ".join(names).lower()
    if "subtitle" in s or "sub-title" in s or "подзаглавие на книга" in s:
        return "subtitle"
    if "author" in s or "автор" in s:
        return "author"
    if "title" in s or "заглавие" in s:
        return "title"
    return None


# --- Разпознаване на сюжетен разделител --------------------------------------
DIVIDER_CHARS = set("*⁕⁂∗•·.＊✱﹡ 	")


def looks_like_divider(text):
    t = text.strip()
    if not t:
        return False
    compact = re.sub(r"\s+", "", t)
    if len(compact) < 3:
        return False
    if set(compact) <= set("*⁕⁂∗＊✱﹡") and compact.count("*") + \
            sum(compact.count(c) for c in "⁕⁂∗＊✱﹡") >= 3:
        return True
    return False


# --- Ядро на конвертора ------------------------------------------------------
class Converter:
    def __init__(self, styles, args):
        self.styles = styles
        self.args = args
        self.out = []            # изходни редове
        self.open_block = None   # текущо отворен блоков маркер (роля)

    # ---- помощни за изхода --------------------------------------------------
    def line(self, text=""):
        self.out.append(text)

    def blank(self):
        if self.out and self.out[-1] != "":
            self.out.append("")

    def close_block(self):
        if self.open_block:
            self.line("%s$" % self.open_block)
            self.open_block = None
            self.blank()

    def ensure_block(self, role):
        if self.open_block == role:
            return
        self.close_block()
        self.blank()
        self.line("%s>" % role)
        self.open_block = role

    # ---- разбор на инлайн съдържание ---------------------------------------
    def flatten(self, para, base_mods):
        """Връща (sublines, notes).

        sublines: списък от редове; всеки ред е списък от токени
                  ('text', str, mods) | ('img', fname) | ('noteref', ref)
        notes:    списък от (ref, text) за бележките под линия
        """
        sublines = [[]]
        notes = []
        note_counter = [0]

        def add_text(txt, mods):
            if not txt:
                return
            cur = sublines[-1]
            if cur and cur[-1][0] == "text" and cur[-1][2] == mods:
                cur[-1] = ("text", cur[-1][1] + txt, mods)
            else:
                cur.append(("text", txt, mods))

        def walk(node, mods):
            if node.text:
                add_text(node.text, mods)
            for child in node:
                tag = ln(child.tag)
                if tag == "span":
                    sname = child.get(qn("text", "style-name"))
                    cmods = props_to_mods(mods, self.styles.text_props(sname)) if sname else mods
                    walk(child, cmods)
                elif tag == "line-break":
                    sublines.append([])
                elif tag == "tab":
                    add_text(" ", mods)
                elif tag == "s":
                    try:
                        cnt = int(child.get(qn("text", "c"), "1"))
                    except ValueError:
                        cnt = 1
                    add_text(" " * cnt, mods)
                elif tag == "note":
                    self._handle_note(child, notes, note_counter, sublines[-1])
                elif tag in ("a", "bookmark-ref", "reference-ref", "span-ref"):
                    walk(child, mods)  # запазваме видимия текст на връзката
                elif tag == "frame":
                    fname = self._frame_image(child)
                    if fname:
                        sublines[-1].append(("img", fname))
                    # текст в рамка (текстови кутии) — обхождаме за всеки случай
                    for tb in child.iter(qn("text", "p")):
                        pass
                elif tag == "image":
                    fname = self._image_name(child)
                    if fname:
                        sublines[-1].append(("img", fname))
                else:
                    walk(child, mods)
                if child.tail:
                    add_text(child.tail, mods)

        walk(para, base_mods)
        return sublines, notes

    def _handle_note(self, note, notes, counter, cur_subline):
        counter[0] += 1
        # текстът на бележката
        body_el = note.find(qn("text", "note-body"))
        body_txt = ""
        if body_el is not None:
            parts = []
            for p in body_el:
                sub, _n = self.flatten(p, set())
                parts.append(self._render_sublines(sub, self.args.markup).strip())
            body_txt = " ".join(x for x in parts if x)
        notes.append(["*", body_txt])
        cur_subline.append(("noteref", None))

    def _frame_image(self, frame):
        img = frame.find(qn("draw", "image"))
        if img is not None:
            return self._image_name(img)
        return None

    def _image_name(self, img):
        href = img.get(qn("xlink", "href"))
        if not href:
            return None
        return os.path.basename(href.rstrip("/"))

    # ---- сериализация на токени --------------------------------------------
    def _render_subline(self, tokens, markup):
        pieces = []
        for tok in tokens:
            if tok[0] == "text":
                pieces.append(wrap_mods(tok[1], tok[2], markup))
            elif tok[0] == "img":
                pieces.append("{img:%s}" % tok[1])
            elif tok[0] == "noteref":
                pieces.append(tok[1] or "*")
        return "".join(pieces)

    def _render_sublines(self, sublines, markup):
        return "\n".join(self._render_subline(sl, markup) for sl in sublines)

    # ---- обработка на един параграф ----------------------------------------
    def emit_paragraph(self, para, role, names, base_mods, marker_prefix=""):
        sublines, notes = self.flatten(para, base_mods)

        # номериране на препратките към бележки в този параграф
        refs = [i for sl in sublines for i, t in enumerate(sl) if t[0] == "noteref"]
        n_notes = len(notes)
        if n_notes > 1:
            k = 0
            for sl in sublines:
                for i, t in enumerate(sl):
                    if t[0] == "noteref":
                        k += 1
                        sl[i] = ("noteref", "*%d" % k)
                        notes[k - 1][0] = "*%d" % k
        elif n_notes == 1:
            for sl in sublines:
                for i, t in enumerate(sl):
                    if t[0] == "noteref":
                        sl[i] = ("noteref", "*")
            notes[0][0] = "*"

        rendered = [self._render_subline(sl, self.args.markup) for sl in sublines]
        rendered = [r for r in rendered] or [""]

        # изпразваме напълно празни параграфи (без картинка/бележка)
        if all(r.strip() == "" for r in rendered) and not notes:
            return False

        for r in rendered:
            self.line("%s\t%s" % (marker_prefix, r))

        for ref, txt in notes:
            self.line("\t[%s %s]" % (ref, txt))
        return True

    # ---- заглавия ----------------------------------------------------------
    def emit_heading(self, heading):
        self.close_block()
        level = heading.get(qn("text", "outline-level"), "1")
        try:
            depth = max(1, int(level))
        except ValueError:
            depth = 1
        marker = ">" * depth
        sublines, notes = self.flatten(heading, set())
        rendered = [self._render_subline(sl, self.args.markup).strip() for sl in sublines]
        rendered = [r for r in rendered if r] or [""]
        self.blank()
        self.blank() if depth == 1 else None
        for r in rendered:
            self.line(("%s\t%s" % (marker, r)) if r else marker)
        for ref, txt in notes:
            self.line("\t[%s %s]" % (ref, txt))
        self.blank()

    # ---- заглавен блок (| автор / заглавие) --------------------------------
    def emit_title_block(self, authors, titles):
        wrote = False
        for a in authors:
            self.line("|\t%s" % a)
            wrote = True
        for t in titles:
            self.line("|\t%s" % t)
            wrote = True
        if wrote:
            self.blank()

    # ---- сюжетен разделител -------------------------------------------------
    def emit_divider(self):
        self.close_block()
        self.blank()
        self.line("\t%s" % self.args.divider)
        self.blank()


# --- Обхождане на тялото на документа ----------------------------------------
SKIP_TAGS = {"table-of-content", "illustration-index", "object-index",
             "user-index", "alphabetical-index", "bibliography",
             "table-index", "sequence-decls", "soft-page-break"}


def iter_blocks(container):
    """Генерира (kind, element) в реда на документа.

    kind ∈ {'h', 'p', 'table'}; влиза в списъци, секции и рамки-контейнери.
    """
    for child in container:
        tag = ln(child.tag)
        if tag in SKIP_TAGS:
            continue
        if tag == "h":
            yield ("h", child)
        elif tag == "p":
            yield ("p", child)
        elif tag == "table":
            yield ("table", child)
        elif tag in ("list", "list-item", "list-header", "section",
                     "index-body", "table-of-content"):
            if tag == "table-of-content":
                continue
            for item in iter_blocks(child):
                yield item
        # други контейнери пропускаме


def load_xml(zf, name):
    try:
        data = zf.read(name)
    except KeyError:
        return None
    return ET.fromstring(data)


def convert(path, args):
    with zipfile.ZipFile(path) as zf:
        content = load_xml(zf, "content.xml")
        if content is None:
            raise ValueError("Липсва content.xml — това валиден .odt файл ли е?")
        styles_root = load_xml(zf, "styles.xml")

    styles = Styles()
    styles.add_root(styles_root)
    styles.add_root(content)

    body = content.find(qn("office", "body"))
    text_root = body.find(qn("office", "text")) if body is not None else None
    if text_root is None:
        raise ValueError("Липсва office:text — няма съдържание за конвертиране.")

    conv = Converter(styles, args)

    # --- автоматично разпознаване на заглавен блок в началото --------------
    blocks = list(iter_blocks(text_root))
    detected_authors, detected_titles = [], []
    consumed = 0
    if not (args.author or args.title):
        for kind, el in blocks:
            if kind != "p":
                break
            sname = el.get(qn("text", "style-name"))
            names = styles.names(sname) if sname else []
            kindt = title_kind(names)
            text = "".join(el.itertext()).strip()
            if kindt == "author" and text:
                detected_authors.append(text)
                consumed += 1
            elif kindt in ("title", "subtitle") and text:
                detected_titles.append(text)
                consumed += 1
            else:
                break

    authors = ([args.author] if args.author else detected_authors)
    titles = ([args.title] if args.title else detected_titles)
    conv.emit_title_block(authors, titles)
    if not (args.author or args.title):
        blocks = blocks[consumed:]

    # --- основно обхождане --------------------------------------------------
    for kind, el in blocks:
        if kind == "h":
            conv.emit_heading(el)
            continue
        if kind == "table":
            conv.close_block()
            emit_table(conv, el, styles, args)
            continue

        # параграф
        sname = el.get(qn("text", "style-name"))
        names = styles.names(sname) if sname else []
        role = classify_role(names)
        text = "".join(el.itertext())

        # ред за автор (@) вътре в отворен епиграф/цитат/стихотворение
        if role is None and is_attribution(names) and conv.open_block in ("E", "C", "P"):
            conv.emit_paragraph(el, None, names, set(), marker_prefix="@")
            continue

        # сюжетен разделител?
        if looks_like_divider(text) or (args.blank_as_divider and text.strip() == ""
                                        and role is None):
            if text.strip() == "" and not args.blank_as_divider:
                pass
            else:
                conv.emit_divider()
                continue

        base_mods = props_to_mods(set(), styles.text_props(sname)) if sname else set()
        # цели-блокове не се обгръщат допълнително в акцент
        if role in ("E", "C", "P", "D", "A"):
            base_mods = set()

        if role:
            conv.ensure_block(role)
            prefix = ""
            if role in ("E", "C", "P") and is_attribution(names):
                prefix = "@"
                conv.emit_paragraph(el, role, names, set(), marker_prefix=prefix)
            else:
                conv.emit_paragraph(el, role, names, set())
            continue

        # извън блок → затваряме евентуален отворен блок
        conv.close_block()

        if is_subheading(names):
            conv.emit_paragraph(el, None, names, set(), marker_prefix="#")
            continue

        conv.emit_paragraph(el, None, names, base_mods)

    conv.close_block()

    # --- информационен блок (по избор) -------------------------------------
    if args.info:
        conv.blank()
        conv.line("I>")
        with open(args.info, encoding="utf-8") as f:
            for row in f.read().splitlines():
                conv.line("\t%s" % row if row.strip() else "")
        conv.line("I$")

    # --- почистване на изходните редове ------------------------------------
    lines = conv.out
    # без повече от един последователен празен ред
    cleaned = []
    for ln_ in lines:
        if ln_ == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(ln_)
    while cleaned and cleaned[0] == "":
        cleaned.pop(0)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned) + "\n"


def _render_cell(conv, cell, styles, args):
    """Връща (текст, брой_бележки) за една клетка.

    Вграденото форматиране (курсив/получер и т.н.) се запазва; ако цялата
    клетка е получер (напр. заглавен ред), това идва от стила на параграфа.
    Бележки под линия в таблици се пропускат (много рядък случай)."""
    parts, n_notes = [], 0
    for blk in cell:
        tag = ln(blk.tag)
        if tag in ("p", "h"):
            paras = [blk]
        elif tag == "list":
            paras = list(blk.iter(qn("text", "p")))
        else:
            continue
        for p in paras:
            sname = p.get(qn("text", "style-name"))
            base = props_to_mods(set(), styles.text_props(sname)) if sname else set()
            sublines, notes = conv.flatten(p, base)
            n_notes += len(notes)
            for sl in sublines:                 # махаме препратките към бележки
                sl[:] = [t for t in sl if t[0] != "noteref"]
            txt = " ".join(conv._render_subline(sl, args.markup)
                           for sl in sublines).strip()
            if txt:
                parts.append(txt)
    text = " ".join(parts)
    # литералната черта би счупила колоните — заместваме я с плътна черта
    text = text.replace("|", "¦")
    return text, n_notes


def emit_table(conv, table, styles, args):
    """Извежда ODT таблица като SFB блок  T> … T$  с клетки, разделени с ' | '.

    Всеки ред е един табулиран ред; клетките се разделят с ' | '. Заглавните
    редове (table:table-header-rows) се обхождат наравно и запазват получерния
    си стил, ако е зададен в .odt. Хоризонтално слети и повтарящи се клетки се
    допълват с празни клетки, за да се пази подредбата на колоните."""
    rows = list(table.iter(qn("table", "table-row")))
    if not rows:
        return
    conv.blank()
    conv.line("T>")
    dropped = 0
    for row in rows:
        cells = []
        for cell in row:
            tag = ln(cell.tag)
            if tag not in ("table-cell", "covered-table-cell"):
                continue
            rep = int(cell.get(qn("table", "number-columns-repeated"), "1") or 1)
            if tag == "covered-table-cell":
                cells.extend([""] * rep)
                continue
            txt, n = _render_cell(conv, cell, styles, args)
            dropped += n
            # Хоризонтално слетите клетки в ODT са последвани от изрични
            # <covered-table-cell/>, които вече попълват липсващите колони,
            # затова тук не добавяме допълнителни празни клетки по colspan.
            for _ in range(rep):
                cells.append(txt)
        conv.line("\t" + " | ".join(cells))
    conv.line("T$")
    conv.blank()
    if dropped:
        sys.stderr.write("ПРЕДУПРЕЖДЕНИЕ: %d бележки под линия в таблица бяха "
                         "пропуснати — добавете ги ръчно.\n" % dropped)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Конвертор от .odt към SFB формата на Читанка.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="входен .odt файл")
    ap.add_argument("-o", "--output", help="изходен .sfb файл (по подразбиране: "
                    "като входа, но с разширение .sfb). Никога не може да "
                    "съвпадне с входа.")
    ap.add_argument("--author", help="автор(и) за заглавния | блок "
                    "(няколко се разделят със запетая във вашия текст)")
    ap.add_argument("--title", help="заглавие за заглавния | блок")
    ap.add_argument("--divider", default="* * *",
                    help="текст на сюжетния разделител (по подразбиране '* * *'; "
                         "често се използва и '****')")
    ap.add_argument("--markup", choices=["mixed", "braces"], default="mixed",
                    help="'mixed' (по подразбиране): _курсив_ и __получер__, "
                         "фигурни скоби за индекси/комбинации; "
                         "'braces': винаги {e}/{s}/{sub}/{sup}")
    ap.add_argument("--blank-as-divider", action="store_true",
                    help="третирай празните параграфи като сюжетни разделители")
    ap.add_argument("--info", metavar="FILE",
                    help="текстов файл, чието съдържание да се сложи в I> … I$ "
                         "накрая (издание, сканиране и т.н.)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.input):
        ap.error("файлът не съществува: %s" % args.input)

    # Изходът по подразбиране е името на входа с разширение .sfb.
    out_path = args.output or (os.path.splitext(args.input)[0] + ".sfb")

    # Предпазна мярка: изходът НИКОГА не бива да съвпадне с входа, за да не се
    # презапише оригиналният .odt (или какъвто и да е входен файл).
    def _same_file(a, b):
        try:
            if os.path.exists(a) and os.path.exists(b):
                return os.path.samefile(a, b)
        except OSError:
            pass
        return (os.path.normcase(os.path.abspath(a))
                == os.path.normcase(os.path.abspath(b)))

    if _same_file(out_path, args.input):
        ap.error("изходният файл съвпада с входния (%s) — това би презаписало "
                 "оригинала. Задайте различно име с -o или преименувайте входа."
                 % out_path)

    try:
        result = convert(args.input, args)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write("ГРЕШКА: %s\n" % e)
        return 1

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(result)
    sys.stderr.write("Готово → %s\n" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
