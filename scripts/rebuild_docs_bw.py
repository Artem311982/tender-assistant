import docx
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls
import os
import re

def clean_spaces(text):
    """Прибирає подвійні та кратні пробіли у кожному рядку, зберігаючи переноси рядків."""
    if not text:
        return ""
    lines = text.split('\n')
    return '\n'.join(re.sub(r' {2,}', ' ', line).strip() for line in lines)

def setup_doc_bw():
    """Створює новий документ Word за ДСТУ 4163:2020 без колонтитулів та без кольорів."""
    doc = docx.Document()

    # Поля сторінки за ДСТУ 4163:2020 (ліве 30 мм, праве 15 мм, верхнє/нижнє 20 мм)
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(1.5)

    # ЖОДНИХ КОЛОНТИТУЛІВ
    section.header.is_linked_to_previous = True
    section.footer.is_linked_to_previous = True
    for p in section.header.paragraphs:
        p.text = ""
    for p in section.footer.paragraphs:
        p.text = ""

    # Базовий стиль: Times New Roman, 12 pt, виключно чорний колір
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Times New Roman'
    normal_style.font.size = Pt(12)
    normal_style.font.color.rgb = RGBColor(0, 0, 0)

    return doc

def add_hyperlink_bw(paragraph, url, text, underline=True, bold=False, font_size_pt=12):
    """Додає чорне підкреслене гіперпосилання без синього кольору."""
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

    # Виключно чорний колір (#000000)
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

def set_table_margins(table, top=100, bottom=100, left=130, right=130):
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

def add_signature_block(doc):
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
        "Уповноважена особа з публічних закупівель\n"
        "Національного університету кораблебудування\n"
        "імені адмірала Макарова"
    ))
    rs0.font.name = "Times New Roman"
    rs0.font.size = Pt(11)
    rs0.font.bold = True
    rs0.font.color.rgb = RGBColor(0, 0, 0)

    ps1 = cell_sig1.paragraphs[0]
    ps1.paragraph_format.line_spacing = 1.15
    ps1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    rs1 = ps1.add_run(clean_spaces("\n\n___________ Людмила ШУМОВА\n«09» жовтня 2026 року"))
    rs1.font.name = "Times New Roman"
    rs1.font.size = Pt(11)
    rs1.font.bold = True
    rs1.font.color.rgb = RGBColor(0, 0, 0)


