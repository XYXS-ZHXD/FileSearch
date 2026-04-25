"""
Generate icon.ico from SVG design using Pillow.
Includes 16, 32, 48, 64, 128, 256 sizes.
"""
from PIL import Image, ImageDraw
import os

def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # 背景圆角矩形（蓝色）
    margin = int(s * 0.125)  # 32/256
    rr = int(s * 0.109)      # 28/256 圆角
    bg_color = (66, 133, 244, 255)  # #4285F4
    d.rounded_rectangle([margin, margin, s - margin, s - margin], radius=rr, fill=bg_color)

    # 文件夹主体（浅蓝白）
    folder_color = (232, 244, 255, 255)  # #E8F4FF
    fx1 = int(s * 0.25)     # 64/256
    fy1 = int(s * 0.328)    # 84/256
    fx2 = int(s * 0.75)     # 192/256
    fy2 = int(s * 0.703)    # 180/256
    fr  = int(s * 0.047)    # 12/256
    d.rounded_rectangle([fx1, fy1, fx2, fy2], radius=fr, fill=folder_color)

    # 文件夹标签（凸起的小矩形）
    tab_x1 = fx1
    tab_x2 = int(s * 0.4375)  # 112/256
    tab_y2 = fy1
    tab_y1 = int(s * 0.266)   # 68/256
    d.rounded_rectangle([tab_x1, tab_y1, tab_x2, tab_y2], radius=fr, fill=folder_color)

    # 搜索放大镜（白色）
    cx = int(s * 0.586)  # 150/256
    cy = int(s * 0.547)  # 140/256
    cr = int(s * 0.109)  # 28/256
    lw = max(2, int(s * 0.031))  # stroke-width 8/256

    # 圆圈
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr],
              outline=(255, 255, 255, 255), width=lw)

    # 把手
    hx1 = int(s * 0.664)  # 170/256
    hy1 = int(s * 0.625)  # 160/256
    hx2 = int(s * 0.742)  # 190/256
    hy2 = int(s * 0.703)  # 180/256
    d.line([hx1, hy1, hx2, hy2], fill=(255, 255, 255, 255), width=lw)

    return img


def make_ico(output_path):
    sizes = [16, 32, 48, 64, 128, 256]
    images = [draw_icon(s) for s in sizes]
    # Pillow ICO 保存：用最大图像 save，append_images 传其余尺寸
    images[-1].save(
        output_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1]
    )
    fsize = os.path.getsize(output_path)
    print(f"icon.ico generated: {output_path}")
    print(f"File size: {fsize:,} bytes ({len(sizes)} sizes: {sizes})")


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    make_ico(out)
