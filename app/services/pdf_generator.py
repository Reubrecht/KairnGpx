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

        # 1. Header
        elements.append(Paragraph(f"ROADBOOK: {track_title}", self.styles['TitleKV']))
        
        date_str = datetime.now().strftime("%d/%m/%Y")
        target_time = self._format_duration(strategy_data['strategy']['target_time'])
        
        elements.append(Paragraph(
            f"Athlète: {user_name} • Date: {date_str} • Objectif: {target_time}",
            self.styles['SubtitleKV']
        ))
        
        points = strategy_data['points']
        
        # 3. Splits Table - UTMB Columns
        # Point | Altitude (M) | Dist (km) | Dist. inter (km) | Déniv + (M) | Déniv - (M) | Plus rapide | Plus lent | Services
        
        headers = [
            'Point', 
            'Altitude (M)', 
            'Dist (km)', 'Dist. inter', 
            'Déniv +', 'Déniv -', 
            'Plus rapide', 'Plus lent', 
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
            
            fast_time = p.get('time_fast_tod', '-')
            slow_time = p.get('time_slow_tod', '-')
            
            # Style Name (Bold)
            name_para = Paragraph(f"<b>{p['name']}</b>", self.styles['CellText'])
            
            # Nutrition placeholder
            # If nutrition strategy contains keywords related to this point, we could maybe add?
            # For now, just a placeholder icon or empty space for writing
            note = ""
            
            row = [
                name_para,
                alt_str,
                dist_str, seg_dist_str,
                seg_dplus_str, seg_dminus_str,
                fast_time, slow_time,
                note
            ]
            table_data.append(row)

        # Widths: A4 Landscape width approx 29.7cm - margins (1.6cm) = 28.1cm
        # 9 Columns
        # Point: 5cm
        # Alt: 2cm
        # Dist/Int/D+/D-: 4 * 2cm = 8cm
        # Fast/Slow: 2 * 2.5cm = 5cm
        # Services: Remaining (approx 8cm)
        
        col_widths = [
            5*cm, 
            2.0*cm, 
            2.0*cm, 2.0*cm, 
            2.0*cm, 2.0*cm,
            2.5*cm, 2.5*cm,
            None # Auto fill rest
        ]
        
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # Styles
        table_style = [
            # Header
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')), 
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('BOTTOMPADDING', (0,0), (-1,0), 10),
            ('TOPPADDING', (0,0), (-1,0), 10),
            ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#CBD5E1')),
            
            # Data Alignment
            ('ALIGN', (1,0), (7,-1), 'CENTER'), # Numbers Center Aligned
            ('ALIGN', (0,0), (0,-1), 'LEFT'),  # Name Left
            ('ALIGN', (8,0), (-1,-1), 'LEFT'), # Services Left
            
            # General Rows
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 9),
            ('BOTTOMPADDING', (0,1), (-1,-1), 8),
            ('TOPPADDING', (0,1), (-1,-1), 8),
            # ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('LINEBELOW', (0,1), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            
            # Highlight Chrono Columns (Fast/Slow)
            # ('TEXTCOLOR', (6,1), (7,-1), colors.HexColor('#64748B')), 
        ]
        
        # Zebra striping (optional, UTMB is usually plain white with lines)
        # We will stick to lines as per UTMB screenshot usually being clean.
        
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
