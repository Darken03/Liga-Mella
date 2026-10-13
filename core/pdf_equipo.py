"""Generador PDF profesional de estadísticas por equipo (Liga Mella)."""
import os
from io import BytesIO
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER, landscape
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable,
)
from reportlab.lib.colors import HexColor

NAVY = HexColor('#0A1A3A')
GOLD = HexColor('#EAB308')
RED = HexColor('#C81E2E')
GRAY_BG = HexColor('#F4F5F7')
DARK = HexColor('#111827')
MUTED = HexColor('#6B7280')


def _foto_img(path, w=26, h=30):
    """Devuelve Image reportlab o None si no hay foto válida."""
    try:
        if path and os.path.exists(path):
            return Image(path, width=w, height=h)
    except Exception:
        pass
    return None


def _jugador_foto_path(jugador):
    try:
        if getattr(jugador, 'foto', None) and getattr(jugador.foto, 'path', None):
            p = jugador.foto.path
            if os.path.exists(p):
                return p
    except Exception:
        pass
    return None


def _pie(canvas, doc):
    canvas.saveState()
    pw, ph = landscape(LETTER)
    # franja inferior navy + línea dorada
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, pw, 32, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, 32, pw, 3, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica', 7.5)
    canvas.drawString(36, 18, 'LIGA MELLA  •  Reporte oficial de estadísticas')
    canvas.drawRightString(pw - 36, 18, f'Página {doc.page}')
    canvas.restoreState()


def _encabezado(canvas, doc):
    _pie(canvas, doc)
    pw, _ = landscape(LETTER)
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, doc.pagesize[1] - 46, pw, 46, fill=1, stroke=0)
    canvas.setFillColor(GOLD)
    canvas.rect(0, doc.pagesize[1] - 49, pw, 3, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 13)
    canvas.drawString(36, doc.pagesize[1] - 28, 'LIGA MELLA  •  ESTADÍSTICAS POR EQUIPO')
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(pw - 36, doc.pagesize[1] - 28, f'Generado {date.today():%d/%m/%Y}')
    canvas.restoreState()


