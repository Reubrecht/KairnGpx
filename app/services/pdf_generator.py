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

    def generate_pdf(self, track_title, strategy_data, nutrition, user_name="Athlète"):
        """
        Generate a PDF Roadbook (Landscape - UTMB Style).
        """
        
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        # Margins: 1cm for max space
        margin = 0.8 * cm
        
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
        # Logo path: We assume app/static/img/logo.png relative to this service file or app root
        # Services is in app/services, so up one level to app, then static/img/logo.png
        # Using abspath to be safe
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "static/img/logo.png")
        
        if os.path.exists(logo_path):
            # Scale logo to reasonable size (e.g. 5cm wide, preserve aspect ratio if possible, 
            # but Image flowable needs width/height)
            # We'll just set a fixed width of 4cm
            logo = Image(logo_path, width=4*cm, height=1.2*cm)
            logo.hAlign = 'CENTER'
            elements.append(logo)
            elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph(f"ROADBOOK: {track_title}", self.styles['TitleKV']))
        
        date_str = datetime.now().strftime("%d/%m/%Y")
        target_time = self._format_duration(strategy_data['strategy']['target_time'])
        
        elements.append(Paragraph(
            f"Athlète: {user_name} • Date: {date_str} • Objectif: {target_time}",
            self.styles['SubtitleKV']
        ))
        
        points = strategy_data['points']
        
        # 3. Splits Table
        # Columns: Point | Altitude | Dist (km) | Dist. inter | D+ | D- | H. Passage | Services
        
        headers = [
            'Point', 
            'Altitude (M)', 
            'Dist (km)', 'Dist. inter', 
            'Déniv +', 'Déniv -', 
            'Heure de passage', 
            'Services'
        ]
        
        table_data = [headers]
        
        # Rows
        for p in points:
            # Safely get segment stats (start point has 0/None)
            seg_dist = p.get('segment_dist', 0)
            seg_dplus = p.get('segment_d_plus', 0)
            seg_dminus = p.get('segment_d_minus', 0)
            
            # Format numbers
            alt_str = f"{p.get('altitude', 0)}"
            dist_str = f"{p['km']}"
            seg_dist_str = f"{seg_dist}" if seg_dist > 0 else "-"
            
            seg_dplus_str = f"{seg_dplus}" if seg_dplus > 0 else "-"
            seg_dminus_str = f"{seg_dminus}" if seg_dminus > 0 else "-"
            
            # Use scientifically most probable time (time_day)
            time_passage = p.get('time_day', '-')
            
            # Style Name (Bold)
            name_para = Paragraph(f"<b>{p['name']}</b>", self.styles['CellText'])
            
            # Services / Type mapping
            wp_type = p.get('type', 'ravito')
            type_map = {
                'water': '💧 Eau',
                'food': '🍕 Ravito',
                'base_vie': '🏠 Base Vie',
                'check_point': '🚩 Checkpoint',
                'start': '🏁 Départ',
                'finish': '🏁 Arrivée',
                'ravito': '🍕 Ravito'
            }
            note = type_map.get(wp_type, wp_type)
            
            row = [
                name_para,
                alt_str,
                dist_str, seg_dist_str,
                seg_dplus_str, seg_dminus_str,
                time_passage,
                note
            ]
            table_data.append(row)

        # Widths: A4 Landscape width approx 29.7cm - margins (1.6cm) = 28.1cm
        # 8 Columns (removed fast/slow, added single time)
        # Point: 5cm
        # Alt: 2cm
        # Dist/Int/D+/D-: 4 * 2cm = 8cm
        # Time: 3cm
        # Services: Remaining (approx 10cm)
        
        col_widths = [
            5*cm, 
            2.0*cm, 
            2.0*cm, 2.0*cm, 
            2.0*cm, 2.0*cm,
            3.0*cm, # Heure de passage
            None # Auto fill rest
        ]
        
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Styles
        table_style = [
            # Header
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#059669')), # Kairn Green
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#FFFFFF')), # White Text
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('TOPPADDING', (0,0), (-1,0), 10),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#047857')),
            
            # Data Alignment
            ('ALIGN', (1,0), (6,-1), 'CENTER'), # Numbers Center Aligned (Cols 1-6)
            ('ALIGN', (0,0), (0,-1), 'LEFT'),  # Name Left
            ('ALIGN', (7,0), (-1,-1), 'LEFT'), # Services Left
            
            # General Rows
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 9),
            ('BOTTOMPADDING', (0,1), (-1,-1), 8),
            ('TOPPADDING', (0,1), (-1,-1), 8),
            # ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            
            # Highlight Chrono Column (Heure de passage)
            ('FONTNAME', (6,1), (6,-1), 'Helvetica-Bold'), 
        ]
        
        t.setStyle(TableStyle(table_style))
        elements.append(t)
        
        # 4. Global Nutrition Strategy (Footer area)
        if nutrition:
            elements.append(Spacer(1, 1*cm))
            elements.append(Paragraph("Stratégie Nutrition Globale & Notes", self.styles['SectionHeader']))
            
            # Create a bordered box for nutrition
            nutri_data = [[Paragraph(nutrition.replace('\n', '<br/>'), self.styles['NutritionText'])]]
            nutri_table = Table(nutri_data, colWidths=['100%'])
            nutri_table.setStyle(TableStyle([
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ]))
            elements.append(nutri_table)

        doc.build(elements)
        return path

    def _format_duration(self, minutes):
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h}h{m:02d}"
