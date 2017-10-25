from simple_isi import IsiClient, PAPIClient
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


# defaults
config = {
        'server': '',
        'port': 8080,
        'username': '',
        'password': '',
        'verify': None }

def main():
    # arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", help="Pass json through, no resume support", action='store_true')
    parser.add_argument('--verbose', '-v', action='count')
    parser.add_argument("--server", help="server name")
    parser.add_argument("--noverify", help="Turn off SSL verification", action='store_false', default=None)
    parser.add_argument("--tag", help="Parse and return tag from results with resume support")
    parser.add_argument("endpoint", help="PAPI endpoint")
    parser.add_argument("paramaters", nargs="*", help="endpoint paramters")
    args = parser.parse_args()

    # merge in saved defaults
    for filename in ('isilon.yaml', os.path.join(os.path.expanduser('~'),'.isilon_yaml')):
        try:
            config.update(yaml.safe_load(open(filename)))
        except:
            pass

    # override 
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

    client = IsiClient(server=config['server'], port=config['port'], auth=auth, verify=config['verify'])
    if not auth:
        # No saved credentials, try to gather from stdin
        client.auth()

    papi = PAPIClient(client)

    params = dict(map(lambda x: x + [''] * (2 - len(x)), (x.split("=",1) for x in args.paramaters)))

    out = papi.get(args.endpoint, **params)
    try:
        if args.raw:
            print(out.text)
        else:
            print(dumps(list(out.fetchall(args.tag))))
    except:
        print(out.text)

