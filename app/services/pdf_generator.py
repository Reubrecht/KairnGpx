from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import os
import tempfile
from datetime import datetime

class StrategyPdfGenerator:
    def __init__(self):
        self.width, self.height = A4
        self.styles = getSampleStyleSheet()
        self._create_custom_styles()

    def _create_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='TitleKV',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0F172A'),
            alignment=TA_CENTER,
            spaceAfter=20
        ))
        self.styles.add(ParagraphStyle(
            name='SubtitleKV',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#64748B'),
            alignment=TA_CENTER,
            spaceAfter=30
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#0F172A'),
            spaceBefore=15,
            spaceAfter=10,
            borderPadding=(0, 0, 5, 0),
            borderWidth=1,
            borderColor=colors.HexColor('#E2E8F0'),
            borderRadius=None
        ))
        self.styles.add(ParagraphStyle(
            name='NutritionText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#334155'),
            leading=14
        ))

    def generate_pdf(self, track_title, strategy_data, nutrition, user_name="Athlète"):
        """
        Generate a PDF Roadbook.
        strategy_data: Result from StrategyCalculator.calculate_splits
                       Contains 'points' (list) and 'strategy' (dict)
        """
        
        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        elements = []

        # 1. Header
        elements.append(Paragraph(f"ROADBOOK: {track_title}", self.styles['TitleKV']))
        
        date_str = datetime.now().strftime("%d/%m/%Y")
        target_time = self._format_duration(strategy_data['strategy']['target_time'])
        
        elements.append(Paragraph(
            f"Généré pour {user_name} • le {date_str} • Objectif {target_time}",
            self.styles['SubtitleKV']
        ))
        
        # 2. Key Stats (Table)
        # We need total dist and D+ which are in the last point usually
        points = strategy_data['points']
        total_km = points[-1]['km'] if points else 0
        total_dplus = points[-1]['d_plus_cumul'] if points else 0
        
        stats_data = [
            [f"{total_km} km", f"+{total_dplus} m", f"{target_time}"]
        ]
        
        stats_table = Table(stats_data, colWidths=[6*cm, 6*cm, 5*cm])
        stats_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 16),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#0F172A')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(stats_table)
        elements.append(Spacer(1, 1*cm))

        # 3. Splits Table
        elements.append(Paragraph("Détails & Passages", self.styles['SectionHeader']))
        
        # Table Header
        table_data = [['Lieu', 'Km', 'D+ Cumul', 'Temps Course', 'Heure']]
        
        # Rows
        for p in points:
            # Highlight heavy rows?
            row = [
                Paragraph(f"<b>{p['name']}</b>", self.styles['Normal']),
                f"{p['km']} km",
                f"+{p['d_plus_cumul']} m",
                p['time_race'],
                p['time_day']
            ]
            table_data.append(row)

        col_widths = [7*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
        t = Table(table_data, colWidths=col_widths)
        
        # Striped style
        table_style = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')), # Header bg
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'), # Numbers right aligned
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('TOPPADDING', (0,0), (-1,0), 8),
            # Rows
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('BOTTOMPADDING', (0,1), (-1,-1), 6),
            ('TOPPADDING', (0,1), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ]
        
        # Zebra striping
        for i in range(1, len(table_data)):
            if i % 2 == 0:
                table_style.append(('BACKGROUND', (0,i), (-1,i), colors.HexColor('#F8FAFC')))
            else:
                table_style.append(('BACKGROUND', (0,i), (-1,i), colors.white))
                
        t.setStyle(TableStyle(table_style))
        elements.append(t)
        elements.append(Spacer(1, 1*cm))

        # 4. Nutrition Strategy
        if nutrition:
            elements.append(Paragraph("Stratégie Nutrition", self.styles['SectionHeader']))
            elements.append(Paragraph(nutrition.replace('\n', '<br/>'), self.styles['NutritionText']))
            elements.append(Spacer(1, 1*cm))

        # 5. Footer / Branding
        # elements.append(Spacer(1, 2*cm))
        # elements.append(Paragraph("Kairn - Planifiez votre prochaine aventure", self.styles['SubtitleKV']))

        doc.build(elements)
        return path

    def _format_duration(self, minutes):
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h}h{m:02d}"
