"""
Eagle Eye - A WoW realm status monitor
"""
import configparser
import json
import os
import sys
import time
from os.path import exists
import requests

REGIONS       = ['us','eu','kr','tw']
GAMEVERSIONS  = ['','classic','classic1x']
CONFIG_FILE   = '.eagle.ini'
URL           = 'https://worldofwarcraft.blizzard.com/graphql'
SHA256HASH    = 'b37e546366a58e211e922b8c96cd1ff74249f564a49029cc9737fef3300ff175'
TIMEOUT       = 10
SLEEP         = 1
PROGRESS      = ['|','/','-','\\']
NOCURSOR      = '\033[?25l'
CURSOR        = '\033[?25h'
CLEARLINE     = '\x1b[K'
RESET         = bool(sys.argv[1:] and sys.argv[1].lower() == 'reset')

config = configparser.ConfigParser()

def region_game_version():
    """ get realm id from config """

    return config['REALM']['region_game_version']

def realm_name():
    """ get realm id from config """

    return config['REALM']['name']

def get_settings(cfg):
    """ validates the settings of the config file """

    if not cfg.has_section('REALM'):
        cfg.add_section('REALM')

    if RESET or not cfg.has_option('REALM', 'region_game_version') or region_game_version() == '':
        cfg.set('REALM', 'region_game_version', '')

    if RESET or not cfg.has_option('REALM', 'name') or realm_name() == '':
        cfg.set('REALM', 'name', '')

def load_config():
    """ load the config file """

    if exists(CONFIG_FILE):
        config.read(CONFIG_FILE)

    get_settings(config)

    with open(CONFIG_FILE, 'w', encoding='ascii') as configfile:
        config.write(configfile)

class BColors:
    """ font colors """

    HEADER    = '\033[95m'
    OKBLUE    = '\033[94m'
    OKCYAN    = '\033[96m'
    OKGREEN   = '\033[92m'
    WARNING   = '\033[93m'
    FAIL      = '\033[91m'
    ENDC      = '\033[0m'
    BOLD      = '\033[1m'
    UNDERLINE = '\033[4m'

def clear_screen():
    """ clear the terminal screen """

    os.system('cls' if os.name == 'nt' else 'clear')

def simple_string(string):
    """ simplify strings for comparison """

    string = string.strip()
    string = string.replace('-','')
    string = string.replace('_','')
    string = string.replace(' ','')
    string = string.lower()

    return string

def headers():
    """ headers for api call """

    return {
        'Content-Type': 'application/json'
    }

def data(reg_gam_ver):
    """ body for api call """

    return json.dumps({
        "operationName": "GetRealmStatusData",
        "variables": {
            "input": {
                "compoundRegionGameVersionSlug": reg_gam_ver
            }
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": SHA256HASH
            }
        }
    })

def get_rgv(region,game_version):
    """ region game version for api call """

    if game_version == '':
        return region

    return f'{game_version}-{region}'

def api_call(rgv):
    """ makes a call to the Blizzard API """

    body = None
    error = None

    try:
        response = requests.post(
            URL,
            headers=headers(),
            data=data(rgv),
            timeout=TIMEOUT
        )
        response.raise_for_status()
        body = response.json()
    except requests.HTTPError as e:
        error = f'HTTPError {e.response.status_code}'
    except requests.exceptions.ConnectTimeout:
        error = 'ConnectTimeout'
    except requests.exceptions.ReadTimeout:
        error = 'ReadTimeout'
    except requests.exceptions.JSONDecodeError:
        error = 'JSONDecodeError'
    except KeyError:
        error = 'KeyError'

    return body, error

def valid_response(body):
    """ Validate JSON has required keys """

    if not body:
        return False

    if not 'data' in body:
        return False

    if not 'Realms' in body['data']:
        return False

    return True

def choose_realm(realms):
    """ choose the right realm to use """

    for realm in realms:
        print(f'{realms.index(realm) + 1}) {realm["name"]} {realm["rgv"]}')

    choice = None
    while choice is None:
        i = input(f'Choose your Realm [1-{len(realms)}]: ')
        try:
            i = int(i) - 1
        except ValueError:
            i = 0

        if 0 <= i < len(realms):
            choice = i
            continue

        print('Invalid Option.')

    return realms[choice]['name'], realms[choice]['rgv']

def find_realms(search_string):
    """ find a realm by name """

    rgvs   = [get_rgv(r,gv) for r in REGIONS for gv in GAMEVERSIONS]
    realms = []

    for rgv in rgvs:
        body, error = api_call(rgv)

        if error:
            print(f'{error} while searching connected realms.')
            return realms

        if not valid_response(body):
            return realms

        for rlm in body['data']['Realms']:
            name = rlm['name']

            if simple_string(name) == search_string:
                realms.append({'name': name, 'rgv': rgv})

    return realms

def find_realm():
    """ gets realm info for config """

    if realm_name() != '':
        return

    clear_screen()
    rlm_name = None
    msg = 'Enter your realm name: '
    while rlm_name is None:
        rlm = input(msg)
        rlm = simple_string(rlm)
        realms = find_realms(rlm)

        if len(realms) == 0:
            msg = 'Realm name not found. Enter your realm name: '
            continue

        if len(realms) == 1:
            rlm_name = realms[0]['name']
            rgv = realms[0]['rgv']
            continue

        rlm_name, rgv = choose_realm(realms)

    config.set('REALM', 'name', rlm_name)
    config.set('REALM', 'region_game_version', rgv)

    with open(CONFIG_FILE, 'w', encoding='ascii') as configfile:
        config.write(configfile)

def check_status():
    """ get realm status """ 

    clear_screen()

    i=0
    while True:
        time.sleep(SLEEP)

        online = False
        body, error = api_call(region_game_version())

        if error:
            name = 'ERROR'
            status = error

        if not valid_response(body):
            continue

        for rlm in body['data']['Realms']:
            if rlm['name'] != realm_name():
                continue

            name = realm_name()
            online = bool(rlm['online'])

        progress = PROGRESS[i % 4]
        i+=1

        color  = BColors.FAIL
        status = 'DOWN'

        if online:
            color  = BColors.OKGREEN
            status = 'UP'

        print(f'{CLEARLINE}', end='')
        print(f'{NOCURSOR}{progress}{color} {name}: {status}{BColors.ENDC}', end='\r', flush=True)

load_config()
find_realm()

try:
    check_status()
except KeyboardInterrupt:
    pass

print(CURSOR, end='')