def generar_pdf_equipo(equipo, torneo, lineas, pitcheo, linea_eq=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(LETTER),
        leftMargin=30, rightMargin=30, topMargin=62, bottomMargin=44,
        title=f'Estadisticas {equipo.nombre}',
        author='Liga Mella',
    )
    ss = getSampleStyleSheet()
    sTitle = ParagraphStyle('T', parent=ss['Heading1'], fontSize=20, leading=22,
                            textColor=NAVY, fontName='Helvetica-Bold')
    sSub = ParagraphStyle('S', parent=ss['Normal'], fontSize=9, leading=12,
                          textColor=MUTED, fontName='Helvetica')
    sH2 = ParagraphStyle('H2', parent=ss['Heading2'], fontSize=12, leading=14,
                         textColor=NAVY, fontName='Helvetica-Bold',
                         spaceBefore=14, spaceAfter=6,
                         borderPadding=(0, 0, 4, 0))
    sCell = ParagraphStyle('C', parent=ss['Normal'], fontSize=7.5, leading=9,
                           fontName='Helvetica', textColor=DARK)
    sCellB = ParagraphStyle('CB', parent=sCell, fontName='Helvetica-Bold')
    sCellC = ParagraphStyle('CC', parent=sCell, alignment=TA_CENTER)
    sCellCB = ParagraphStyle('CCB', parent=sCellB, alignment=TA_CENTER)
    sHead = ParagraphStyle('H', parent=ss['Normal'], fontSize=7, leading=8,
                           fontName='Helvetica-Bold', textColor=colors.white,
                           alignment=TA_CENTER)
    sInit = ParagraphStyle('I', parent=ss['Normal'], fontSize=10, leading=12,
                           fontName='Helvetica-Bold', textColor=colors.white,
                           alignment=TA_CENTER)
    story = []

    # ---------- Portada equipo ----------
    logo_path = None
    try:
        if getattr(equipo, 'logo', None) and getattr(equipo.logo, 'path', None):
            if os.path.exists(equipo.logo.path):
                logo_path = equipo.logo.path
    except Exception:
        logo_path = None
    if logo_path:
        logo = Image(logo_path, width=64, height=64)
    else:
        logo = Paragraph(f"<font color='#FFFFFF'><b>{(equipo.sigla or '?')[:3]}</b></font>", sInit)

    if linea_eq:
        record = f"{linea_eq.ganados}W - {linea_eq.perdidos}L   •   C.A {linea_eq.ca}   C.P {linea_eq.cp}   DIF {'+' if linea_eq.dif > 0 else ''}{linea_eq.dif}"
    else:
        record = f"{equipo.victorias}W - {equipo.derrotas}L (histórico)"

    info = [
        Paragraph(f"{equipo.nombre}", sTitle),
        Paragraph(f"{equipo.sigla}  •  {torneo.nombre} {torneo.temporada}  •  {record}  •  {len(lineas)} jugadores con actuación", sSub),
    ]
    # caja de color del equipo
    try:
        team_color = HexColor(equipo.color or '#0A1A3A')
    except Exception:
        team_color = NAVY
    head_tbl = Table([[logo, info]], colWidths=[76, 640])
    head_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#EFF3FA')),
        ('ROUNDEDCORNERS', [6, 6, 6, 6]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, -1), 4, team_color),
    ]))
    story.append(head_tbl)
    story.append(Spacer(1, 8))

    # ---------- Roster con fotos ----------
    story.append(Paragraph('ROSTER  •  FOTOS', sH2))
    story.append(HRFlowable(width='100%', thickness=2, color=GOLD, spaceAfter=6))
    ros_head = [Paragraph(f"<b>{c}</b>", sHead) for c in
                ['FOTO', '#', 'JUGADOR', 'POS', 'CAP']]
    ros_data = [ros_head]
    jugadores_orden = sorted(
        [l.jugador for l in lineas],
        key=lambda j: (0 if getattr(j, 'es_capitan', False) else 1, getattr(j, 'dorsal', 0)),
    )
    # si no hay actuaciones pero hay roster, mostrar roster igual
    if not jugadores_orden:
        try:
            jugadores_orden = list(equipo.jugadores.all().order_by('dorsal')[:25])
        except Exception:
            jugadores_orden = []
    # tabla en 2 columnas de bloques para ahorrar espacio: la partimos en filas de 2 jugadores
    for j in jugadores_orden:
        fp = _jugador_foto_path(j)
        foto = _foto_img(fp, w=24, h=28) or Paragraph(
            f"<font color='#0A1A3A'><b>{(j.nombre or '?')[:1]}</b></font>", sCellC)
        nombre = f"{j.nombre} {getattr(j, 'apellido', '') or ''}".strip()
        cap = '★' if getattr(j, 'es_capitan', False) else ''
        ros_data.append([
            foto,
            Paragraph(f"{getattr(j, 'dorsal', '-')}", sCellC),
            Paragraph(f"<b>{nombre}</b>", sCell),
            Paragraph(f"{getattr(j, 'posicion', '')}", sCellC),
            Paragraph(f"{cap}", sCellC),
        ])
    if len(ros_data) == 1:
        ros_data.append([Paragraph('Sin jugadores registrados.', sCell)] * 5)
    t_ros = Table(ros_data, colWidths=[44, 30, 220, 50, 40], repeatRows=1)
    t_ros.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D9DEE7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F7F9FC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    # Roster + destacados lado a lado
    dest_txt = _destacados_html(lineas)
    dest = Paragraph(dest_txt, ParagraphStyle(
        'D', parent=ss['Normal'], fontSize=8.5, leading=12, textColor=DARK))
    lado = Table([[t_ros, dest]], colWidths=[390, 322])
    lado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(lado)

    # ---------- Bateo ----------
    story.append(Paragraph(f"BATEO  •  {torneo.nombre} {torneo.temporada}", sH2))
    story.append(HRFlowable(width='100%', thickness=2, color=GOLD, spaceAfter=6))
    cols = ['#', 'JUGADOR', 'AB', 'R', 'H', '2B', '3B', 'HR', 'CI', 'BB', 'K', 'AVG', 'OBP', 'SLG', 'OPS']
    bat_head = [Paragraph(f"<b>{c}</b>", sHead) for c in cols]
    bat_data = [bat_head]
    for i, l in enumerate(lineas, 1):
        j = l.jugador
        nombre = f"{j.nombre} {getattr(j, 'apellido', '') or ''}".strip()
        bat_data.append([
            Paragraph(f"{i}", sCellC),
            Paragraph(f"<b>{nombre}</b> <font color='#6B7280'>#{getattr(j, 'dorsal', '-')} {getattr(j, 'posicion', '')}</font>", sCell),
            Paragraph(f"{l.ab}", sCellC),
            Paragraph(f"{l.r}", sCellC),
            Paragraph(f"{l.h}", sCellC),
            Paragraph(f"{l.h2}", sCellC),
            Paragraph(f"{l.h3}", sCellC),
            Paragraph(f"<b>{l.hr}</b>", sCellCB),
            Paragraph(f"<b>{l.rbi}</b>", sCellCB),
            Paragraph(f"{l.bb}", sCellC),
            Paragraph(f"{l.k}", sCellC),
            Paragraph(f"{l.avg:.3f}", sCellC),
            Paragraph(f"{l.obp:.3f}", sCellC),
            Paragraph(f"{l.slg:.3f}", sCellC),
            Paragraph(f"<b>{l.ops:.3f}</b>", sCellCB),
        ])
    # totales
    tot = _totales(lineas)
    bat_data.append([
        Paragraph('', sCellC),
        Paragraph('<b>TOTAL EQUIPO</b>', sCellB),
        Paragraph(f"<b>{tot['ab']}</b>", sCellCB),
        Paragraph(f"<b>{tot['r']}</b>", sCellCB),
        Paragraph(f"<b>{tot['h']}</b>", sCellCB),
        Paragraph(f"<b>{tot['h2']}</b>", sCellCB),
        Paragraph(f"<b>{tot['h3']}</b>", sCellCB),
        Paragraph(f"<b>{tot['hr']}</b>", sCellCB),
        Paragraph(f"<b>{tot['rbi']}</b>", sCellCB),
        Paragraph(f"<b>{tot['bb']}</b>", sCellCB),
        Paragraph(f"<b>{tot['k']}</b>", sCellCB),
        Paragraph(f"<b>{tot['avg']:.3f}</b>", sCellCB),
        Paragraph(f"<b>{tot['obp']:.3f}</b>", sCellCB),
        Paragraph(f"<b>{tot['slg']:.3f}</b>", sCellCB),
        Paragraph(f"<b>{tot['ops']:.3f}</b>", sCellCB),
    ])
    if len(bat_data) == 2:
        bat_data.insert(1, [Paragraph('Sin actuaciones de bateo en este torneo.', sCell)] + [Paragraph('', sCell)] * 14)
    t_bat = Table(bat_data, colWidths=[22, 150, 30, 26, 26, 26, 26, 30, 30, 28, 26, 44, 44, 44, 46], repeatRows=1)
    t_bat.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('BACKGROUND', (0, -1), (-1, -1), HexColor('#FEF3C7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#D9DEE7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, HexColor('#F7F9FC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_bat)
    story.append(Paragraph(
        'AVG = H ÷ AB  •  OBP incluye boletos/golpeados  •  OPS = OBP + SLG.',
        ParagraphStyle('N', parent=ss['Normal'], fontSize=7, textColor=MUTED)))
    story.append(Spacer(1, 4))

    # ---------- Pitcheo ----------
    story.append(Paragraph('PITCHEO', sH2))
    story.append(HRFlowable(width='100%', thickness=2, color=GOLD, spaceAfter=6))
    pcols = ['#', 'LANZADOR', 'JL', 'IP', 'K', 'BB', 'H', 'R', 'ER', 'ERA']
    pit_head = [Paragraph(f"<b>{c}</b>", sHead) for c in pcols]
    pit_data = [pit_head]
    for i, p in enumerate(pitcheo or [], 1):
        j = p.jugador
        nombre = f"{j.nombre} {getattr(j, 'apellido', '') or ''}".strip()
        pit_data.append([
            Paragraph(f"{i}", sCellC),
            Paragraph(f"<b>{nombre}</b> <font color='#6B7280'>#{getattr(j, 'dorsal', '-')}</font>", sCell),
            Paragraph(f"{p.jl}", sCellC),
            Paragraph(f"{p.ip}", sCellC),
            Paragraph(f"<b>{p.k}</b>", sCellCB),
            Paragraph(f"{p.bb}", sCellC),
            Paragraph(f"{p.h}", sCellC),
            Paragraph(f"{p.r}", sCellC),
            Paragraph(f"{p.er}", sCellC),
            Paragraph(f"{p.era:.2f}", sCellC),
        ])
    if len(pit_data) == 1:
        pit_data.append([Paragraph('Sin actuaciones de pitcheo en este torneo.', sCell)] + [Paragraph('', sCell)] * 9)
    t_pit = Table(pit_data, colWidths=[24, 220, 40, 50, 50, 50, 50, 50, 50, 60], repeatRows=1)
    t_pit.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#7F1D1D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#D9DEE7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#FEF2F2')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_pit)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        'Documento oficial generado por Liga Mella. Datos del torneo seleccionado. '
        'Fotos del roster incluidas cuando están disponibles.',
        ParagraphStyle('F', parent=ss['Normal'], fontSize=7, textColor=MUTED, alignment=TA_CENTER)))

    doc.build(story, onFirstPage=_encabezado, onLaterPages=_encabezado)
    return buf.getvalue()


