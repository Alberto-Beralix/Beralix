# -*- coding: utf-8 -*-
#
# Author: Natalia Bidart <natalia.bidart@canonical.com>
# Author: Manuel de la Pena <manuel@canonical.com>
#
# Copyright 2011 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utils to be used by the UI modules."""

import os
import re
import gettext

from ubuntu_sso.logger import setup_logging
from ubuntu_sso import xdg_base_directory

logger = setup_logging('ubuntu_sso.utils.ui')


gettext.textdomain('ubuntu-sso-client')
_ = gettext.gettext

# all the text that is used in the gui
CAPTCHA_SOLUTION_ENTRY = _('Type the characters above')
CAPTCHA_LOAD_ERROR = _('There was a problem getting the captcha, '
                       'reloading...')
CAPTCHA_REQUIRED_ERROR = _('The captcha is a required field')
CONNECT_HELP_LABEL = _('To connect this computer to %(app_name)s ' \
                       'enter your details below.')
EMAIL1_ENTRY = _('Email address')
EMAIL2_ENTRY = _('Re-type Email address')
EMAIL_LABEL = EMAIL1_ENTRY + ':'
EMAIL_MISMATCH = _('The email addresses don\'t match, please double check '
                       'and try entering them again.')
EMAIL_INVALID = _('The email must be a valid email address.')
EMAIL_TOKEN_ENTRY = _('Enter code verification here')
ERROR = _('The process did not finish successfully.')
EXISTING_ACCOUNT_CHOICE_BUTTON = _('Sign me in with my existing account')
FIELD_REQUIRED = _('This field is required.')
FORGOTTEN_PASSWORD_BUTTON = _('I\'ve forgotten my password')
JOIN_HEADER_LABEL = _('Create %(app_name)s account')
LOADING = _('Loading...')
LOGIN_BUTTON_LABEL = _('Already have an account? Click here to sign in')
LOGIN_EMAIL_ENTRY = _('Email address')
LOGIN_HEADER_LABEL = _('Connect to %(app_name)s')
LOGIN_PASSWORD_ENTRY = _('Password')
LOGIN_PASSWORD_LABEL = LOGIN_PASSWORD_ENTRY + ':'
NAME_ENTRY = _('Name')
NEXT = _('Next')
ONE_MOMENT_PLEASE = _('One moment please...')
PASSWORD_CHANGED = _('Your password was successfully changed.')
PASSWORD1_ENTRY = RESET_PASSWORD1_ENTRY = _('Password')
PASSWORD2_ENTRY = RESET_PASSWORD2_ENTRY = _('Re-type Password')
PASSWORD_HELP = _('The password must have a minimum of 8 characters and ' \
                  'include one uppercase character and one number.')
PASSWORD_MISMATCH = _('The passwords don\'t match, please double check ' \
                      'and try entering them again.')
PASSWORD_TOO_WEAK = _('The password is too weak.')
REQUEST_PASSWORD_TOKEN_LABEL = _('To reset your %(app_name)s password,'
                                 ' enter your email address below:')
REQUEST_PASSWORD_TOKEN_WRONG_EMAIL = _('Sorry we did not recognize the email'
                                       ' address.')
REQUEST_PASSWORD_TOKEN_TECH_ERROR = _('We are very Sorry! The service that'
                                      ' signs you on is not responding right'
                                      ' now\nPlease try again or come back in'
                                      ' a few minutes.')
RESET_PASSWORD = _('Reset password')
RESET_CODE_ENTRY = _('Reset code')
RESET_EMAIL_ENTRY = _('Email address')
SET_NEW_PASSWORD_LABEL = _('A password reset code has been sent to ' \
                           '%(email)s.\nPlease enter the code below ' \
                           'along with your new password.')
