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

def find_realm_name(search_string):
    """ find a realm by name """

    for r in REGIONS:
        for gv in GAMEVERSIONS:
            rgv = get_rgv(r, gv)
            body, error = api_call(rgv)

            if error:
                print(f'{error} while searching connected realms.')
                return None, None

            if not 'data' in body or not 'Realms' in body['data']:
                return None, None

            for rlm in body['data']['Realms']:
                name = rlm['name']

                if simple_string(name) == search_string:
                    return name, rgv

    return None, None

def find_realm():
    """ gets realm info for config """

    if realm_name() != '':
        return

    rlm_name = None
    msg = 'Enter your realm name: '
    while rlm_name is None:
        clear_screen()
        rlm = input(msg)
        rlm = simple_string(rlm)
        rlm_name, rgv = find_realm_name(rlm)
        msg = 'Realm name not found. Enter your realm name: '

    config.set('REALM', 'name', rlm_name)
    config.set('REALM', 'region_game_version', rgv)

    with open(CONFIG_FILE, 'w', encoding='ascii') as configfile:
        config.write(configfile)

def check_status():
    """ get realm status """ 

    clear_screen()

    i=0
    while True:
        online = False
        body, error = api_call(region_game_version())

        if error:
            name = 'ERROR'
            status = error

        if not body:
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
        time.sleep(SLEEP)

load_config()
find_realm()

try:
    check_status()
except KeyboardInterrupt:
    pass

print(CURSOR, end='')
