import base64
import warnings
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from invoice_generator.domain.models import ValidationError


class LogoNormalizer:
    def normalize(self, content: bytes) -> str:
        if len(content) > 2_000_000:
            raise ValidationError("logo", "Choose a PNG or JPEG logo smaller than 2 MB.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if image.format not in ("PNG", "JPEG") or max(image.size) > 4000:
                        raise ValueError
                    image.load()
                    converted = image.convert("RGBA")
                    converted.thumbnail((800, 250))
                    output = BytesIO()
                    converted.save(output, format="PNG")
                    return base64.b64encode(output.getvalue()).decode()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as error:
            raise ValidationError(
                "logo", "Choose a readable PNG or JPEG up to 4000 pixels per side."
            ) from error
