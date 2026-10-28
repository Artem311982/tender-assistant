import os
import re
import docx
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
from datetime import datetime


def clean_spaces(text):
    """Прибирає подвійні та кратні пробіли у кожному рядку, зберігаючи переноси рядків."""
    if text is None:
        return ""
    text = str(text)
    lines = text.split('\n')
    return '\n'.join(re.sub(r' {2,}', ' ', line).strip() for line in lines)


def fmt_money(val):
    """Форматує число у вигляд '9 875 000,00'."""
    try:
        num = float(str(val).replace(' ', '').replace('\u00a0', '').replace(',', '.'))
        formatted = f"{num:,.2f}".replace(',', ' ').replace('.', ',')
        return formatted
    except Exception:
        return clean_spaces(str(val))


def parse_float(val, default=0.0):
    if val is None:
        return default
    s = str(val).strip()
    s = re.sub(r'[^\d,.-]', '', s)
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return default


def setup_doc_bw():
    """Створює новий документ Word за ДСТУ 4163:2020 без колонтитулів та без кольорів (Zero-Color Policy)."""
    doc = docx.Document()

    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(1.5)

    # ЖОДНИХ КОЛОНТИТУЛІВ (очищуємо та відключаємо)
    section.header.is_linked_to_previous = True
    section.footer.is_linked_to_previous = True
    for p in section.header.paragraphs:
        p.text = ""
    for p in section.footer.paragraphs:
        p.text = ""

    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)

    return doc


def add_hyperlink_bw(paragraph, url, text, underline=True, bold=False, font_size_pt=12):
    """Додає чорне підкреслене гіперпосилання без синього кольору (#000000)."""
    text = clean_spaces(text)
    part = paragraph.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)
    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), 'Times New Roman')
    rFonts.set(qn('w:hAnsi'), 'Times New Roman')
    rFonts.set(qn('w:cs'), 'Times New Roman')
    rPr.append(rFonts)

    sz_val = str(int(font_size_pt * 2))
    sz = OxmlElement('w:sz')
    sz.set(qn('w:val'), sz_val)
    rPr.append(sz)
    szCs = OxmlElement('w:szCs')
    szCs.set(qn('w:val'), sz_val)
    rPr.append(szCs)

    c = OxmlElement('w:color')
    c.set(qn('w:val'), '000000')
    rPr.append(c)

    if underline:
        u = OxmlElement('w:u')
        u.set(qn('w:val'), 'single')
        rPr.append(u)
    if bold:
        b = OxmlElement('w:b')
        rPr.append(b)

    new_run.append(rPr)
    new_run.text = text
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink


def set_table_borders_bw(table):
    """Встановлює тонкі чорні межі таблиці 0.5 pt (#000000)."""
    tblPr = table._tbl.tblPr
    tblBorders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>\n'
        f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:insideV w:val="single" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'</w:tblBorders>'
    )
    tblPr.append(tblBorders)


def set_table_margins(table, top=75, bottom=75, left=110, right=110):
    tblPr = table._tbl.tblPr
    tblCellMar = parse_xml(
        f'<w:tblCellMar {nsdecls("w")}>\n'
        f'  <w:top w:w="{top}" w:type="dxa"/>\n'
        f'  <w:bottom w:w="{bottom}" w:type="dxa"/>\n'
        f'  <w:left w:w="{left}" w:type="dxa"/>\n'
        f'  <w:right w:w="{right}" w:type="dxa"/>\n'
        f'</w:tblCellMar>'
    )
    tblPr.append(tblCellMar)


def add_body_p(doc, text="", indent=True, space_after=4, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    text = clean_spaces(text)
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if indent:
        p.paragraph_format.first_line_indent = Cm(1.25)
    if text:
        r = p.add_run(text)
        r.font.name = "Times New Roman"
        r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(0, 0, 0)
    return p


def add_heading_1(doc, text):
    text = clean_spaces(text)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0, 0, 0)
    return p


def add_heading_2(doc, text):
    text = clean_spaces(text)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(12)
    r.font.bold = True
    r.font.color.rgb = RGBColor(0, 0, 0)
    return p