# ==============================================================================
# ФАЙЛ 1: ОБҐРУНТУВАННЯ (БЕЗ ШАПКИ, СКОРОЧЕНИЙ ВСТУП І ТАБЛИЦІ РОЗДІЛІВ 1 ТА 2)
# ==============================================================================
def create_main_justification_doc(output_path):
    doc = setup_doc_bw()

    # Заголовок документа (без шапки "ЗАТВЕРДЖУЮ...")
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(4)
    p_title.paragraph_format.line_spacing = 1.15
    r_title = p_title.add_run("ОБҐРУНТУВАННЯ")
    r_title.font.name = "Times New Roman"
    r_title.font.size = Pt(14)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(0, 0, 0)

    p_sub = doc.add_paragraph()
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

    # ==================== РОЗДІЛ 1 ====================
    add_heading_1(doc, "1. Загальні відомості про замовника та закупівлю")
    add_body_p(
        doc,
        "Це Обґрунтування складено уповноваженою особою Національного університету кораблебудування імені адмірала Макарова "
        "(Шумова Людмила Владиславівна, дата підпису оголошення: 09.10.2026)"
    )

    t1_data = [
        ("Найменування замовника:", "НАЦІОНАЛЬНИЙ УНІВЕРСИТЕТ КОРАБЛЕБУДУВАННЯ ІМЕНІ АДМІРАЛА МАКАРОВА"),
        ("Ідентифікаційний код замовника в ЄДР:", "02066753"),
        ("Вид та назва предмета закупівлі:", "Товари — Теплова енергія (Лот 1 — Теплова енергія)"),
        ("Код за Єдиним закупівельним словником:", "ДК 021:2015: 09320000-8 — Пара, гаряча вода та пов’язана продукція"),
        ("Кількість товарів:", "1 800 гігакалорія (Гкал)"),
        ("Очікувана вартість предмета закупівлі:", "9 875 000,00 грн без ПДВ")
    ]

    table1 = doc.add_table(rows=len(t1_data), cols=2)
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

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # ==================== РОЗДІЛ 2 ====================
    add_heading_1(doc, "2. Обґрунтування технічних та якісних характеристик предмета закупівлі")
    add_body_p(
        doc,
        "Технічні та якісні характеристики предмета закупівлі розроблені відповідно до статті 23 Закону України «Про публічні закупівлі» "
        "з урахуванням положень пункту 28 Особливостей № 1178 та оголошення про проведення відкритих торгів UA-2026-10-09-013480-a. "
        "Вид предмета закупівлі: товари. Назва номенклатурної позиції: Теплова енергія (код згідно з Єдиним закупівельним словником "
        "ДК 021:2015: 09320000-8 — Пара, гаряча вода та пов’язана продукція). Загальний обсяг постачання становить 1 800 гігакалорій (Гкал)."
    )
    add_body_p(
        doc,
        "Вимоги до технічних параметрів і якості теплоносія:\n"
        "1. Параметри теплоносія: Температура мережної води в подавальному трубопроводі на межі балансової належності має відповідати "
        "затвердженому температурному графіку централізованого опалення для відповідної середньодобової температури зовнішнього повітря.\n"
        "2. Гідравлічний режим: Робочий тиск на вводі повинен забезпечувати стабільну циркуляцію теплоносія у внутрішньобудинкових системах "
        "об'єктів університету відповідно до будівельних і санітарних норм.\n"
        "3. Якість теплоносія: Фізико-хімічні показники теплоносія повинні відповідати Правилам технічної експлуатації теплових установок і мереж.\n"
        "4. Режим поставки та розрахунків: Відповідно до умов оголошення здійснюється повторювана поставка за заявкою замовника "
        "(період: 61 календарний день) на умовах післяоплати 100% протягом 30 робочих днів після поставки товару.\n"
        "5. Комерційний облік: Обсяг фактично спожитої теплової енергії (у Гкал) визначається на підставі показників приладів комерційного обліку "
        "відповідно до Закону України «Про комерційний облік теплової енергії та водопостачання»."
    )

    add_body_p(
        doc,
        "Відповідно до оголошення про проведення відкритих торгів UA-2026-10-09-013480-a місце поставки товарів охоплює 9 локацій "
        "замовника у м. Миколаєві (загальний обсяг за лотом № 1 становить 1 800 Гкал):"
    )

    locs = [
        ("1", "54007, Україна, Миколаївська область, м. Миколаїв, вул. Ковальська, 5"),
        ("2", "54007, Україна, Миколаївська область, м. Миколаїв, вул. Марка Кропивницького, 138а"),
        ("3", "54007, Україна, Миколаївська область, м. Миколаїв, вул. Морехідна, 2"),
        ("4", "54007, Україна, Миколаївська область, м. Миколаїв, проспект Героїв України, 9"),
        ("5", "54007, Україна, Миколаївська область, м. Миколаїв, вул. Бузника, 5"),
        ("6", "54007, Україна, Миколаївська область, м. Миколаїв, вул. Бузника, 5"),
        ("7", "54007, Україна, Миколаївська область, м. Миколаїв, проспект Героїв України, 11"),
        ("8", "54007, Україна, Миколаївська область, м. Миколаїв, вул. Бузника, 3"),
        ("9", "54007, Україна, Миколаївська область, м. Миколаїв, вул. Колодязна, 21")
    ]

    table_loc = doc.add_table(rows=len(locs) + 1, cols=2)
    table_loc.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_loc.autofit = False
    set_table_borders_bw(table_loc)
    set_table_margins(table_loc, top=65, bottom=65, left=100, right=100)

    t_loc_widths = [Cm(1.5), Cm(15.0)]
    for r in table_loc.rows:
        for idx, w in enumerate(t_loc_widths):
            r.cells[idx].width = w

    t_loc_hdr = ["№ з/п", "Місце поставки товарів (згідно з оголошенням UA-2026-10-09-013480-a)"]
    for idx, txt in enumerate(t_loc_hdr):
        c = table_loc.rows[0].cells[idx]
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(clean_spaces(txt))
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0, 0, 0)

    for i, (n, addr) in enumerate(locs):
        row = table_loc.rows[i+1]
        c0, c1 = row.cells[0], row.cells[1]
        c0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        c1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r0 = p0.add_run(clean_spaces(n))
        r0.font.name = "Times New Roman"
        r0.font.size = Pt(10)
        r0.font.color.rgb = RGBColor(0, 0, 0)

        p1 = c1.paragraphs[0]
        r1 = p1.add_run(clean_spaces(addr))
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(10)
        r1.font.color.rgb = RGBColor(0, 0, 0)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # ==================== РОЗДІЛ 3 ====================
    add_heading_1(doc, "3. Обґрунтування розміру бюджетного призначення")
    add_body_p(
        doc,
        "Розмір бюджетного призначення визначено відповідно до Бюджетного кодексу України, Закону України «Про Державний бюджет "
        "України на 2026 рік» та кошторису Національного університету кораблебудування імені адмірала Макарова на 2026 рік. "
        "Відповідно до річного плану закупівель (ідентифікатор плану: 949d3328d8834c33842e25e0ad1c806f) та оголошення про проведення "
        "відкритих торгів UA-2026-10-09-013480-a розмір бюджетного призначення за КЕКВ 2271 «Оплата теплопостачання» на закупівлю "
        "1 800 гігакалорій теплової енергії становить 9 875 000,00 грн (дев'ять мільйонів вісімсот сімдесят п'ять тисяч гривень 00 копійок) без ПДВ."
    )

    # ==================== РОЗДІЛ 4 ====================
    add_heading_1(doc, "4. Обґрунтування очікуваної вартості предмета закупівлі")
    add_body_p(
        doc,
        "Розрахунок очікуваної вартості предмета закупівлі здійснено уповноваженою особою відповідно до Примірної методики визначення "
        "очікуваної вартості предмета закупівлі, затвердженої наказом Міністерства розвитку економіки, торгівлі та сільського господарства України "
        "від 25.03.2020 № 275, на підставі аналізу цін (без ПДВ) реальних закупівель теплової енергії в системі Prozorro та діючих тарифів "
        "на теплову енергію у м. Миколаєві на 2026 рік."
    )
    add_body_p(
        doc,
        "Загальна очікувана вартість закупівлі обсягом 1 800 Гкал становить:\n"
        "ОВ = 1 800 Гкал × 5 486,1111 грн (без ПДВ) = 9 875 000,00 грн без ПДВ."
    )

    fin_rows = [
        ("Кількість товарів (плановий обсяг закупівлі за Лотом 1):", "1 800,00 гігакалорія (Гкал)"),
        ("Розрахункова ціна за одиницю товару (1 Гкал) без ПДВ:", "5 486,11 грн без ПДВ"),
        ("ОЧІКУВАНА ВАРТІСТЬ ПРЕДМЕТА ЗАКУПІВЛІ (БЕЗ ПДВ):", "9 875 000,00 грн без ПДВ")
    ]

    table_fin = doc.add_table(rows=len(fin_rows), cols=2)
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
        p0.paragraph_format.space_after = Pt(2)
        r0 = p0.add_run(clean_spaces(param))
        r0.font.name = "Times New Roman"
        r0.font.size = Pt(10)
        r0.font.color.rgb = RGBColor(0, 0, 0)

        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(2)
        p1.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r1 = p1.add_run(clean_spaces(val))
        r1.font.name = "Times New Roman"
        r1.font.size = Pt(10)
        r1.font.color.rgb = RGBColor(0, 0, 0)

        if i == len(fin_rows) - 1:
            r0.font.bold = True
            r1.font.bold = True
            r1.font.size = Pt(11)

    add_signature_block(doc)
    doc.save(output_path)
    print(f"Main Justification Document created: {output_path}")