def _totales(lineas):
    tot = {'ab': 0, 'r': 0, 'h': 0, 'h2': 0, 'h3': 0, 'hr': 0, 'rbi': 0,
           'bb': 0, 'hbp': 0, 'sf': 0, 'k': 0}
    for l in lineas:
        for k in tot:
            tot[k] += getattr(l, k, 0) or 0
    ab, h, bb, hbp, sf = tot['ab'], tot['h'], tot['bb'], tot['hbp'], tot['sf']
    h2, h3, hr = tot['h2'], tot['h3'], tot['hr']
    tb = (h - h2 - h3 - hr) + 2 * h2 + 3 * h3 + 4 * hr
    tot['avg'] = round(h / ab, 3) if ab else 0
    den = ab + bb + hbp + sf
    tot['obp'] = round((h + bb + hbp) / den, 3) if den else 0
    tot['slg'] = round(tb / ab, 3) if ab else 0
    tot['ops'] = round(tot['obp'] + tot['slg'], 3)
    return tot


def _destacados_html(lineas):
    if not lineas:
        return '<b>DESTACADOS</b><br/>Sin actuaciones en este torneo.'
    def _nm(l):
        j = l.jugador
        return f"{j.nombre} {getattr(j, 'apellido', '') or ''}".strip()
    cand_avg = [l for l in lineas if (l.ab or 0) >= 5]
    best_avg = max(cand_avg or lineas, key=lambda l: l.avg)
    best_hr = max(lineas, key=lambda l: l.hr)
    best_rbi = max(lineas, key=lambda l: l.rbi)
    best_ops = max(lineas, key=lambda l: l.ops)
    return (
        '<b><font color="#0A1A3A">★ DESTACADOS DEL EQUIPO</font></b><br/><br/>'
        f'• Mejor AVG: <b>{_nm(best_avg)}</b> — {best_avg.avg:.3f} ({best_avg.h}/{best_avg.ab})<br/>'
        f'• Más HR: <b>{_nm(best_hr)}</b> — {best_hr.hr} HR<br/>'
        f'• Más impulsadas: <b>{_nm(best_rbi)}</b> — {best_rbi.rbi} CI<br/>'
        f'• Mejor OPS: <b>{_nm(best_ops)}</b> — {best_ops.ops:.3f}<br/><br/>'
        '<font color="#6B7280">Corte AVG mínimo 5 AB. En empate, manda el orden de la tabla.</font>'
    )
