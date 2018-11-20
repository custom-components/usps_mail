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

__version__ = '0.1.0'
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'usps_mail'
USPS_MAIL_DATA = DOMAIN + '_data'
CONF_PROVIDER = 'provider'
CONF_INBOXFOLDER = 'inbox_folder'
CONF_CAMERA = 'camera'
CONF_DEFAULT_IMG = 'default_image'

MIN_CAMERA_VERSION = '0.0.4'

INTERVAL = datetime.timedelta(hours=1)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PROVIDER): cv.string,
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEFAULT_IMG, default='None'): cv.string,
        vol.Optional(CONF_CAMERA, default=False): cv.boolean,
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
    camera = config[DOMAIN][CONF_CAMERA]
    image = config[DOMAIN][CONF_DEFAULT_IMG]
    ha_conf_dir = str(hass.config.path())
    usps_mail = UspsMail(hass, mailserver, port, inbox_folder, username, password, image, ha_conf_dir)
    if camera:
        camera_dir = str(hass.config.path("custom_components/camera/"))
        camera_file = 'usps_mail.py'
        camera_full_path = camera_dir + camera_file
        if not os.path.isfile(camera_full_path):
            get_camera(camera_file, camera_dir)
        with open(camera_full_path, 'r') as local:
            for line in local.readlines():
                if '__version__' in line:
                    camera_version = line.split("'")[1]
                    break
        local.close()
        if camera_version != MIN_CAMERA_VERSION:
            get_camera(camera_file, camera_dir)
        load_platform(hass, 'camera', DOMAIN, {}, config)
    def scan_mail_service(call):
        """Set up service for manual trigger."""
        usps_mail.scan_mail(call)
    track_time_interval(hass, usps_mail.scan_mail, INTERVAL)
    hass.services.register(DOMAIN, 'scan_mail', scan_mail_service)
    return True


class UspsMail:
    """The class for this component"""
    def __init__(self, hass, mailserver, port, inbox_folder, username, password, image, ha_conf_dir):
        self.hass = hass
        self.packages = None
        self.letters = None
        self.ha_conf_dir = ha_conf_dir
        self._mailserver = mailserver
        self._port = port
        self._default_image = image
        self._inbox_folder = inbox_folder
        self._username = username
        self._password = password
        self.hass.data[USPS_MAIL_DATA] = {}
        self.scan_mail('now')

    def scan_mail(self, call):
        """Main logic of the component"""
        try:
            account = self.login()
            select_folder(account, self._inbox_folder)
        except Exception as exx:
            _LOGGER.debug("Error connecting logging into email server.")
            _LOGGER.debug(str(exx))

        mail_count = self.get_mails(account)
        package_count = self.package_count(account)

        self.hass.data[USPS_MAIL_DATA]['mailattr'] = {'icon': 'mdi:email-outline', 'friendly_name': 'USPS Mail'}
        self.hass.data[USPS_MAIL_DATA]['packageattr'] = {'icon': 'mdi:package-variant', 'friendly_name': 'USPS Packages'}
        self.hass.states.set('sensor.usps_letters', mail_count, self.hass.data[USPS_MAIL_DATA]['mailattr'])
        self.hass.states.set('sensor.usps_packages', package_count, self.hass.data[USPS_MAIL_DATA]['packageattr'])


    def get_mails(self, account):
        """Get mail count from mail"""
        self.hass.data[USPS_MAIL_DATA]['images'] = []
        today = get_formatted_date()
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
                    image = base64.b64encode(part.get_payload(decode=True))
                    self.hass.data[USPS_MAIL_DATA]['images'].append(image)
                    image_count = image_count + 1
                _LOGGER.debug("Found %s mails and images in your email.", image_count)
        if image_count == 0:
            _LOGGER.debug("Found %s mails", image_count)
            self.hass.data[USPS_MAIL_DATA]['images'].append(default_image(self.ha_conf_dir, self._default_image))
        self.hass.data[USPS_MAIL_DATA]['count'] = 0
        self.hass.data[USPS_MAIL_DATA]['total'] = image_count
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
        _LOGGER.debug('Finished downloading the camera.')
    else:
        _LOGGER.critical('Failed to download camera from %s', CAMERA_URL)
        task_state = False
    return task_state