# ==============================================================================
# ФАЙЛ 2: ДОДАТОК ДО ОБҐРУНТУВАННЯ
# (ВИРІВНЯНА НУМЕРАЦІЯ: 1, 2, 2.1, 2.2; БЕЗ ДЖЕРЕЛ ТА БЕЗ ПОРЯДКУ ОПРИЛЮДНЕННЯ)
# ==============================================================================
def create_separated_sections_doc(output_path):
    doc = setup_doc_bw()

    # Заголовок окремого документа
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(6)
    p_title.paragraph_format.space_after = Pt(4)
    p_title.paragraph_format.line_spacing = 1.15
    r_title = p_title.add_run(clean_spaces(
        "ДОДАТОК ДО ОБҐРУНТУВАННЯ ЗАКУПІВЛІ UA-2026-10-09-013480-a"
    ))
    r_title.font.name = "Times New Roman"
    r_title.font.size = Pt(13)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(0, 0, 0)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(12)
    p_sub.paragraph_format.line_spacing = 1.15
    r_sub = p_sub.add_run(clean_spaces(
        "(Нормативно-правове регулювання та аналіз закупівель у системі Prozorro за 2026 рік без ПДВ)"
    ))
    r_sub.font.name = "Times New Roman"
    r_sub.font.size = Pt(11)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(0, 0, 0)

    # ==================== РОЗДІЛ 1 ====================
    add_heading_1(doc, "1. Нормативно-правове регулювання закупівлі")
    add_body_p(
        doc,
        "Правові підстави проведення закупівлі регламентовано такими нормативно-правовими актами України:\n"
        "1. Законом України «Про публічні закупівлі» від 25.12.2015 № 922-VIII;\n"
        "2. Постановою Кабінету Міністрів України від 11.10.2016 № 710 «Про ефективне використання державних коштів» "
        "(пункт 4-1 якої зобов'язує замовника обґрунтувати технічні та якісні характеристики предмета закупівлі, розмір бюджетного "
        "призначення, очікувану вартість предмета закупівлі та оприлюднити обґрунтування на власному веб-сайті протягом 5 робочих днів "
        "з дня оприлюднення оголошення про проведення відкритих торгів);\n"
        "3. Постановою Кабінету Міністрів України від 12.10.2022 № 1178 «Про затвердження особливостей здійснення публічних закупівель "
        "товарів, робіт і послуг для замовників... на період дії правового режиму воєнного стану...» (в редакції від 29.09.2026);\n"
        "4. Законом України «Про теплопостачання» від 02.06.2005 № 2633-IV;\n"
        "5. Законом України «Про житлово-комунальні послуги» від 09.11.2017 № 2189-VIII;\n"
        "6. Законом України «Про комерційний облік теплової енергії та водопостачання» від 22.06.2017 № 2119-VIII;\n"
        "7. Правилами надання послуги з постачання теплової енергії, затвердженими постановою Кабінету Міністрів України від 21.08.2019 № 830;\n"
        "8. Постановою НКРЕКП від 27.12.2023 № 2598 «Про встановлення тарифів на виробництво теплової енергії ПРАТ “МИКОЛАЇВСЬКА ТЕЦ”» "
        "(у редакції постанови НКРЕКП від 09.09.2026 № 1491);\n"
        "9. Примірною методикою визначення очікуваної вартості предмета закупівлі, затвердженою наказом Міністерства розвитку економіки, "
        "торгівлі та сільського господарства України від 25.03.2020 № 275."
    )

    # ==================== РОЗДІЛ 2 (2.1 та 2.2) ====================
    add_heading_1(doc, "2. Аналіз цін постачальників та розрахунок очікуваної вартості предмета закупівлі (без ПДВ)")
    add_heading_2(doc, "2.1. Аналіз закупівель та укладених договорів у системі Prozorro за 2026 рік (без ПДВ):")
    add_body_p(
        doc,
        "У період січня–жовтня 2026 року проведено моніторинг реальних процедур закупівель теплової енергії (код ДК 021:2015: 09320000-8) "
        "в електронній системі публічних закупівель Prozorro серед бюджетних установ та організацій м. Миколаєва (постачальники — "
        "ОКП «Миколаївоблтеплоенерго», ЄДРПОУ 31319242, та ПрАТ «Миколаївська ТЕЦ», ЄДРПОУ 30083966). "
        "Для забезпечення повної співставності з оголошенням UA-2026-10-09-013480-a усі вартісні показники закупівель та ціни за одиницю (1 Гкал) "
        "наведено у таблиці без урахування податку на додану вартість (без ПДВ)."
    )

    table_bench = doc.add_table(rows=5, cols=6)
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
        "Постачальник теплової енергії", 
        "Ідентифікатор та посилання на закупівлю в Prozorro", 
        "Обсяг, Гкал", 
        "Сума закупівлі / Ціна за 1 Гкал (без ПДВ)"
    ]
    for idx, txt in enumerate(tb_headers):
        c = table_bench.rows[0].cells[idx]
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(clean_spaces(txt))
        r.font.name = "Times New Roman"
        r.font.size = Pt(8.5)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0, 0, 0)

    bench_data = [
        (
            "1",
            "Виконавчий комітет Миколаївської міської ради (ЄДРПОУ 04056612, м. Миколаїв)",
            "ОКП «Миколаївоблтеплоенерго» (ЄДРПОУ 31319242)",
            "UA-2026-01-23-012905-a",
            "https://prozorro.gov.ua/uk/tender/UA-2026-01-23-012905-a",
            "18,1959",
            "80 296,63 грн без ПДВ\n(4 412,90 грн/Гкал без ПДВ)"
        ),
        (
            "2",
            "Миколаївський фаховий коледж культури і мистецтв (м. Миколаїв, просп. Миру, 16)",
            "ПрАТ «Миколаївська ТЕЦ» (ЄДРПОУ 30083966)",
            "UA-2026-01-01-002211-a",
            "https://prozorro.gov.ua/uk/tender/UA-2026-01-01-002211-a",
            "190,0298",
            "1 068 058,33 грн без ПДВ\n(5 620,48 грн/Гкал без ПДВ)"
        ),
        (
            "3",
            "Управління Держспецзв’язку в Миколаївській області (м. Миколаїв)",
            "Теплопостачальне підприємство м. Миколаєва (договір № 2257)",
            "UA-2026-01-28-017047-a",
            "https://prozorro.gov.ua/uk/tender/UA-2026-01-28-017047-a",
            "За спец.",
            "534 794,38 грн без ПДВ (ОВ)\n257 930,33 грн без ПДВ (дог.)"
        ),
        (
            "4",
            "Головне управління Національної поліції в Миколаївській області (ЄДРПОУ 40108735)",
            "ОКП «Миколаївоблтеплоенерго» (ЄДРПОУ 31319242)",
            "UA-2026-10-12-014133-a",
            "https://prozorro.gov.ua/uk/tender/UA-2026-10-12-014133-a",
            "За спец.",
            "55 833,33 грн без ПДВ\n(очікувана вартість без ПДВ)"
        )
    ]

    for i, (num, cust, supp, tid, turl, vol, price_str) in enumerate(bench_data):
        row = table_bench.rows[i+1]
        vals = [num, cust, supp, tid, vol, price_str]
        for col_idx, val in enumerate(vals):
            c = row.cells[col_idx]
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.05
            
            if col_idx in [0, 4, 5]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT

            if col_idx == 3:
                r_id_txt = p.add_run(f"{clean_spaces(tid)}\n")
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

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    add_heading_2(doc, "2.2. Урахування регульованих тарифів та розрахунок очікуваної вартості (без ПДВ):")
    add_body_p(
        doc,
        "Оскільки ринок постачання теплової енергії перебуває у сфері державного та муніципального цінового регулювання, під час "
        "визначення очікуваної вартості предмета закупівлі без ПДВ враховано:\n"
        "— результати реальних закупівель теплової енергії у м. Миколаєві в системі Prozorro за 2026 рік у перерахунку без ПДВ "
        "(зокрема, за закупівлею Виконавчого комітету Миколаївської міської ради UA-2026-01-23-012905-a у ОКП «Миколаївоблтеплоенерго» "
        "ціна становить 4 412,90 грн/Гкал без ПДВ; за закупівлею UA-2026-01-01-002211-a у ПрАТ «Миколаївська ТЕЦ» з урахуванням теплоносія "
        "та транспортування — 5 620,48 грн/Гкал без ПДВ; за закупівлею ГУНП в Миколаївській області UA-2026-10-12-014133-a очікувана вартість "
        "становить 55 833,33 грн без ПДВ);\n"
        "— постанову НКРЕКП від 27.12.2023 № 2598 (із змінами згідно з постановою НКРЕКП від 09.09.2026 № 1491), якою встановлено "
        "базовий тариф на виробництво теплової енергії для потреб бюджетних установ на рівні 2 958,42 грн/Гкал без ПДВ (без урахування "
        "тарифів на транспортування та постачання теплової енергії розподільчими мережами);\n"
        "— економічно обґрунтовані розрахункові тарифи теплопостачальних підприємств м. Миколаєва для бюджетних установ на опалювальний сезон 2026 року."
    )

    add_body_p(
        doc,
        "Розрахункова ціна одиниці товару (1 Гкал теплової енергії з урахуванням виробництва, транспортування та постачання), застосована "
        "замовником для визначення очікуваної вартості закупівлі UA-2026-10-09-013480-a, становить 5 486,1111 грн/Гкал без ПДВ, "
        "що перебуває в межах фактичного діапазону цін реальних договорів у м. Миколаєві за 2026 рік без ПДВ (4 412,90 – 5 620,48 грн/Гкал без ПДВ). "
        "Загальна очікувана вартість закупівлі 1 800 Гкал становить: 1 800 Гкал × 5 486,1111 грн = 9 875 000,00 грн без ПДВ."
    )

    add_signature_block(doc)
    doc.save(output_path)
    print(f"Separated Sections Document created: {output_path}")


if __name__ == '__main__':
    for base_root in [r"C:\Projects\Тендерний помічник", r"C:\Projects\Проект 1"]:
        if os.path.exists(base_root):
            subj_folder = os.path.join(base_root, "Результат", "Теплова_енергія")
            os.makedirs(subj_folder, exist_ok=True)
            main_doc_path = os.path.join(subj_folder, "Обґрунтування_Теплова_енергія.docx")
            addon_doc_path = os.path.join(subj_folder, "Додаток_до_обґрунтування_Теплова_енергія.docx")
            create_main_justification_doc(main_doc_path)
            create_separated_sections_doc(addon_doc_path)

    input_addon = r"C:\Projects\Тендерний помічник\Вхідні дані\Додаток до обгрунтування.docx"
    create_separated_sections_doc(input_addon)