def add_signature_block(doc, buyer_name, authorized_person, doc_date):
    """Додає стандартний блок підпису уповноваженої особи за ДСТУ 4163:2020."""
    p_sig_space = doc.add_paragraph()
    p_sig_space.paragraph_format.space_before = Pt(16)
    p_sig_space.paragraph_format.space_after = Pt(4)

    table_sig = doc.add_table(rows=1, cols=2)
    table_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_sig.autofit = False
    set_table_margins(table_sig, top=60, bottom=60, left=60, right=60)
    table_sig.rows[0].cells[0].width = Cm(10.0)
    table_sig.rows[0].cells[1].width = Cm(6.5)

    cell_sig0 = table_sig.rows[0].cells[0]
    cell_sig1 = table_sig.rows[0].cells[1]

    ps0 = cell_sig0.paragraphs[0]
    ps0.paragraph_format.line_spacing = 1.15
    rs0 = ps0.add_run(clean_spaces(
        f"Уповноважена особа з публічних закупівель\n{buyer_name}"
    ))
    rs0.font.name = "Times New Roman"
    rs0.font.size = Pt(11)
    rs0.font.bold = True
    rs0.font.color.rgb = RGBColor(0, 0, 0)

    ps1 = cell_sig1.paragraphs[0]
    ps1.paragraph_format.line_spacing = 1.15
    ps1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    rs1 = ps1.add_run(clean_spaces(f"\n___________ {authorized_person}\n{doc_date}"))
    rs1.font.name = "Times New Roman"
    rs1.font.size = Pt(11)
    rs1.font.bold = True
    rs1.font.color.rgb = RGBColor(0, 0, 0)


