from . import IsiClient, PapiClient, quiet
from json import dumps
import sys
import argparse
import logging
import yaml
import os

logger = logging.getLogger()
logging.basicConfig(
            level=30,
            format='%(relativeCreated)6.1f %(processName)12s: %(levelname).1s %(module)8.8s:%(lineno)-4d %(message)s')

# Safety
try:
    os.umask(0o0077)
except:
    logger.warning("Unable to set umask, please verify that cookiejae is safe")

# defaults
config = {
        'server': '',
        'port': 8080,
        'username': '',
        'password': '',
        'verify': True }

# disable SSL verification warnings
quiet()

def main():
    # arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", "-p", help="Profile from config file if not default", default='default')
    parser.add_argument("--raw", help="Pass json through, no resume support", action='store_true')
    parser.add_argument('--verbose', '-v', action='count')
    parser.add_argument("--server", help="server name")
    parser.add_argument("--noverify", help="Turn off SSL verification", action='store_false', default=None)
    parser.add_argument("--tag", help="Parse and return tag from results with resume support")
    parser.add_argument("endpoint", help="PAPI endpoint")
    parser.add_argument("paramaters", nargs="*", help="endpoint paramters")
    args = parser.parse_args()

    # merge in saved defaults
    for filename in ('isilon.yaml', os.path.expanduser('~/.isilon_yaml')):
        try:
            config.update(yaml.safe_load(open(filename))[args.profile])
        except:
            pass

    # override 
    logger.debug("%s", repr(config))
    if args.server:
        config['server'] = args.server

    if args.verbose:
        logger.setLevel(30-(10*args.verbose))

    # create client
    if config['username'] != '' and config['password'] != '':
        auth=(config['username'], config['password'])
    else:
        auth=None
    
    try:
        if args.noverify != None:
            config['verify'] = args.noverify
    except:
        pass

    client = IsiClient(**config)
    #client.auth()

    papi = PapiClient(client)

    # Munge paramaters into a dict
    params = dict(map(lambda x: x + [''] * (2 - len(x)), (x.split("=",1) for x in args.paramaters)))

    out = papi.get(args.endpoint, **params)
    try:
        if args.raw:
            print(out.text)
        else:
            for item in out.iter_json():
                print(dumps(item))
    except:
        print(out.text)

