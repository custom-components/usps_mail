"""
A component that give you to info about incoming letters and packages from USPS.

This component is based of the work of @skalavala
https://skalavala.github.io/usps/

For more details about this component, please refer to the documentation at
https://github.com/custom-components/usps_mail
"""
import logging
import base64

from homeassistant.components.camera import Camera
from custom_components.usps_mail import USPS_MAIL_DATA

__version__ = '0.0.5'
_LOGGER = logging.getLogger(__name__)

CONF_FILE_PATH = 'file_path'
DEFAULT_NAME = 'USPS Mail Pictures'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Camera that works with local files."""
    camera = UspsMailCamera(hass, DEFAULT_NAME)
    add_devices([camera])


class UspsMailCamera(Camera):
    """Representation of a local file camera."""

    def __init__(self, hass, name):
        """Initialize USPS Mail Camera component."""
        super().__init__()
        self.is_streaming = False
        self.hass = hass
        self._name = name

    def camera_image(self):
        """Return image response."""
        total = self.hass.data[USPS_MAIL_DATA]['total']
        if self.hass.data[USPS_MAIL_DATA]['count'] == total - 1 or total == 0:
            self.hass.data[USPS_MAIL_DATA]['count'] = 0
        else:
            self.hass.data[USPS_MAIL_DATA]['count'] = self.hass.data[USPS_MAIL_DATA]['count'] + 1
        image = self.hass.data[USPS_MAIL_DATA]['images'][self.hass.data[USPS_MAIL_DATA]['count']]
        return base64.b64decode(image)

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