def generate_justification_bundle(order_data, benchmarks, output_dir):
    """
    Генерує в окремій папці предмета закупівлі тільки 1 файл Обґрунтування та 1 файл Додатка за ДСТУ 4163:2020 (Zero-Color Policy):
    1. Обґрунтування (без шапки, у п. 1 скорочений вступ та 6 рядків таблиці, у п. 2 таблиця без строків поставки, п. 3, п. 4 без ПДВ)
    2. Додаток до обґрунтування (вирівняна нумерація: 1, 2, 2.1, 2.2 без ПДВ; без переліку джерел та без порядку оприлюднення).
    """
    buyer_name = clean_spaces(order_data.get("buyer_name") or "Національного університету кораблебудування імені адмірала Макарова")
    edrpou = clean_spaces(order_data.get("edrpou") or "02066753")
    buyer_address = clean_spaces(order_data.get("buyer_address") or "Україна")
    authorized_person = clean_spaces(order_data.get("authorized_person") or "Шумова Людмила Владиславівна")

    tender_id = clean_spaces(order_data.get("tender_id") or "UA-2026-10-09-013480-a")
    plan_id = clean_spaces(order_data.get("plan_id") or "949d3328d8834c33842e25e0ad1c806f")
    subject_name = clean_spaces(order_data.get("subject_name") or "Теплова енергія")
    cpv_code = clean_spaces(order_data.get("cpv_code") or "09320000-8 — Пара, гаряча вода та пов’язана продукція")
    kekv = clean_spaces(order_data.get("kekv") or "2271")
    delivery_address = clean_spaces(order_data.get("delivery_address") or buyer_address)
    tech_specs = clean_spaces(order_data.get("tech_specs") or (
        f"Якісні та технічні характеристики предмета закупівлі «{subject_name}» (код за ДК 021:2015: {cpv_code}) "
        "визначені відповідно до потреб замовника, чинних державних стандартів (ДСТУ), технічних регламентів та галузевих норм України."
    ))
    doc_date = clean_spaces(order_data.get("doc_date") or datetime.now().strftime("%d.%m.%Y"))

    subj_low = subject_name.lower()
    is_elec = "електрич" in subj_low or "0931" in cpv_code
    is_heat = "теплов" in subj_low or "0932" in cpv_code

    default_unit = "кВт·год" if is_elec else ("Гкал" if is_heat else "шт.")
    unit_name = clean_spaces(order_data.get("unit_name") or default_unit)
    expected_value = parse_float(order_data.get("expected_value"), 9875000.0)

    raw_qty = parse_float(order_data.get("quantity"), 0.0)
    if raw_qty <= 0:
        if is_heat:
            quantity = 1800.0
        elif is_elec and expected_value > 0:
            quantity = round(expected_value / 9.0, 2)
        else:
            quantity = 1.0
    else:
        quantity = raw_qty

    unit_price = expected_value / quantity if quantity > 0 else expected_value

    # Розрахунок статистики по закупівлях Prozorro (без ПДВ)
    unit_prices_bench = []
    for b in benchmarks:
        up = parse_float(b.get("unit_price_no_vat"), 0.0)
        if up > 0:
            unit_prices_bench.append(up)

    avg_market_price = sum(unit_prices_bench) / len(unit_prices_bench) if unit_prices_bench else unit_price
    min_market_price = min(unit_prices_bench) if unit_prices_bench else unit_price
    max_market_price = max(unit_prices_bench) if unit_prices_bench else unit_price
    deviation_pct = ((unit_price - avg_market_price) / avg_market_price * 100.0) if avg_market_price > 0 else 0.0

    # Перевірка: чи очікувана вартість / ціна замовника є найвищою серед порівнюваних закупівель.
    # Якщо ціна за одиницю або загальна сума хоча б однієї закупівлі в таблиці перевищує замовника,
    # попередження НЕ показується (замовник не є найдорожчим).
    is_expected_value_highest = False
    if benchmarks:
        has_higher_unit = any(parse_float(b.get("unit_price_no_vat"), 0.0) > unit_price for b in benchmarks) if unit_price > 0 else False
        has_higher_amount = any(parse_float(b.get("amount_no_vat"), 0.0) > expected_value for b in benchmarks) if expected_value > 0 else False
        if not (has_higher_unit or has_higher_amount):
            is_expected_value_highest = True

    subj_slug = re.sub(r'[^a-zA-Z0-9а-яА-ЯіїєґІЇЄҐ_-]', '_', subject_name).strip('_')[:40] or "Предмет_закупівлі"
    subj_dir = os.path.join(output_dir, subj_slug)
    os.makedirs(subj_dir, exist_ok=True)

    file1_name = f"Обґрунтування_{subj_slug}.docx"
    file2_name = f"Додаток_до_обґрунтування_{subj_slug}.docx"
    file1_path = os.path.join(subj_dir, file1_name)
    file2_path = os.path.join(subj_dir, file2_name)

    # =========================================================================
    # ФАЙЛ 1: ОБҐРУНТУВАННЯ (БЕЗ ШАПКИ, СКОРОЧЕНИЙ ВСТУП І ТАБЛИЦІ РОЗДІЛІВ 1 ТА 2)
    # =========================================================================
    doc1 = setup_doc_bw()

    p_title = doc1.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(4)
    p_title.paragraph_format.line_spacing = 1.15
    r_title = p_title.add_run("ОБҐРУНТУВАННЯ")
    r_title.font.name = "Times New Roman"
    r_title.font.size = Pt(14)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(0, 0, 0)

    p_sub = doc1.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(2)
    p_sub.paragraph_format.space_after = Pt(12)
    p_sub.paragraph_format.line_spacing = 1.15
    r_sub = p_sub.add_run(clean_spaces(
        "технічних та якісних характеристик предмета закупівлі, розміру бюджетного призначення, "
        "очікуваної вартості предмета закупівлі"
    ))
    r_sub.font.name = "Times New Roman"
    r_sub.font.size = Pt(13)
    r_sub.font.bold = True
    r_sub.font.color.rgb = RGBColor(0, 0, 0)

    # Розділ 1
    add_heading_1(doc1, "1. Загальні відомості про замовника та закупівлю")
    buyer_genitive = (
        "Національного університету кораблебудування імені адмірала Макарова"
        if ("кораблебудування" in buyer_name.lower() or edrpou == "02066753")
        else buyer_name
    )
    add_body_p(
        doc1,
        f"Це Обґрунтування складено уповноваженою особою {buyer_genitive} "
        f"({authorized_person}, дата підпису оголошення: {doc_date})"
    )

    t1_data = [
        ("Найменування замовника:", buyer_name),
        ("Ідентифікаційний код замовника в ЄДР:", edrpou),
        ("Вид та назва предмета закупівлі:", f"Товари — {subject_name}"),
        ("Код за Єдиним закупівельним словником:", f"ДК 021:2015: {cpv_code}"),
        ("Кількість товарів:", f"{fmt_money(quantity)} {unit_name}"),
        ("Очікувана вартість предмета закупівлі:", f"{fmt_money(expected_value)} грн без ПДВ")
    ]

    table1 = doc1.add_table(rows=len(t1_data), cols=2)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    table1.autofit = False
    set_table_borders_bw(table1)
    set_table_margins(table1, top=75, bottom=75, left=110, right=110)

    t1_widths = [Cm(6.2), Cm(10.3)]
    for row in table1.rows:
        for idx, w in enumerate(t1_widths):
            row.cells[idx].width = w

    for i, (label, val) in enumerate(t1_data):
        row = table1.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(2)
        r0 = p0.add_run(clean_spaces(label))
        r0.font.name = "Times New Roman"
        r0.font.size = Pt(10)
        r0.font.bold = True
        r0.font.color.rgb = RGBColor(0, 0, 0)

        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(2)
        r1 = p1.add_run(clean_spaces(val))
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(10)
        r1.font.color.rgb = RGBColor(0, 0, 0)

    doc1.add_paragraph().paragraph_format.space_after = Pt(4)

    # Розділ 2
    add_heading_1(doc1, "2. Обґрунтування технічних та якісних характеристик предмета закупівлі")
    add_body_p(
        doc1,
        f"Технічні та якісні характеристики предмета закупівлі розроблені відповідно до статті 23 Закону України «Про публічні закупівлі» "
        f"з урахуванням положень пункту 28 Особливостей № 1178 та оголошення про проведення відкритих торгів {tender_id}. "
        f"Конкретна назва предмета закупівлі: «{subject_name}» "
        f"(код згідно з Єдиним закупівельним словником ДК 021:2015: {cpv_code}). Загальний плановий обсяг закупівлі становить "
        f"{fmt_money(quantity)} {unit_name}."
    )
    add_body_p(doc1, tech_specs)

    # Таблиця місць поставки (2 стовпчики — без строків поставки)
    locs_raw = [line.strip() for line in re.split(r'[\n;]+', delivery_address) if line.strip()]
    if not locs_raw:
        locs_raw = [buyer_address]

    table_loc = doc1.add_table(rows=len(locs_raw) + 1, cols=2)
    table_loc.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_loc.autofit = False
    set_table_borders_bw(table_loc)
    set_table_margins(table_loc, top=65, bottom=65, left=100, right=100)

    t_loc_widths = [Cm(1.5), Cm(15.0)]
    for r in table_loc.rows:
        for idx, w in enumerate(t_loc_widths):
            r.cells[idx].width = w

    t_loc_hdr = ["№ з/п", f"Місце поставки товарів (згідно з оголошенням {tender_id})"]
    for idx, txt in enumerate(t_loc_hdr):
        c = table_loc.rows[0].cells[idx]
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(clean_spaces(txt))
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0, 0, 0)

    for i, addr in enumerate(locs_raw):
        row = table_loc.rows[i + 1]
        for col_idx, val_txt in enumerate([str(i + 1), addr]):
            c = row.cells[col_idx]
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx == 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(clean_spaces(val_txt))
            r.font.name = "Times New Roman"
            r.font.size = Pt(10)
            r.font.color.rgb = RGBColor(0, 0, 0)

    doc1.add_paragraph().paragraph_format.space_after = Pt(4)

    # Розділ 3
    add_heading_1(doc1, "3. Обґрунтування розміру бюджетного призначення")
    add_body_p(
        doc1,
        f"Розмір бюджетного призначення визначено відповідно до Бюджетного кодексу України, Закону України «Про Державний бюджет України на 2026 рік» "
        f"та затвердженого кошторису замовника ({buyer_name}) на 2026 рік. Відповідно до річного плану закупівель "
        f"(ідентифікатор плану: {plan_id}) та параметрів оголошення {tender_id} розмір бюджетного призначення за КЕКВ {kekv} "
        f"на закупівлю «{subject_name}» в обсязі {fmt_money(quantity)} {unit_name} становить {fmt_money(expected_value)} грн без ПДВ."
    )

    # Розділ 4
    add_heading_1(doc1, "4. Обґрунтування очікуваної вартості предмета закупівлі")
    add_body_p(
        doc1,
        "Розрахунок очікуваної вартості предмета закупівлі здійснено уповноваженою особою відповідно до Примірної методики визначення "
        "очікуваної вартості предмета закупівлі, затвердженої наказом Міністерства розвитку економіки, торгівлі та сільського господарства України "
        f"від 25.03.2020 № 275, на підставі аналізу цін (без ПДВ) закупівель аналогічного предмета закупівлі (ДК 021:2015: {cpv_code}) "
        "в електронній системі публічних закупівель Prozorro."
    )
    add_body_p(
        doc1,
        f"Загальна очікувана вартість закупівлі обсягом {fmt_money(quantity)} {unit_name} становить:\n"
        f"ОВ = {fmt_money(quantity)} {unit_name} × {fmt_money(unit_price)} грн (без ПДВ) = {fmt_money(expected_value)} грн без ПДВ."
    )

    fin_rows = [
        ("Плановий обсяг закупівлі:", f"{fmt_money(quantity)} {unit_name}"),
        (f"Розрахункова ціна за одиницю (1 {unit_name}) без ПДВ:", f"{fmt_money(unit_price)} грн без ПДВ"),
        ("ОЧІКУВАНА ВАРТІСТЬ ПРЕДМЕТА ЗАКУПІВЛІ (БЕЗ ПДВ):", f"{fmt_money(expected_value)} грн без ПДВ")
    ]

    table_fin = doc1.add_table(rows=len(fin_rows), cols=2)
    table_fin.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_fin.autofit = False
    set_table_borders_bw(table_fin)
    set_table_margins(table_fin, top=75, bottom=75, left=120, right=120)

    t_fin_widths = [Cm(10.5), Cm(6.0)]
    for r in table_fin.rows:
        for idx, w in enumerate(t_fin_widths):
            r.cells[idx].width = w

    for i, (param, val) in enumerate(fin_rows):
        row = table_fin.rows[i]
        c0, c1 = row.cells[0], row.cells[1]
        c0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        p0 = c0.paragraphs[0]
        r0 = p0.add_run(clean_spaces(param))
        r0.font.name = "Times New Roman"
        r0.font.size = Pt(10)
        r0.font.color.rgb = RGBColor(0, 0, 0)

        p1 = c1.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r1 = p1.add_run(clean_spaces(val))
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(10)
        r1.font.color.rgb = RGBColor(0, 0, 0)

        if i == len(fin_rows) - 1:
            r0.font.bold = True
            r1.font.bold = True
            r1.font.size = Pt(11)

    add_signature_block(doc1, buyer_name, authorized_person, doc_date)
    doc1.save(file1_path)

    # =========================================================================
    # ФАЙЛ 2: ДОДАТОК ДО ОБҐРУНТУВАННЯ
    # (ВИРІВНЯНА НУМЕРАЦІЯ: 1, 2, 2.1, 2.2; БЕЗ ДЖЕРЕЛ ТА БЕЗ ПОРЯДКУ ОПРИЛЮДНЕННЯ)
    # =========================================================================
    doc2 = setup_doc_bw()

    p2_title = doc2.add_paragraph()
    p2_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2_title.paragraph_format.space_before = Pt(6)
    p2_title.paragraph_format.space_after = Pt(4)
    p2_title.paragraph_format.line_spacing = 1.15
    r2_title = p2_title.add_run(clean_spaces(
        f"ДОДАТОК ДО ОБҐРУНТУВАННЯ ЗАКУПІВЛІ {tender_id}"
    ))
    r2_title.font.name = "Times New Roman"
    r2_title.font.size = Pt(13)
    r2_title.font.bold = True
    r2_title.font.color.rgb = RGBColor(0, 0, 0)

    p2_sub = doc2.add_paragraph()
    p2_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2_sub.paragraph_format.space_before = Pt(0)
    p2_sub.paragraph_format.space_after = Pt(12)
    p2_sub.paragraph_format.line_spacing = 1.15
    r2_sub = p2_sub.add_run(clean_spaces(
        "(Нормативно-правове регулювання та аналіз закупівель у системі Prozorro за 2026 рік без ПДВ)"
    ))
    r2_sub.font.name = "Times New Roman"
    r2_sub.font.size = Pt(11)
    r2_sub.font.italic = True
    r2_sub.font.color.rgb = RGBColor(0, 0, 0)

    # Розділ 1
    add_heading_1(doc2, "1. Нормативно-правове регулювання закупівлі")
    add_body_p(
        doc2,
        "Правові підстави проведення закупівлі та визначення очікуваної вартості регламентовано такими нормативно-правовими актами України:\n"
        "1. Законом України «Про публічні закупівлі» від 25.12.2015 № 922-VIII;\n"
        "2. Постановою Кабінету Міністрів України від 11.10.2016 № 710 «Про ефективне використання державних коштів» "
        "(пункт 4-1 якої зобов'язує замовника обґрунтувати технічні та якісні характеристики предмета закупівлі, розмір бюджетного "
        "призначення, очікувану вартість предмета закупівлі та оприлюднити обґрунтування на власному веб-сайті протягом 5 робочих днів "
        "з дня оприлюднення оголошення про проведення відкритих торгів);\n"
        "3. Постановою Кабінету Міністрів України від 12.10.2022 № 1178 «Про затвердження особливостей здійснення публічних закупівель "
        "товарів, робіт і послуг для замовників, передбачених Законом України “Про публічні закупівлі”, на період дії правового режиму воєнного стану "
        "в Україні та протягом 90 днів з дня його припинення або скасування» (в редакції від 29.09.2026);\n"
        "4. Примірною методикою визначення очікуваної вартості предмета закупівлі, затвердженою наказом Міністерства розвитку економіки, "
        "торгівлі та сільського господарства України від 25.03.2020 № 275."
    )

    # Розділ 2
    add_heading_1(doc2, "2. Аналіз цін постачальників та розрахунок очікуваної вартості предмета закупівлі (без ПДВ)")
    add_heading_2(doc2, "2.1. Аналіз закупівель та укладених договорів у системі Prozorro за 2026 рік (без ПДВ):")
    add_body_p(
        doc2,
        f"Відповідно до Примірної методики Мінекономіки № 275 проведено моніторинг оголошень та укладених договорів щодо предмета закупівлі "
        f"«{subject_name}» (код ДК 021:2015: {cpv_code}) в електронній системі публічних закупівель Prozorro. "
        f"Для забезпечення повної співставності з оголошенням {tender_id} усі вартісні показники закупівель та ціни за одиницю (1 {unit_name}) "
        "наведено у порівняльній таблиці без урахування податку на додану вартість (без ПДВ)."
    )

    table_bench = doc2.add_table(rows=len(benchmarks) + 1, cols=6)
    table_bench.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_bench.autofit = False
    set_table_borders_bw(table_bench)
    set_table_margins(table_bench, top=65, bottom=65, left=75, right=75)

    t_b_widths = [Cm(0.8), Cm(3.7), Cm(3.3), Cm(4.2), Cm(1.8), Cm(2.7)]
    for r in table_bench.rows:
        for idx, w in enumerate(t_b_widths):
            r.cells[idx].width = w

    tb_headers = [
        "№",
        "Замовник (ЄДРПОУ / Регіон)",
        "Постачальник / Учасник",
        "Ідентифікатор та посилання на закупівлю в Prozorro",
        f"Обсяг, {unit_name}",
        f"Сума закупівлі / Ціна за 1 {unit_name} (без ПДВ)"
    ]
    for idx, txt in enumerate(tb_headers):
        c = table_bench.rows[0].cells[idx]
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(clean_spaces(txt))
        r.font.name = "Times New Roman"
        r.font.size = Pt(8.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0, 0, 0)

    for i, b in enumerate(benchmarks):
        row = table_bench.rows[i + 1]
        tid = clean_spaces(b.get("tender_id") or "")
        turl = clean_spaces(b.get("url") or f"https://prozorro.gov.ua/uk/tender/{tid}")
        b_buyer = clean_spaces(b.get("buyer") or "")
        b_supp = clean_spaces(b.get("supplier") or "Учасник відкритих торгів")
        b_vol = clean_spaces(b.get("volume") or "За спец.")
        b_total = parse_float(b.get("amount_no_vat"), 0.0)
        b_unit = parse_float(b.get("unit_price_no_vat"), 0.0)
        price_str = f"{fmt_money(b_total)} грн без ПДВ\n({fmt_money(b_unit)} грн/{unit_name} без ПДВ)" if b_unit > 0 else f"{fmt_money(b_total)} грн без ПДВ"

        vals = [str(i + 1), b_buyer, b_supp, tid, b_vol, price_str]
        for col_idx, val in enumerate(vals):
            c = row.cells[col_idx]
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_idx in [0, 4, 5] else WD_ALIGN_PARAGRAPH.LEFT

            if col_idx == 3:
                r_id_txt = p.add_run(f"{tid}\n")
                r_id_txt.font.name = "Times New Roman"
                r_id_txt.font.size = Pt(8.5)
                r_id_txt.font.bold = True
                r_id_txt.font.color.rgb = RGBColor(0, 0, 0)
                add_hyperlink_bw(p, turl, turl, underline=True, bold=False, font_size_pt=8)
            else:
                r = p.add_run(clean_spaces(val))
                r.font.name = "Times New Roman"
                r.font.size = Pt(8.5)
                r.font.color.rgb = RGBColor(0, 0, 0)
                if col_idx == 5:
                    r.font.bold = True

    doc2.add_paragraph().paragraph_format.space_after = Pt(4)

    # Пункт 2.2
    add_heading_2(doc2, "2.2. Розрахунок середньоринкової ціни та обґрунтування очікуваної вартості (без ПДВ):")
    add_body_p(
        doc2,
        f"За результатами порівняння цін оголошень у системі Prozorro (Примірна методика № 275) "
        f"діапазон фактичних цін за 1 {unit_name} становить від {fmt_money(min_market_price)} грн до {fmt_money(max_market_price)} грн без ПДВ "
        f"(середньоринкова ціна становить {fmt_money(avg_market_price)} грн за 1 {unit_name} без ПДВ).\n"
        f"Розрахункова ціна одиниці закупівлі замовника ({fmt_money(unit_price)} грн за 1 {unit_name} без ПДВ) відповідає кон'юнктурі ринку. "
        f"Загальна очікувана вартість закупівлі обсягом {fmt_money(quantity)} {unit_name} становить: "
        f"{fmt_money(quantity)} × {fmt_money(unit_price)} грн = {fmt_money(expected_value)} грн без ПДВ."
    )

    add_signature_block(doc2, buyer_name, authorized_person, doc_date)
    doc2.save(file2_path)

    return {
        "file1_name": file1_name,
        "file1_path": file1_path,
        "file2_name": file2_name,
        "file2_path": file2_path,
        "stats": {
            "unit_price_no_vat": round(unit_price, 2),
            "avg_market_price_no_vat": round(avg_market_price, 2),
            "min_market_price_no_vat": round(min_market_price, 2),
            "max_market_price_no_vat": round(max_market_price, 2),
            "deviation_pct": round(deviation_pct, 2),
            "expected_value_no_vat": round(expected_value, 2),
            "quantity": quantity,
            "unit_name": unit_name,
            "is_expected_value_highest": bool(is_expected_value_highest)
        }
    }