def default_image(hadir, image_location):
    """Set a default image if there is none from mail"""
    base = """
    R0lGODlhvgJHAbMAAPX1+JeplnaIc9nZ2IaXe7LCrs6grmZ0YrjMzf7///3///z///v///n/////
    //v7+iH/C1hNUCBEYXRhWE1QPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpy
    ZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0
    az0iQWRvYmUgWE1QIENvcmUgNS42LWMxMzggNzkuMTU5ODI0LCAyMDE2LzA5LzE0LTAxOjA5OjAx
    ICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIv
    MjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4
    bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMu
    YWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94
    YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3No
    b3AgQ0MgMjAxNyAoTWFjaW50b3NoKSIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDo1RDUwQzZG
    RDkwOTIxMUU4QUY2NzlEMTY0MzUxRkIzOCIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDo1RDUw
    QzZGRTkwOTIxMUU4QUY2NzlEMTY0MzUxRkIzOCI+IDx4bXBNTTpEZXJpdmVkRnJvbSBzdFJlZjpp
    bnN0YW5jZUlEPSJ4bXAuaWlkOjVENTBDNkZCOTA5MjExRThBRjY3OUQxNjQzNTFGQjM4IiBzdFJl
    Zjpkb2N1bWVudElEPSJ4bXAuZGlkOjVENTBDNkZDOTA5MjExRThBRjY3OUQxNjQzNTFGQjM4Ii8+
    IDwvcmRmOkRlc2NyaXB0aW9uPiA8L3JkZjpSREY+IDwveDp4bXBtZXRhPiA8P3hwYWNrZXQgZW5k
    PSJyIj8+Af/+/fz7+vn49/b19PPy8fDv7u3s6+rp6Ofm5eTj4uHg397d3Nva2djX1tXU09LR0M/O
    zczLysnIx8bFxMPCwcC/vr28u7q5uLe2tbSzsrGwr66trKuqqainpqWko6KhoJ+enZybmpmYl5aV
    lJOSkZCPjo2Mi4qJiIeGhYSDgoGAf359fHt6eXh3dnV0c3JxcG9ubWxramloZ2ZlZGNiYWBfXl1c
    W1pZWFdWVVRTUlFQT05NTEtKSUhHRkVEQ0JBQD8+PTw7Ojk4NzY1NDMyMTAvLi0sKyopKCcmJSQj
    IiEgHx4dHBsaGRgXFhUUExIREA8ODQwLCgkIBwYFBAMCAQAAIfkEAAAAAAAsAAAAAL4CRwEABP+Q
    tTnZUi6rxdRmVvJRFfZkaCYm4uM6ibNQYNPFaezhyWwrOokFKOKAMLBErZNKfYSYROMxVflIU9cJ
    RqViJ8iFl7ZQCck4FGPc1Y4p7rh8TpcD7vi8fs/v+/9+D4B7DQCChneHXYV5gm6Ig5GSk5SVlpeY
    mZqbnJ2GWp57DqGkABIkISg9IEY3CkunFg4eSSivIFqvCxxkrBdIKhtAMLw3s1Aeu8plqkvALNC3
    EwsxUlMNYTSsuSrXXzbUPRMADUbhrzY0wDAOayRtWRNedfT1dqX4jS6T7/d69fkCChxIsKDBgwgP
    nkKjqhWUIiBq2MBxiwGOLA8YZCgW68IqVlH/jqUS9yPIkV0gacEY8YPYMmWnmFnT9m7NGjcK3nyx
    qdMDugrpSpzI6cbbNRfXyJFrY6/pnIRQ78Dxp49e1KtYs2rdytWgERupgi2pEO6KOg1QYLirMgto
    CTPT0piLUmyYzw2twkWL+JZlRL4yF86TVy/ot3glqmn5dlOON3JHF8PB6LRynK74vCy9vMceZq4D
    tob+TJrgodJ/pIHkgTIoEyWomKxMO9MGWsOyiIFLMZfYwyYSw0J0jeGntiXVzGJhOkdihYU7qcE4
    XGFOoXHYqSBCzNyyZdSS9p02dH0q50SOAIJfj2+0pdHu2ctPNF/Px9yqnsTSUO7vDlse5BIb/18h
    fLSLT2l84NF90qXQ0TArtVIBfw79VQ4S0sQzDz0W/OWcUeD4BOJCjcVBgVKUSXaddyzuMxB8mriD
    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
    hTdnfxzyEqE3cZMYAQA7
    """
    if image_location != 'None':
        with open(hadir + image_location, 'rb') as img_file:
            image = img_file.read()
        img_file.close()
        base = base64.b64encode(image)
    return base
