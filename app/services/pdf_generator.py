from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import os
import tempfile
from datetime import datetime

class StrategyPdfGenerator:
    def __init__(self):
        # Landscape Mode
        self.width, self.height = landscape(A4)
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='TitleKV',
            parent=self.styles['Heading1'],
            fontSize=22,
            textColor=colors.HexColor('#0F172A'),
            alignment=TA_CENTER,
            spaceAfter=10
        ))
        self.styles.add(ParagraphStyle(
            name='SubtitleKV',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#64748B'),
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=10,
            spaceAfter=5,
            borderPadding=(0, 0, 5, 0),
            borderWidth=1,
            borderColor=colors.HexColor('#E2E8F0'),
            borderRadius=None
        ))
        self.styles.add(ParagraphStyle(
            name='NutritionText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#334155'),
            leading=12
        ))
        self.styles.add(ParagraphStyle(
            name='CellText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#1E293B'),
        ))
        self.styles.add(ParagraphStyle(
            name='CellTextBold',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#0F172A'),
            fontName='Helvetica-Bold'
        ))

    def _get_layout_params(self, row_count, has_nutrition):
        """
        Calculate layout parameters based on row count to try and fit on one page.
        A4 Landscape Height ~ 595 pts (21cm)
        Margins: 0.8cm * 2 ~ 45 pts
        Header: ~ 100 pts
        Footer/Nutrition: ~ 50 pts
        Available for Table: ~ 400 pts
        """
        # Default (Comfortable)
        params = {
            'font_size': 9,
            'padding': 8,
            'logo_height': 1.2 * cm,
            'header_space': 0.5 * cm,
            'title_size': 22,
            'subtitle_size': 12
        }

        # Compact (20-35 rows)
        if 20 <= row_count < 35:
            params.update({
                'font_size': 8,
                'padding': 4,
                'logo_height': 1.0 * cm,
                'header_space': 0.3 * cm,
                'title_size': 18,
                'subtitle_size': 10
            })
        # Ultra Compact (35+ rows)
        elif row_count >= 35:
            params.update({
                'font_size': 7,
                'padding': 2,
                'leading': 8, # tighter line height
                'logo_height': 0.8 * cm,
                'header_space': 0.2 * cm,
                'title_size': 16,
                'subtitle_size': 9
            })
            
        return params

    def generate_pdf(self, track_title, strategy_data, nutrition, user_name="Athlète"):
        """
        Generate a PDF Roadbook (Landscape - UTMB Style).
        Fits on single page via dynamic scaling.
        """
        
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        # Margins: 0.8cm default, reduce if needed
        points = strategy_data['points']
        row_count = len(points)
        has_nutrition = bool(nutrition)
        
        layout = self._get_layout_params(row_count, has_nutrition)
        
        margin = 0.5 * cm if row_count > 40 else 0.8 * cm
        
        doc = SimpleDocTemplate(
            path,
            pagesize=landscape(A4),
            rightMargin=margin,
            leftMargin=margin,
            topMargin=margin,
            bottomMargin=margin
        )

        elements = []

        # 1. Header with Logo
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "static/img/logo.png")
        
        if os.path.exists(logo_path):
            # Dynamic Logo Size
            logo = Image(logo_path, width=4*cm, height=layout['logo_height'])
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, layout['header_space']))

        # Update Styles for Title
        title_style = ParagraphStyle('DynTitle', parent=self.styles['TitleKV'], fontSize=layout['title_size'])
        subtitle_style = ParagraphStyle('DynSub', parent=self.styles['SubtitleKV'], fontSize=layout['subtitle_size'])

        elements.append(Paragraph(f"ROADBOOK: {track_title}", title_style))
        
        date_str = datetime.now().strftime("%d/%m/%Y")
        target_time = self._format_duration(strategy_data['strategy']['target_time'])
        
        elements.append(Paragraph(
            f"Athlète: {user_name} • Date: {date_str} • Objectif: {target_time}",
            subtitle_style
        ))
        
        # 3. Splits Table
        headers = [
            'Point', 
            'Altitude', 
            'Dist', 'Inter', 
            'D+', 'D-', 
            'Heure', 
            'Services'
        ]
        
        table_data = [headers]
        
        # Dynamic Cell Styles
        cell_style = ParagraphStyle(
            'DynCell', 
            parent=self.styles['Normal'], 
            fontSize=layout['font_size'],
            leading=layout.get('leading', 12)
        )
        cell_style_bold = ParagraphStyle(
            'DynCellBold', 
            parent=cell_style, 
            fontName='Helvetica-Bold'
        )
        
        # Rows
        for p in points:
            # Safely get segment stats
            seg_dist = p.get('segment_dist', 0)
            seg_dplus = p.get('segment_d_plus', 0)
            seg_dminus = p.get('segment_d_minus', 0)
            
            # Format numbers
            alt_str = f"{p.get('altitude', 0)}"
            dist_str = f"{p['km']}"
            seg_dist_str = f"{seg_dist}" if seg_dist > 0 else "-"
            seg_dplus_str = f"{seg_dplus}" if seg_dplus > 0 else "-"
            seg_dminus_str = f"{seg_dminus}" if seg_dminus > 0 else "-"
            time_passage = p.get('time_day', '-')
            
            # Name (Bold)
            name_para = Paragraph(f"<b>{p['name']}</b>", cell_style)
            
            # Services
            wp_type = p.get('type', 'ravito')
            type_map = {
                'water': '💧 Eau', 'food': '🍕 Ravito', 'base_vie': '🏠 Base Vie',
                'check_point': '🚩 Check', 'start': '🏁 Départ', 'finish': '🏁 Arrivée',
                'ravito': '🍕 Ravito'
            }
            note = type_map.get(wp_type, wp_type)
            note_para = Paragraph(note, cell_style)
            
            row = [
                name_para,
                Paragraph(alt_str, cell_style),
                Paragraph(dist_str, cell_style),
                Paragraph(seg_dist_str, cell_style),
                Paragraph(seg_dplus_str, cell_style),
                Paragraph(seg_dminus_str, cell_style),
                Paragraph(f"<b>{time_passage}</b>", cell_style_bold),
                note_para
            ]
            table_data.append(row)

        # Widths
        # Adjust widths slightly for compact mode? Keep simple for now.
        col_widths = [
            5*cm, 
            1.8*cm, 
            1.6*cm, 1.6*cm, 
            1.6*cm, 1.6*cm,
            2.5*cm, # Heure
            None # Services
        ]
        
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Table Styles
        padding = layout['padding']
        
        table_style = [
            # Header
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#FFFFFF')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), layout['font_size']),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,0), padding + 2),
            ('TOPPADDING', (0,0), (-1,0), padding + 2),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#047857')),
            
            # Formatting
            ('ALIGN', (1,0), (6,-1), 'CENTER'),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('ALIGN', (7,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            
            # Rows
            ('BOTTOMPADDING', (0,1), (-1,-1), padding),
            ('TOPPADDING', (0,1), (-1,-1), padding),
            ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ]
        
        t.setStyle(TableStyle(table_style))
        elements.append(t)
        
        # 4. Nutrition (Only if space allows ideally, but we'll add it)
        if nutrition:
            elements.append(Spacer(1, 0.5*cm))
            # Smaller nutrition text if compact
            nutri_style = ParagraphStyle('Nutri', parent=self.styles['NutritionText'], fontSize=layout['font_size'])
            
            elements.append(Paragraph("Stratégie Nutrition Globale", self.styles['SectionHeader']))
            
            nutri_data = [[Paragraph(nutrition.replace('\n', '<br/>'), nutri_style)]]
            nutri_table = Table(nutri_data, colWidths=['100%'])
            nutri_table.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(nutri_table)

        doc.build(elements)
        return path

    def _format_duration(self, minutes):
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h}h{m:02d}"