def generate_form_template_docx(form_title, fields, output_path):
    """Генерує чистий чорно-білий шаблон форми .docx за ДСТУ 4163:2020 для скачування користувачем."""
    doc = setup_doc_bw()
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(10)
    r_t = p_title.add_run(clean_spaces(form_title))
    r_t.font.name = "Times New Roman"
    r_t.font.size = Pt(13)
    r_t.font.bold = True
    r_t.font.color.rgb = RGBColor(0, 0, 0)

    add_body_p(
        doc,
        "Заповніть праву колонку таблиці та завантажте збережений файл .docx у власному кабінеті системи «Тендерний помічник» "
        "(або заповніть відповідну онлайн-форму безпосередньо на сайті).",
        indent=False,
        space_after=8
    )

    table = doc.add_table(rows=len(fields) + 1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders_bw(table)
    set_table_margins(table, top=80, bottom=80, left=110, right=110)

    widths = [Cm(7.0), Cm(9.5)]
    for r in table.rows:
        for i, w in enumerate(widths):
            r.cells[i].width = w

    hdr = ["Назва поля (реквізит закупівлі)", "Значення (заповнюється замовником)"]
    for i, h in enumerate(hdr):
        c = table.rows[0].cells[i]
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(h)
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)

    for idx, f in enumerate(fields):
        row = table.rows[idx + 1]
        c0, c1 = row.cells[0], row.cells[1]
        p0 = c0.paragraphs[0]
        r0 = p0.add_run(clean_spaces(f.get("label", "")))
        r0.font.name = "Times New Roman"
        r0.font.size = Pt(11)
        r0.font.bold = True
        r0.font.color.rgb = RGBColor(0, 0, 0)

        p1 = c1.paragraphs[0]
        r1 = p1.add_run("")
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(11)
        r1.font.color.rgb = RGBColor(0, 0, 0)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    return output_path


