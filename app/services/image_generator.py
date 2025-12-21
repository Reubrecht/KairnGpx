from PIL import Image, ImageDraw, ImageFont
import os
from typing import Dict, Any, List

class StrategyImageGenerator:
    def __init__(self):
        # Configuration
        self.width = 1200
        # Height will be dynamic based on points
        self.margin = 50
        self.row_height = 80
        self.header_height = 160
        self.footer_height = 80
        
        # Colors
        self.color_bg = (255, 255, 255)
        self.color_text = (30, 41, 59) # Slate 800
        self.color_accent = (234, 88, 12) # Brand Orange/Red
        self.color_line = (226, 232, 240) # Slate 200
        self.color_header_bg = (248, 250, 252) # Slate 50
        
        # Fonts
        # Try to load Arial or similar
        try:
            self.font_title = ImageFont.truetype("arial.ttf", 48)
            self.font_header = ImageFont.truetype("arialbd.ttf", 28)
            self.font_cell = ImageFont.truetype("arial.ttf", 28)
            self.font_small = ImageFont.truetype("arial.ttf", 20)
        except:
            self.font_title = ImageFont.load_default()
            self.font_header = ImageFont.load_default()
            self.font_cell = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def generate_roadbook(self, strategy_data: Dict[str, Any], track_title: str) -> str:
        """
        Generate a PNG roadbook and return the file path.
        """
        points = strategy_data.get("points", [])
        strategy_info = strategy_data.get("strategy", {})
        
        # Calculate Height
        content_height = (len(points) + 1) * self.row_height # +1 for header row
        total_height = self.header_height + content_height + self.footer_height
        
        # Create Image
        img = Image.new('RGB', (self.width, total_height), self.color_bg)
        draw = ImageDraw.Draw(img)
        
        # --- HEADER ---
        # Title
        draw.text((self.margin, 50), f"Roadbook: {track_title}", font=self.font_title, fill=self.color_text)
        
        # Subtitle (Target Time)
        target = strategy_info.get("target_time", 0)
        h = target // 60
        m = target % 60
        subtitle = f"Objectif: {h}h{m:02d} | Fatigue Factor: {int(strategy_info.get('fatigue_factor', 0)*100)}%"
        draw.text((self.margin, 110), subtitle, font=self.font_cell, fill=self.color_accent)
        
        # --- TABLE HEADER ---
        y_start = self.header_height
        columns = ["Lieu", "Km", "D+ Cumul", "Temps Course", "Heure"]
        col_x = [self.margin, 500, 650, 850, 1050]
        
        # Draw Header Row Background
        draw.rectangle([self.margin, y_start, self.width - self.margin, y_start + self.row_height], fill=self.color_header_bg)
        
        for i, col in enumerate(columns):
            draw.text((col_x[i], y_start + 25), col, font=self.font_header, fill=self.color_text)
            
        y_curr = y_start + self.row_height
        
        # --- TABLE ROWS ---
        for p in points:
            # Separator Line
            draw.line([self.margin, y_curr, self.width - self.margin, y_curr], fill=self.color_line, width=1)
            
            # Content
            # Name
            draw.text((col_x[0], y_curr + 25), str(p['name'])[:25], font=self.font_cell, fill=self.color_text)
            
            # Km
            draw.text((col_x[1], y_curr + 25), f"{p['km']} km", font=self.font_cell, fill=self.color_text)
            
            # D+
            draw.text((col_x[2], y_curr + 25), f"{p['d_plus_cumul']} m+", font=self.font_cell, fill=self.color_text)
            
            # Time Race
            draw.text((col_x[3], y_curr + 25), p['time_race'], font=self.font_cell, fill=self.color_accent)
            
            # Time Day
            draw.text((col_x[4], y_curr + 25), p['time_day'], font=self.font_cell, fill=self.color_text)
            
            y_curr += self.row_height
            
        # Lines bottom
        draw.line([self.margin, y_curr, self.width - self.margin, y_curr], fill=self.color_line, width=2)
            
        # --- FOOTER ---
        footer_y = total_height - 60
        draw.text((self.margin, footer_y), "Généré par Kairn", font=self.font_text if hasattr(self, 'font_text') else self.font_small, fill=(150, 150, 150))
        
        # Save
        filename = f"roadbook_temp.png"
        output_dir = "app/media/generated"
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, filename)
        
        img.save(file_path)
        return file_path
