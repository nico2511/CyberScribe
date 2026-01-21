
import base64
from io import BytesIO
from PIL import Image, ImageDraw

def create_icon(color, filename):
    # Create a 64x64 image
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colors
    primary = "#4a4a4a" if color == 'gray' else "#b91c1c"
    secondary = "#d4d4d4"
    eye_color = "#00ff00" if color == 'gray' else "#fbbf24"
    outline = "black"

    # Head (Rounded Rectangle)
    draw.rounded_rectangle([10, 15, 54, 55], radius=8, fill=primary, outline=outline, width=2)
    
    # Visor / Eyes Area
    draw.rectangle([15, 25, 49, 35], fill="#1f2937", outline=outline, width=1)
    
    # Eyes (glowing horizontal bars)
    draw.rectangle([18, 28, 25, 32], fill=eye_color)
    draw.rectangle([39, 28, 46, 32], fill=eye_color)
    
    # Antenna
    draw.line([32, 15, 32, 5], fill=outline, width=2)
    draw.ellipse([28, 2, 36, 10], fill=eye_color, outline=outline)

    # Mouth / Grill
    for x in range(20, 45, 5):
        draw.line([x, 42, x, 50], fill="#1f2937", width=1)
    
    # Bolts
    draw.ellipse([12, 17, 16, 21], fill=secondary, outline=outline)
    draw.ellipse([48, 17, 52, 21], fill=secondary, outline=outline)
    draw.ellipse([12, 49, 16, 53], fill=secondary, outline=outline)
    draw.ellipse([48, 49, 52, 53], fill=secondary, outline=outline)

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    print(f"ICON_{filename.upper()} = \"{img_str}\"")

if __name__ == "__main__":
    create_icon('gray', 'gray')
    create_icon('red', 'red')
