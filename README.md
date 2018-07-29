# USPS Mail

A component that give you to info about incoming letters and packages from USPS.\
This component is based of the work of [skalavala](https://github.com/skalavala)

***
⚠️ **Before you start using this make sure that you read this article on [skalavala's blog](https://skalavala.github.io/usps/).**\
Read down to `Prerequisites`, from that part this component takes care of the rest.
***

## Installation

### Step 1

Install this component by copying `/custom_components/usps_mail.py` from this repo to `<config directory>/custom_components/usps_mail.py` on your Home Assistant instanse.

### Step 2

Add this to your `configuration.yaml`

```yaml
usps_mail:
  provider: gmail
  email: 'username@gamil.com'
  password: 'fjkhg347847idsbj'
  output_dir: '/config/www/'
```

#### Optional config options

| key | default | required | description
| --- | --- | --- | ---
| **provider** | | yes | Your mail provider, can be `gmail`, `outlook`, `yahoo`
| **email** | | yes | Your email address
| **password** | | yes | Your mail password, if you have 2FA enabled you need to create a `App password` for this.
| **output_dir** | None | no | The directory where it wil put a gif, should be `%configdir%/www`
| **inbox_folder** | `Inbox` | no | The folder in your inbox where these mails are
| **port** | `993` | no | The IMAP port that the provider is using.

***

## To get a camera feed of your gif (pending mails)

**NB!: This require you to set a `output_dir` in the configuration for `usps_mail`**

Add this to your `configuration.yaml`

```yaml
camera:
  - platform: local_file
    name: USPS Mail Pictures
    file_path: /config/www/USPS.gif
```

***

## Updates

This component are subject to change.\
To make sure you get notified about upcoming releases you should also get the [custom_updater](https://github.com/custom-components/custom_updater) component.

***

## Activate Debug logging

Put this in your `configuration.yaml`

```yaml
logger:
  default: warn
  logs:
    custom_components.usps_mail: debug
```

***

Due to how `custom_componentes` are loaded, it is normal to see a `ModuleNotFoundError` error on first boot after adding this, to resolve it, restart Home-Assistant.