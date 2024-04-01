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

def print_line(msg):
    """ print a message on the same line """

    print(f'{CLEARLINE}', end='')
    print(f'{NOCURSOR}{msg}', end='\r', flush=True)

def progress(i):
    """ prints a progress indicator """

    return PROGRESS[i % 4]

def green_text(text):
    """ highlights text in green """

    return f'{BColors.OKGREEN}{text}{BColors.ENDC}'

def red_text(text):
    """ highlights text in red """

    return f'{BColors.FAIL}{text}{BColors.ENDC}'

def choose_realm(realms):
    """ choose the right realm to use """

    none = len(realms) + 1

    print('\nRESULTS:')
    for realm in realms:
        num = green_text(realms.index(realm) + 1)
        category = realm['category'] + ' ' + realm['rgv'][-2:].upper()
        print(f'[{num}] {realm["name"]} ({category})')
    print(f'[{green_text(none)}] None\n')

    choice = None
    while choice is None:
        opts = green_text(f'1-{none}')
        i = input(f'Choose your Realm [{opts}]: ')
        try:
            i = int(i)
        except ValueError:
            i = 0

        if i == none:
            clear_screen()
            return None, None

        i-=1
        if 0 <= i < len(realms):
            choice = i
            continue

        print('Invalid Option.')

    return realms[choice]['name'], realms[choice]['rgv']

def build_realm_list():
    """ build a list of realm names """

    rgvs   = [get_rgv(r,gv) for r in REGIONS for gv in GAMEVERSIONS]
    realm_list = []

    clear_screen()

    msg = green_text('Building realm list')
    i=0
    for rgv in rgvs:
        i+=1
        time.sleep(SLEEP/2)

        print_line(f'{progress(i)} {msg}')

        body, error = api_call(rgv)

        if error:
            print(f'{error} while building realm list. ({rgv})')
            continue

        if not valid_response(body):
            print(f'Invalid response while building realm list. ({rgv})')
            continue

        for rlm in body['data']['Realms']:
            name = rlm['name']
            category = rlm['category']
            realm_list.append({'name': name, 'rgv': rgv, 'category': category})

    return realm_list

def find_realms(search_string, realm_list):
    """ find a realm by name """

    realms = []

    for rlm in realm_list:
        name = rlm['name']
        rgv  = rlm['rgv']
        category = rlm['category']

        if simple_string(name) == search_string:
            realms.append({'name': name, 'rgv': rgv, 'category': category})

    return realms

def find_realm():
    """ gets realm info for config """

    if realm_name() != '':
        return

    realm_list = build_realm_list()

    rlm_name = None
    msg = 'Enter your realm name: '
    while rlm_name is None:
        clear_screen()
        rlm    = input(msg)
        rlm    = simple_string(rlm)
        realms = find_realms(rlm, realm_list)

        if len(realms) == 0:
            msg = 'Realm name not found. Enter your realm name: '
            continue

        if len(realms) == 1:
            rlm_name = realms[0]['name']
            rgv      = realms[0]['rgv']
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
        i+=1
        time.sleep(SLEEP)

        online = False
        body, error = api_call(region_game_version())

        if error:
            name   = red_text('ERROR')
            status = red_text(error)

        if not valid_response(body):
            continue

        for rlm in body['data']['Realms']:
            if rlm['name'] != realm_name():
                continue

            name   = red_text(realm_name())
            online = bool(rlm['online'])

        status = red_text('DOWN')

        if online:
            name   = green_text(realm_name())
            status = green_text('UP')

        print_line(f'{progress(i)} {name}: {status}')

load_config()
find_realm()

try:
    check_status()
except KeyboardInterrupt:
    pass

print(CURSOR, end='')