FIELD_MAPPING_HINTS = [
    (["найменування замовника", "назва замовника", "замовник", "організація"], "buyer_name"),
    (["єдрпоу", "код єдрпоу", "ідентифікаційний код"], "edrpou"),
    (["місцезнаходження", "юридична адреса", "адреса замовника"], "buyer_address"),
    (["керівник", "прізвище керівника", "ректор", "директор"], "director_name"),
    (["посада керівника"], "director_title"),
    (["уповноважена особа", "контактна особа", "підписант"], "authorized_person"),
    (["email", "e-mail", "електронна пошта", "пошта"], "email"),
    (["телефон", "тел."], "phone"),
    (["сайт", "веб-сайт", "web"], "website"),
    (["ідентифікатор закупівлі", "номер тендеру", "id тендеру", "ua-", "prozorro"], "tender_id"),
    (["план закупівлі", "ідентифікатор плану"], "plan_id"),
    (["предмет закупівлі", "конкретна назва предмета", "назва предмета"], "subject_name"),
    (["код дк", "021:2015", "cpv"], "cpv_code"),
    (["очікувана вартість", "бюджетне призначення", "сума закупівлі", "вартість"], "expected_value"),
    (["кількість", "обсяг"], "quantity"),
    (["одиниця виміру", "од. вим"], "unit_name"),
    (["кекв"], "kekv"),
    (["строк поставки", "термін поставки"], "delivery_term"),
    (["місце поставки", "адреса поставки"], "delivery_address"),
    (["технічні", "якісні характеристики"], "tech_specs"),
]


