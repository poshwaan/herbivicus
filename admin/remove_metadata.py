

import argparse
import sys
from pathlib import Path

from PIL import Image

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp"}


def strip_metadata(src_path: Path, dst_path: Path) -> None:
    """Re-save an image containing only pixel data, no metadata."""
    with Image.open(src_path) as img:
        # Convert palette/alpha modes safely and drop any info dict (EXIF, ICC, etc.)
        data = list(img.getdata())
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(data)

        save_kwargs = {}
        if src_path.suffix.lower() in (".jpg", ".jpeg"):
            save_kwargs["quality"] = 95
            save_kwargs["subsampling"] = 0

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        clean_img.save(dst_path, **save_kwargs)


def collect_images(paths, directory, recursive):
    files = [Path(p) for p in paths]

    if directory:
        d = Path(directory)
        pattern = "**/*" if recursive else "*"
        files.extend(
            p for p in d.glob(pattern)
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

    return files


def main():
    parser = argparse.ArgumentParser(description="Remove all metadata from images.")
    parser.add_argument("images", nargs="*", help="Image file paths")
    parser.add_argument("--dir", help="Process all images in this directory")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subfolders (use with --dir)")
    parser.add_argument("-o", "--output", help="Output path (only valid with a single input file)")
    parser.add_argument("--in-place", action="store_true", help="Overwrite original files instead of creating copies")
    args = parser.parse_args()

    files = collect_images(args.images, args.dir, args.recursive)

    if not files:
        print("No images found. Provide file paths or --dir.")
        sys.exit(1)

    if args.output and len(files) != 1:
        print("-o/--output can only be used with a single input file.")
        sys.exit(1)

    for src in files:
        if not src.exists():
            print(f"Skipping (not found): {src}")
            continue
        if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"Skipping (unsupported type): {src}")
            continue

        if args.in_place:
            dst = src
        elif args.output:
            dst = Path(args.output)
        else:
            dst = src.with_name(f"{src.stem}_clean{src.suffix}")

        try:
            strip_metadata(src, dst)
            print(f"Cleaned: {src} -> {dst}")
        except Exception as e:
            print(f"Error processing {src}: {e}")


if __name__ == "__main__":
    main()