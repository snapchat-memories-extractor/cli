from pathlib import Path
from PIL import Image
from src.config import Config
from src.overlay.scan_overlay_pairs import OverlayPair


class ImageComposer:
    def __init__(self, pair: OverlayPair, output_path: Path) -> None:
        self.main_path = pair.main_path
        self.overlay_path = pair.overlay_path
        self.output_path = output_path

    def apply_overlay(self) -> None:
        with Image.open(self.main_path) as base_image:
            exif_bytes = base_image.info.get("exif")
            base_image = self._ensure_rgba(base_image)

            with Image.open(self.overlay_path) as overlay_image:
                overlay_image = self._ensure_rgba(overlay_image)
                # In some cases the overlay image is mismatched by 1 pixel
                overlay_image = self._resize_to_match(overlay_image, base_image.size)
                combined_image = Image.alpha_composite(base_image, overlay_image)

        combined_rgb_image = combined_image.convert("RGB")

        quality = Config.cli_options["jpeg_quality"]
        save_kwargs = {"format": "JPEG", "quality": quality}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes

        combined_rgb_image.save(str(self.output_path), **save_kwargs)

    @staticmethod
    def _ensure_rgba(image: Image.Image) -> Image.Image:
        if image.mode != "RGBA":
            return image.convert("RGBA")
        return image

    @staticmethod
    def _resize_to_match(
        image: Image.Image,
        target_size: tuple[int, int],
    ) -> Image.Image:
        if image.size != target_size:
            return image.resize(target_size, Image.Resampling.LANCZOS)
        return image