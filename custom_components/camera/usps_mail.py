"""
A component that give you to info about incoming letters and packages from USPS.

This component is based of the work of @skalavala
https://skalavala.github.io/usps/

For more details about this component, please refer to the documentation at
https://github.com/custom-components/usps_mail
"""
import logging
import mimetypes
import os

from homeassistant.components.camera import Camera
from custom_components.usps_mail import USPS_MAIL_DATA

_LOGGER = logging.getLogger(__name__)

CONF_FILE_PATH = 'file_path'
DEFAULT_NAME = 'USPS Mail Pictures'

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Camera that works with local files."""
    file_path = hass.data[USPS_MAIL_DATA]['output_dir'] + 'USPS.gif'
    camera = UspsMailCamera(DEFAULT_NAME, file_path)
    add_devices([camera])


class UspsMailCamera(Camera):
    """Representation of a local file camera."""

    def __init__(self, name, file_path):
        """Initialize USPS Mail Camera component."""
        super().__init__()

        self._name = name
        self.check_file_path_access(file_path)
        self._file_path = file_path
        # Set content type of local file
        content, _ = mimetypes.guess_type(file_path)
        if content is not None:
            self.content_type = content

    def camera_image(self):
        """Return image response."""
        try:
            with open(self._file_path, 'rb') as file:
                return file.read()
        except FileNotFoundError:
            _LOGGER.warning("Could not read camera %s image from file: %s",
                            self._name, self._file_path)

    def check_file_path_access(self, file_path):
        """Check that filepath given is readable."""
        if not os.access(file_path, os.R_OK):
            _LOGGER.warning("Could not read camera %s image from file: %s",
                            self._name, file_path)

    def update_file_path(self, file_path):
        """Update the file_path."""
        self.check_file_path_access(file_path)
        self._file_path = file_path
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the camera state attributes."""
        return {
            'file_path': self._file_path,
        }
