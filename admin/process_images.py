import argparse
import sys
from pathlib import Path

from PIL import Image, ImageFile

# Allow loading of truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
COMPRESSION_THRESHOLD = 600 * 1024  # 600 KB in bytes
QUALITY = 85


def process_image(src_path: Path) -> tuple[int, int, str]:
    """
    Process an image: remove metadata, compress if needed, convert to JPG.
    Returns (original_size, new_size, status_message).
    """
    original_size = src_path.stat().st_size
    original_format = src_path.suffix.lower()

    # Open image and strip all metadata
    with Image.open(src_path) as img:
        # Convert to RGB if needed (handles RGBA, P mode, etc.)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Get pixel data only (no metadata)
        data = list(img.getdata())
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(data)

        # Determine if compression is needed
        needs_compression = original_size > COMPRESSION_THRESHOLD

        save_kwargs = {
            "format": "WEBP",
            "quality": QUALITY,
            "method": 6,  # 0-6: higher = better compression but slower
        }

        # Save as WebP to original location (replacing original)
        webp_path = src_path.with_suffix(".webp")
        clean_img.save(webp_path, **save_kwargs)

        # If original was not WebP, remove it
        if original_format != ".webp":
            src_path.unlink()

        new_size = webp_path.stat().st_size
        compression_status = "compressed" if needs_compression else "not compressed"

        return original_size, new_size, compression_status


def collect_images(paths, directory, recursive):
    """Collect image files from provided paths and/or directory."""
    files = [Path(p) for p in paths]

    if directory:
        d = Path(directory)
        pattern = "**/*" if recursive else "*"
        files.extend(
            p for p in d.glob(pattern)
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    # Remove duplicates
    return list(set(files))


def main():
    parser = argparse.ArgumentParser(
        description="Process images: remove metadata, compress if >600KB, convert to WebP."
    )
    parser.add_argument("images", nargs="*", help="Image file paths")
    parser.add_argument(
        "--dir", help="Process all images in this directory"
    )
    parser.add_argument(
        "--recursive", action="store_true", help="Recurse into subfolders (use with --dir)"
    )
    args = parser.parse_args()

    files = collect_images(args.images, args.dir, args.recursive)

    if not files:
        print("No images found. Provide file paths or --dir.")
        sys.exit(1)

    total_original = 0
    total_new = 0
    skipped = 0
    processed = 0

    print(f"Found {len(files)} image files. Processing...\n")

    for src in sorted(files):
        if not src.exists():
            print(f"  SKIPPED {src.name}: File not found")
            skipped += 1
            continue
        if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"  SKIPPED {src.name}: Unsupported format")
            skipped += 1
            continue

        try:
            original, new, compression_status = process_image(src)
            total_original += original
            total_new += new
            saving = original - new
            pct = (saving / original * 100) if original else 0
            jpg_path = src.with_suffix(".jpg")
            relative = str(jpg_path.relative_to(src.parent.parent))

            print(
                f"  {relative:<55}  {original/1024:>7.1f} KB  →  {new/1024:>7.1f} KB  "
                f"({pct:+.1f}%)  [{compression_status}]"
            )
            processed += 1
        except Exception as e:
            print(f"  ERROR {src.name}: {e}")
            skipped += 1

    total_saving = total_original - total_new
    total_pct = (total_saving / total_original * 100) if total_original else 0

    print(f"\n{'─'*100}")
    print(f"  Processed      : {processed} file(s)")
    print(f"  Total original : {total_original / 1_048_576:.2f} MB")
    print(f"  Total new      : {total_new / 1_048_576:.2f} MB")
    print(f"  Saved          : {total_saving / 1_048_576:.2f} MB  ({total_pct:.1f}%)")
    if skipped:
        print(f"  Skipped        : {skipped} file(s)")


if __name__ == "__main__":
    main()
