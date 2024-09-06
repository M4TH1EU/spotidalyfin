import hashlib
from pathlib import Path

from PIL import Image
from PIL.Image import Resampling

from spotidalyfin import cfg

LIBRARY_MAX_SIZE = (1920, 1080)
PEOPLE_MAX_SIZE = (900, 900)
STUDIO_MAX_SIZE = (1066, 600)


class JellyfinCompression:
    def __init__(self):
        self.metadata_dir = cfg.get("jellyfin-metadata-dir")
        self.checksum_file = self.metadata_dir / ".image_checksums.txt"
        self.checksums = self.load_checksums()

    def calculate_checksum(self, file_path):
        hash_md5 = hashlib.md5()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def load_checksums(self):
        if not self.checksum_file.exists():
            return set()

        with self.checksum_file.open("r") as f:
            checksums = {line.strip() for line in f}
        return checksums

    def save_checksum(self, checksum):
        with self.checksum_file.open("a") as f:
            f.write(checksum + "\n")

    def process_image(self, file_path: Path, max_size: tuple[int, int]):
        current_checksum = self.calculate_checksum(file_path)

        if current_checksum in self.checksums:
            print(f"Skipping already processed image: {file_path}")
            return

        try:
            with Image.open(file_path) as img:
                if max_size:
                    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                        print(f"Resizing image: {file_path}")
                        img.thumbnail(max_size, Resampling.LANCZOS)

                print(f"Compressing image: {file_path}")
                img.save(file_path, quality=40, optimize=True)
                self.save_checksum(self.calculate_checksum(file_path))
        except Exception as e:
            print(f"Error processing image: {file_path}")
            print(e)

    def compress_images(self):
        library = self.metadata_dir / "library"
        people = self.metadata_dir / "People"
        studio = self.metadata_dir / "Studio"
        artists = self.metadata_dir / "artists"

        for directory in [library, people, studio, artists]:
            if directory == library:
                max_size = LIBRARY_MAX_SIZE
            elif directory == people:
                max_size = PEOPLE_MAX_SIZE
            elif directory == studio:
                max_size = STUDIO_MAX_SIZE
            else:
                max_size = None

            for file in directory.glob("**/*"):
                if file.is_file() and file.suffix in [".jpg", ".jpeg", ".png"]:
                    self.process_image(file, max_size)
