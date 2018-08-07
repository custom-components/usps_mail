"""
A component that give you to info about incoming letters and packages from USPS.

This component is based of the work of @skalavala
https://skalavala.github.io/usps/

For more details about this component, please refer to the documentation at
https://github.com/custom-components/usps_mail
"""
import base64
import datetime
import email
import imaplib
import logging
import os
import sys
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.event import track_time_interval

__version__ = '0.0.2'
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'usps_mail'
USPS_MAIL_DATA = DOMAIN + '_data'
CONF_PROVIDER = 'provider'
CONF_INBOXFOLDER = 'inbox_folder'

INTERVAL = datetime.timedelta(hours=1)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PROVIDER): cv.string,
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_INBOXFOLDER, default='Inbox'): cv.string,
        vol.Optional(CONF_PORT, default='993'): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

CAMERA_URL = 'https://raw.githubusercontent.com/custom-components/usps_mail/dev/custom_components/camera/usps_mail.py'

def setup(hass, config):
    """Set up this component."""
    _LOGGER.info('version %s is starting, if you have ANY issues with this, please report'
                 ' them here: https://github.com/custom-components/usps_mail', __version__)
    mailserver = get_mailserver(config[DOMAIN][CONF_PROVIDER])
    port = config[DOMAIN][CONF_PORT]
    inbox_folder = config[DOMAIN][CONF_INBOXFOLDER]
    username = config[DOMAIN][CONF_EMAIL]
    password = config[DOMAIN][CONF_PASSWORD]
    usps_mail = UspsMail(hass, mailserver, port, inbox_folder, username, password)

    camera_dir = str(hass.config.path("custom_components/camera/"))
    camera_file = 'usps_mail.py'
    camera_full_path = camera_dir + camera_file
    if not os.path.isfile(camera_full_path):
        get_camera(camera_file, camera_dir)
    load_platform(hass, 'camera', DOMAIN)
    def scan_mail_service(call):
        """Set up service for manual trigger."""
        usps_mail.scan_mail(call)
    track_time_interval(hass, usps_mail.scan_mail, INTERVAL)
    hass.services.register(DOMAIN, 'scan_mail', scan_mail_service)
    return True


class UspsMail:
    """The class for this component"""
    def __init__(self, hass, mailserver, port, inbox_folder, username, password):
        self.hass = hass
        self.packages = None
        self.letters = None
        self._mailserver = mailserver
        self._port = port
        self._inbox_folder = inbox_folder
        self._username = username
        self._password = password
        self.hass.data[USPS_MAIL_DATA] = {}
        self.hass.data[USPS_MAIL_DATA]['images'] = []
        self.scan_mail('now')

    def scan_mail(self, call):
        """Main logic of the component"""
        try:
            account = self.login()
            select_folder(account, self._inbox_folder)
        except Exception as exx:
            _LOGGER.debug("Error connecting logging into email server.")
            _LOGGER.debug(str(exx))
            sys.exit(1)

        mail_count = self.get_mails(account)
        package_count = self.package_count(account)

        self.hass.data[USPS_MAIL_DATA]['mailattr'] = {'icon': 'mdi:email-outline', 'friendly_name': 'USPS Mail'}
        self.hass.data[USPS_MAIL_DATA]['packageattr'] = {'icon': 'mdi:package-variant', 'friendly_name': 'USPS Packages'}
        self.hass.states.set('sensor.usps_letters', mail_count, self.hass.data[USPS_MAIL_DATA]['mailattr'])
        self.hass.states.set('sensor.usps_packages', package_count, self.hass.data[USPS_MAIL_DATA]['packageattr'])


    def get_mails(self, account):
        """Get mail count from mail"""
        today = get_formatted_date()
        #today = '29-Jul-2018'
        _LOGGER.debug('Searching for mails from %s', today)
        image_count = 0
        rv, data = account.search(None, '(SUBJECT "Informed Delivery Daily Digest" SINCE "' + today + '")')
        if rv == 'OK':
            for num in data[0].split():
                rv, data = account.fetch(num, '(RFC822)')
                msg = email.message_from_string(data[0][1].decode('utf-8'))
                for part in msg.walk():
                    if part.get_content_maintype() == "multipart":
                        continue
                    if part.get('Content-Disposition') is None:
                        continue
                    self.hass.data[USPS_MAIL_DATA]['images'].append(base64.b64encode(part.get_payload(decode=True)))
                    image_count = image_count + 1
                _LOGGER.debug("Found %s mails and images in your email.", image_count)
        if image_count == 0:
            _LOGGER.debug("Found %s mails", image_count)
            self.hass.data[USPS_MAIL_DATA]['feed'].append(default_image())
        return image_count

    def package_count(self, account):
        """Get the package count"""
        count = 0
        today = get_formatted_date()
        rv, data = account.search(None, '(FROM "auto-reply@usps.com" SUBJECT "Item Delivered" SINCE "' + today + '")')
        if rv == 'OK':
            count = len(data[0].split())
        _LOGGER.debug("Found %s packages", count)
        return count

    def login(self):
        """function used to login"""
        _LOGGER.debug("trying to make connection with %s %s", self._mailserver, self._port)
        account = imaplib.IMAP4_SSL(self._mailserver, self._port)
        try:
            account.login(self._username, self._password)
            _LOGGER.debug("Logged into your email server successfully!")
        except imaplib.IMAP4.error:
            _LOGGER.critical('Failed to authenticate using the given credentials. Check your username, password, host and port.')
            sys.exit(1)
        return account

def get_mailserver(provider):
    """Returns the correct hostname for specified provider"""
    if provider == 'gmail':
        mailserver = 'imap.gmail.com'
    elif provider == 'yahoo': # Is there ANYONE still using this? :O
        mailserver = 'imap.mail.yahoo.com'
    elif provider == 'outlook':
        mailserver = 'imap-mail.outlook.com'
    else:
        mailserver = None
    _LOGGER.debug("Provider is set to %s using %s", provider, mailserver)
    return mailserver

def get_formatted_date():
    """Returns today in specific format"""
    return datetime.datetime.today().strftime('%d-%b-%Y')
    #return '29-07-2018'

def select_folder(account, inbox_folder):
    """Select the folder in the inbox to use"""
    #account.list()
    account.select(inbox_folder)

def get_camera(camera_file, camera_dir):
    """Downloading the camera"""
    _LOGGER.debug('Could not find %s in %s.', camera_file, camera_dir)
    sensor_full_path = camera_dir + camera_file
    response = requests.get(CAMERA_URL)
    if response.status_code == 200:
        _LOGGER.debug('Checking folder structure')
        directory = os.path.dirname(camera_dir)
        if not os.path.exists(directory):
            os.makedirs(directory)
        with open(sensor_full_path, 'wb+') as sensorfile:
            sensorfile.write(response.content)
        task_state = True
    else:
        _LOGGER.critical('Failed to download camera from %s', CAMERA_URL)
        task_state = False
    return task_state

#def default_image(outdir):
def default_image():
    """Set a default image if there is none from mail"""
    base = """
    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
    """
    return base
