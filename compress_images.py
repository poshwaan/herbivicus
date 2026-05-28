
import os
from pathlib import Path
from PIL import Image, ImageFile

# Allow loading of truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

IMAGES_DIR = Path(__file__).parent / "images"
QUALITY = 85          
EXTENSIONS = {".jpg", ".jpeg"}


def compress_image(path: Path) -> tuple[int, int]:
    """
    Compress a single JPEG in-place.
    Returns (original_size, new_size) in bytes.
    """
    original_size = path.stat().st_size

    img = Image.open(path)

    # Preserve EXIF data
    exif = img.info.get("exif", b"")

    # Convert to RGB if needed (e.g. RGBA, P mode won't save as JPEG)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    save_kwargs = {
        "format": "JPEG",
        "quality": QUALITY,
        "optimize": True,       # Huffman table optimisation
        "progressive": True,    # Progressive JPEG (also compresses slightly better)
    }
    if exif:
        save_kwargs["exif"] = exif

    img.save(path, **save_kwargs)

    new_size = path.stat().st_size
    return original_size, new_size


def main():
    jpg_files = [
        p for p in IMAGES_DIR.rglob("*")
        if p.suffix.lower() in EXTENSIONS and p.is_file()
    ]

    if not jpg_files:
        print("No JPEG files found.")
        return

    total_original = 0
    total_new = 0
    skipped = 0

    print(f"Found {len(jpg_files)} JPEG files. Compressing...\n")

    for path in sorted(jpg_files):
        try:
            original, new = compress_image(path)
            total_original += original
            total_new += new
            saving = original - new
            pct = (saving / original * 100) if original else 0
            relative = str(path.relative_to(IMAGES_DIR))
            print(f"  {relative:<55}  {original/1024:>7.1f} KB  →  {new/1024:>7.1f} KB  ({pct:+.1f}%)")
        except Exception as e:
            print(f"  SKIPPED {path.name}: {e}")
            skipped += 1

    total_saving = total_original - total_new
    total_pct = (total_saving / total_original * 100) if total_original else 0

    print(f"\n{'─'*80}")
    print(f"  Total original : {total_original / 1_048_576:.2f} MB")
    print(f"  Total new      : {total_new      / 1_048_576:.2f} MB")
    print(f"  Saved          : {total_saving   / 1_048_576:.2f} MB  ({total_pct:.1f}%)")
    if skipped:
        print(f"  Skipped        : {skipped} file(s)")


if __name__ == "__main__":
    main()
