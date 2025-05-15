import os

from PIL import Image


def convert_png_to_ico(png_path, ico_path):
    """Convert PNG to ICO format"""
    try:
        img = Image.open(png_path)
        img.save(
            ico_path,
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        print(f"Successfully converted {png_path} to {ico_path}")
    except Exception as e:
        print(f"Error converting icon: {e}")


if __name__ == "__main__":
    # Get the static directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_dir = os.path.join(base_dir, "static")

    # Paths for PNG and ICO files
    png_path = os.path.join(static_dir, "qi_512.png")
    ico_path = os.path.join(static_dir, "qi.ico")

    convert_png_to_ico(png_path, ico_path)
