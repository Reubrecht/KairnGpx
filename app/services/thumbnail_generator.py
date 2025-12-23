
import os
import gpxpy
import gpxpy.gpx
import matplotlib.pyplot as plt
import contextily as ctx
import xyzservices.providers as xyz
from pathlib import Path
import io
from PIL import Image

class ThumbnailGenerator:
    def __init__(self, output_dir: str = "app/media/thumbnails"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        # Choose a provider. Esri World Imagery is good for satellite/photo feel.
        # OpenStreetMap.Mapnik is standard map.
        # CartoDB.Positron is clean.
        # User asked for "miniature photo", implying satellite or realistic terrain look.
        # Let's try Esri World Imagery.
        self.provider = xyz.Esri.WorldImagery

    def generate_thumbnail(self, gpx_file_path: str, track_id: int) -> str:
        """
        Generates a static map thumbnail for a given GPX file.
        Returns the relative path to the generated image.
        """
        try:
            with open(gpx_file_path, 'r', encoding='utf-8') as f:
                gpx = gpxpy.parse(f)

            # Extract points
            points = []
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        points.append((point.latitude, point.longitude))
            
            if not points:
                # Try routes if no tracks
                for route in gpx.routes:
                    for point in route.points:
                        points.append((point.latitude, point.longitude))
            
            if not points:
                return None

            # Unzip points
            lats, lons = zip(*points)

            # Plotting
            # Use strict margins to avoid excessive whitespace
            fig, ax = plt.subplots(figsize=(8, 5))
            
            # Plot track line
            # WebMercator projection is needed for contextily
            # contextily.add_basemap reprojects automatically if crs is set, 
            # but simpler usage is to stick to lat/lon and let it handle or convert manually.
            # Actually, standard plot is lat/lon. add_basemap expects WebMercator (EPSG:3857) by default
            # BUT we can pass crs=4326 to add_basemap to tell it our data is in lat/lon.
            
            ax.plot(lons, lats, color='#ea580c', linewidth=3, alpha=0.9) # Brand Orange/Red
            
            # Add basemap
            try:
                ctx.add_basemap(ax, crs='EPSG:4326', source=self.provider, attribution=False)
            except Exception as e:
                print(f"Failed to download basemap tile: {e}")
                # Fallback to just line if tiles fail (e.g. no internet)
            
            # Remove axes
            ax.set_axis_off()
            
            # Tight layout
            plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
            plt.margins(0,0)
            
            # Save to buffer first to crop or optimize
            buf = io.BytesIO()
            plt.savefig(buf, format='jpeg', bbox_inches='tight', pad_inches=0, dpi=150)
            buf.seek(0)
            plt.close(fig) # cleanup
            
            # Pillow Optimization
            img = Image.open(buf)
            filename = f"thumb_{track_id}.jpg"
            output_path = os.path.join(self.output_dir, filename)
            
            # Convert to RGB if needed (JPEG doesn't support alpha)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            img.save(output_path, "JPEG", quality=85, optimize=True)
            
            # Return relative path for DB
            return f"/media/thumbnails/{filename}"

        except Exception as e:
            print(f"Thumbnail generation error for {gpx_file_path}: {e}")
            import traceback
            traceback.print_exc()
            return None