SET_UP_ACCOUNT_CHOICE_BUTTON = _('I don\'t have an account yet - sign me up')
SET_UP_ACCOUNT_BUTTON = _('Set up Account')
SIGN_IN_BUTTON = _('Sign In')
SUCCESS = _('The process finished successfully. Congratulations!')
SURNAME_ENTRY = _('Surname')
TC_BUTTON = _('Show Terms & Conditions')
TC_NOT_ACCEPTED = _('Agreeing to the Ubuntu One Terms & Conditions is ' \
                        'required to subscribe.')
TRY_AGAIN_BUTTON = _('Try again')
UNKNOWN_ERROR = _('There was an error when trying to complete the ' \
                      'process. Please check the information and try again.')
VERIFY_EMAIL_TITLE = _('Enter verification code')
VERIFY_EMAIL_CONTENT = _('Check %(email)s for an email from'
                         ' Ubuntu Single Sign On.'
                         ' This message contains a verification code.'
                         ' Enter the code in the field below and click OK'
                         ' to complete creating your %(app_name)s account')
VERIFY_EMAIL_LABEL = ('<b>%s</b>\n\n' % VERIFY_EMAIL_TITLE +
                      VERIFY_EMAIL_CONTENT)
TOS_LABEL = _("You can also find these terms at <a href='%(url)s'>%(url)s</a>")
YES_TO_TC = _('I agree with the %(app_name)s terms and conditions')
YES_TO_UPDATES = _('Yes! Email me %(app_name)s tips and updates.')
CAPTCHA_RELOAD_TOOLTIP = _('Reload')


def get_data_dir():
    """Build absolute path to  the 'data' directory."""
    module = os.path.dirname(__file__)
    result = os.path.abspath(os.path.join(module, os.pardir,
                                          os.pardir, 'data'))
    logger.debug('get_data_file: trying to load from %r (exists? %s)',
                 result, os.path.exists(result))
    if os.path.exists(result):
        logger.info('get_data_file: returning data dir located at %r.', result)
        return result

    # no local data dir, looking within system data dirs
    data_dirs = xdg_base_directory.xdg_data_dirs
    for path in data_dirs:
        result = os.path.join(path, 'ubuntu-sso-client', 'data')
        result = os.path.abspath(result)
        logger.debug('get_data_file: trying to load from %r (exists? %s)',
                     result, os.path.exists(result))
        if os.path.exists(result):
            logger.info('get_data_file: data dir located at %r.', result)
            return result
    else:
        msg = 'get_data_file: can not build a valid data path. Giving up.' \
              '__file__ is %r, data_dirs are %r'
        logger.error(msg, __file__, data_dirs)


def get_data_file(*args):
    """Build absolute path to the path within the 'data' directory."""
    return os.path.join(get_data_dir(), *args)


def get_password_strength(password):
    """Return the strength of the password.

    This function returns the strength of the password so that ui elements
    can show the user how good his password is. The logic used is the
    following:

    * 1 extra point for 4 chars passwords
    * 1 extra point for 8 chars passwords
    * 1 extra point for more than 11 chars passwords.
    * 1 extra point for passwords with at least one number.
    * 1 extra point for passwords for lower and capital chars.
    * 1 extra point for passwords with a special char.

    A passwords starts with 0 and the extra points are added accordingly.
    """
    score = 0
    if len(password) < 1:
        return 0
    if len(password) < 4:
        score = 1
    if len(password) >= 8:
        score += 1
    if len(password) >= 11:
        score += 1
    if re.search('\d+', password):
        score += 1
    if re.search('[a-z]', password) and re.search('[A-Z]', password):
        score += 1
    if re.search('.[!,@,#,$,%,^,&,*,?,_,~,-,£,(,)]', password):
        score += 1
    return score


def is_min_required_password(password):
    """Return if the password meets the minimum requirements."""
    if (len(password) < 8 or
        re.search('[A-Z]', password) is None or
        re.search('\d+', password) is None):
        return False
    return True


def is_correct_email(email_address):
    """Return if the email is correct."""
    return '@' in email_address