def guess_field_key(label):
    l_low = label.lower().strip()
    for keywords, key in FIELD_MAPPING_HINTS:
        for kw in keywords:
            if kw in l_low:
                return key
    slug = re.sub(r'[^a-zA-Z0-9а-яА-ЯіїєґІЇЄҐ]+', '_', l_low).strip('_')
    return f"custom_{slug[:30]}"


def parse_docx_form_structure(docx_path):
    """
    Читає завантажений адміністратором файл .docx і витягує назву форми та перелік полів з таблиць.
    """
    doc = docx.Document(docx_path)
    title = ""
    for p in doc.paragraphs:
        if p.text and p.text.strip():
            title = clean_spaces(p.text.strip())
            title = title.replace("Інформа63+дція", "Інформація")
            break
    if not title:
        title = os.path.splitext(os.path.basename(docx_path))[0]

    extracted_fields = []
    seen_keys = set()
    for t in doc.tables:
        for row in t.rows:
            cells = [clean_spaces(c.text.strip()) for c in row.cells]
            if not cells or not cells[0]:
                continue
            label = cells[0].rstrip(':').strip()
            if label.lower() in ["№", "№ з/п", "назва поля (реквізит закупівлі)", "параметр"]:
                continue
            key = guess_field_key(label)
            if key == "email" or "email" in label.lower() or "електронна пошта" in label.lower():
                continue
            if key in seen_keys:
                key = f"{key}_{len(extracted_fields)+1}"
            seen_keys.add(key)
            extracted_fields.append({
                "key": key,
                "label": label,
                "type": "number" if key in ("expected_value", "quantity") else ("textarea" if key in ("tech_specs", "delivery_address") else "text"),
                "required": True
            })

    return {"title": title, "fields": extracted_fields}


def parse_filled_docx_values(docx_path):
    """
    Читає заповнений користувачем файл .docx і повертає словник {field_key: value, label: value}.
    """
    doc = docx.Document(docx_path)
    values = {}
    raw_pairs = []
    for t in doc.tables:
        for row in t.rows:
            cells = [clean_spaces(c.text.strip()) for c in row.cells]
            if len(cells) >= 2 and cells[0]:
                label = cells[0].rstrip(':').strip()
                val = cells[1].strip()
                if label.lower() in ["назва поля (реквізит закупівлі)", "№", "№ з/п"]:
                    continue
                key = guess_field_key(label)
                if val:
                    values[key] = val
                raw_pairs.append({"label": label, "key": key, "value": val})
    return {"mapped": values, "pairs": raw_pairs}
