from pathlib import Path
from PIL import Image
import io
import uuid

class ImageService:
    @staticmethod
    def process_image(
        file_content: bytes, 
        target_dir: Path, 
        filename_prefix: str = "",
        max_width: int = 1200, 
        max_height: int = 1200, 
        quality: int = 85,
        format: str = "JPEG"
    ) -> str:
        """
        Processes an image: resizes, optimizes, and saves it.
        Returns the simplified filename relative to the media directory structure.
        """
        try:
            img = Image.open(io.BytesIO(file_content))
            
            # Convert RGBA to RGB if saving as JPEG
            if format.upper() == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            # Resize if too large, maintaining aspect ratio
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Generate filename
            # Use UUID to ensure uniqueness and bust cache
            ext = format.lower()
            if ext == "jpeg": ext = "jpg"
            
            clean_prefix = "".join(c for c in filename_prefix if c.isalnum() or c in ('-','_'))[:30]
            new_filename = f"{clean_prefix}_{uuid.uuid4().hex[:8]}.{ext}"
            
            target_path = target_dir / new_filename
            
            # Save
            img.save(target_path, format=format, optimize=True, quality=quality)
            
            return new_filename
            
        except Exception as e:
            print(f"Image processing error: {e}")
            raise e

    @staticmethod
    def process_profile_picture(file_content: bytes, target_dir: Path, username: str) -> str:
        """
        Squared crop centered, max 500x500
        """
        img = Image.open(io.BytesIO(file_content))
        
        # Center Crop to Square
        width, height = img.size
        new_size = min(width, height)
        
        left = (width - new_size)/2
        top = (height - new_size)/2
        right = (width + new_size)/2
        bottom = (height + new_size)/2
        
        img = img.crop((left, top, right, bottom))
        
        # Resize to standard avatar size
        img.thumbnail((500, 500), Image.Resampling.LANCZOS)
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        new_filename = f"avatar_{username}_{uuid.uuid4().hex[:8]}.jpg"
        target_path = target_dir / new_filename
        
        img.save(target_path, "JPEG", optimize=True, quality=85)
        
        return new_filename
