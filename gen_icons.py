
import base64
from io import BytesIO
from PIL import Image, ImageDraw

def create_icon(color, filename):
    # Create a 256x256 image (High Res)
    size = 256
    scale = 4  # Scaling factor from original 64x64 design
    
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Colors
    primary = "#4a4a4a" if color == 'gray' else "#b91c1c"
    secondary = "#d4d4d4"
    eye_color = "#00ff00" if color == 'gray' else "#fbbf24"
    outline = "black"
    
    # Widths
    w_outline = 2 * scale
    w_detail = 1 * scale

    # Helper to scale coords
    def s(coords):
        return [c * scale for c in coords]

    # Head (Rounded Rectangle)
    # Original: [10, 15, 54, 55] -> Scaled
    draw.rounded_rectangle(s([10, 15, 54, 55]), radius=8*scale, fill=primary, outline=outline, width=w_outline)
    
    # Visor / Eyes Area
    # Original: [15, 25, 49, 35]
    draw.rectangle(s([15, 25, 49, 35]), fill="#1f2937", outline=outline, width=w_detail)
    
    # Eyes (glowing horizontal bars)
    # Original: [18, 28, 25, 32]
    draw.rectangle(s([18, 28, 25, 32]), fill=eye_color)
    # Original: [39, 28, 46, 32]
    draw.rectangle(s([39, 28, 46, 32]), fill=eye_color)
    
    # Antenna
    # Original: line [32, 15, 32, 5]
    draw.line(s([32, 15, 32, 5]), fill=outline, width=w_outline)
    # Original: ellipse [28, 2, 36, 10]
    draw.ellipse(s([28, 2, 36, 10]), fill=eye_color, outline=outline, width=w_detail)

    # Mouth / Grill
    # Original: x in range(20, 45, 5) -> lines [x, 42, x, 50]
    for x in range(20, 45, 5):
        draw.line([x*scale, 42*scale, x*scale, 50*scale], fill="#1f2937", width=w_detail)
    
    # Bolts
    bolts = [
        [12, 17, 16, 21],
        [48, 17, 52, 21],
        [12, 49, 16, 53],
        [48, 49, 52, 53]
    ]
    for b in bolts:
        draw.ellipse(s(b), fill=secondary, outline=outline, width=w_detail)

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    print(f"ICON_{filename.upper()} = \"{img_str}\"")
    
    # Save as ICO for the executable with multiple sizes
    if color == 'gray':
        # Create different sizes by resizing the master 256x256 image
        sizes = [256, 128, 64, 48, 32, 16]
        icon_images = []
        for sz in sizes:
            if sz == 256:
                icon_images.append(img)
            else:
                icon_images.append(img.resize((sz, sz), Image.Resampling.LANCZOS))
                
        # Save as ICO containing all sizes
        # The 'append_images' argument adds the other images to the first one
        img.save("app.ico", format="ICO", sizes=[(s,s) for s in sizes], append_images=icon_images[1:])
        print("Generated app.ico with sizes: " + str(sizes))

if __name__ == "__main__":
    create_icon('gray', 'gray')
    create_icon('red', 'red')
