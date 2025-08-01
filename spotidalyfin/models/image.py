from spotidalyfin.models.manager import Manager
from spotidalyfin.models.utils import get_as_base64


class Image:
    def __init__(self, image_url: str):
        self.image_url = image_url

    def get_image(self) -> bytes:
        return get_as_base64(self.image_url)


class ImageAuthenticated(Image):
    def __init__(self, image_url: str, manager: Manager):
        super().__init__(image_url)
        self.manager = manager

    def get_image(self) -> bytes:
        return self.manager.get_image(self.image_url)