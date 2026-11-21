
import base64
from io import BytesIO
from PIL import Image, ImageDraw

VARIANTS = {
    "gray": {"head": "#4a4a4a", "eyes": "#00ff00", "filename": "gray"},
    "red": {"head": "#b91c1c", "eyes": "#fbbf24", "filename": "red"},
    "cyan": {"head": "#4a4a4a", "eyes": "#00f2ff", "filename": "cyan"},
    "loading": {"head": "#4a4a4a", "eyes": "#1f2937", "filename": "loading"},
}


def create_icon(head_color: str, eye_color: str, filename: str, *, write_ico: bool = False):
  # Create a 256x256 image (High Res)
    size = 256
    scale = 4  # Scaling factor from original 64x64 design

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    primary = head_color
    secondary = "#d4d4d4"
    eye_color = eye_color
    outline = "black"

    w_outline = 2 * scale
    w_detail = 1 * scale

    def s(coords):
        return [c * scale for c in coords]

    draw.rounded_rectangle(s([10, 15, 54, 55]), radius=8 * scale, fill=primary, outline=outline, width=w_outline)
    draw.rectangle(s([15, 25, 49, 35]), fill="#1f2937", outline=outline, width=w_detail)
    draw.rectangle(s([18, 28, 25, 32]), fill=eye_color)
    draw.rectangle(s([39, 28, 46, 32]), fill=eye_color)
    draw.line(s([32, 15, 32, 5]), fill=outline, width=w_outline)
    draw.ellipse(s([28, 2, 36, 10]), fill=eye_color, outline=outline, width=w_detail)

    for x in range(20, 45, 5):
        draw.line([x * scale, 42 * scale, x * scale, 50 * scale], fill="#1f2937", width=w_detail)

    bolts = [
        [12, 17, 16, 21],
        [48, 17, 52, 21],
        [12, 49, 16, 53],
        [48, 49, 52, 53],
    ]
    for b in bolts:
        draw.ellipse(s(b), fill=secondary, outline=outline, width=w_detail)

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    print(f'ICON_{filename.upper()}_B64 = "{img_str}"')

    if write_ico:
        sizes = [256, 128, 64, 48, 32, 16]
        icon_images = []
        for sz in sizes:
            if sz == 256:
                icon_images.append(img)
            else:
                icon_images.append(img.resize((sz, sz), Image.Resampling.LANCZOS))
        img.save("app.ico", format="ICO", sizes=[(s, s) for s in sizes], append_images=icon_images[1:])
        print("Generated app.ico with sizes: " + str(sizes))


if __name__ == "__main__":
    for key, spec in VARIANTS.items():
        create_icon(spec["head"], spec["eyes"], spec["filename"], write_ico=(key == "gray"))