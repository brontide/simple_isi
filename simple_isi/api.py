
''' Client tools for Isilon restful api '''

#
# BEGIN py2 compatibility section
#

# print function
from __future__ import print_function


# This is a hack to allow partialmethod on py2
try:
    from functools import partialmethod
except BaseException:
    # python 2 hack https://gist.github.com/carymrobbins/8940382
    from functools import partial

    class partialmethod(partial):
        def __get__(self, instance, owner):
            if instance is None:
                return self
            return partial(self.func, instance,
                           *(self.args or ()), **(self.keywords or {}))

# Make input() work the same
try:
    input = raw_input
except NameError:
    pass

# urllib
from future.standard_library import install_aliases
install_aliases()

#
# END py2 compatibility cruft
#

import requests
import logging
from getpass import getpass, getuser
import sys
from http.cookiejar import LWPCookieJar as fcj
import os
from functools import partial
from datetime import datetime
from urllib.parse import quote
import time
from tarfile import filemode


def sfmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


quiet = requests.packages.urllib3.disable_warnings

logger = logging.getLogger(__name__)


class IsiApiError(ValueError):
    ''' Wapper around Isilon errors which attempts to pull the error from the json if possible '''

    def __init__(self, out):
        self.request_response = out
        try:
            data = out.json()
            ValueError.__init__(self, "Error {}/{} when connecting to url {}".format(
                data['errors'][0]['code'], data['errors'][0]['message'], out.url))
        except BaseException:
            ValueError.__init__(
                self, "URL: {} status code {}".format(
                    out.url, out.status_code))


class IsiClient(object):
    ''' Bare bones Isilon RESTful client designed for utter simplicity '''

    def __init__(
            self,
            server=None,
            username='',
            password='',
            port=8080,
            verify=True):
        self._cookiejar_path = os.path.expanduser('~/.isilon_cookiejar')
        self._s = requests.Session()
        # Set a fixed user-agent since the isisessid is only valid for the current
        # user-agent
        self._s.headers['User-Agent'] = 'simple-isi library based on requests'
        self._s.cookies = fcj()
        try:
            self._s.cookies.load(
                self._cookiejar_path,
                ignore_discard=True,
                ignore_expires=True)
        except BaseException:
            logger.warning(
                "Could not load cookies from %s",
                self._cookiejar_path)
        self.server = server
        self.username = username
        self.password = password
        self.port = port
        self._s.verify = verify
        # if we have cookies make an attempt to login
        logger.debug("Attempting to use cached credentials")
        #self._expires = time.time() + self.refresh_session()
        self._expires = -1
        self.is_ready(prompt=False, force=True)

    def is_ready(self, auto_refresh=600, prompt=True, force=False):
        expires_in = self._expires - time.time()
        # good session
        if not force and expires_in >= auto_refresh:
            return True
        # will expire in less than auto_refresh or forced
        # from a unknown state
        if force or (expires_in > 0 and expires_in < auto_refresh):
            self._expires = time.time() + self.refresh_session()
            return True
        # try to create a new session, will work if username and
        # password are stored
        try:
            self._expires = time.time() + self.create_session()
            return True
        except BaseException:
            pass
        # Must query
        if not prompt:
            return False
        try:
            self._expires = time.time() + self.auth()
            return True
        except BaseException:
            pass
        return False

    def refresh_session(self):
        # returns the time remaining in the session
        try:
            out = self.get('session/1/session', ready_check=False)
            data = out.json()
            self.username = data['username']
            length = min(data["timeout_absolute"], data["timeout_inactive"])
            if length > 60:
                # good senssion
                self._s.cookies.save(
                    self._cookiejar_path,
                    ignore_discard=True,
                    ignore_expires=True)
                return length
        except BaseException:
            # Fallthough for errors
            return -1

    def create_session(self):
        # attempts to authenticate with session module
        if self.username == '' or self.password == '':
            raise ValueError("Can't login without credentials")
        login = {
            'username': self.username,
            'password': self.password,
            'services': [
                'platform',
                'namespace']}
        try:
            self.post('session/1/session', json=login, ready_check=False)
            self.ready = True
        except BaseException:
            logger.debug("Login failure")
        return self.refresh_session()

    def logout(self):
        ''' logout of a valid session / destroy cookie and 
            authentication tokens '''
        self.password = ''
        self._expires = -1
        out = self.delete('session/1/session', ready_check=False, raise_on_error=False)

    def __repr__(self):
        if self._s.auth:
            auth = "with auth of {}/{}".format(self.username,
                                               "*" * len(self.password))
        else:
            auth = "NO AUTHENTICATION TOKEN"
        return "IsiClient-https://{}:{} {}".format(
            self.server, self.port, auth)

    def auth(self):
        # Query for interactive credentials

        # only works for ttys
        if not sys.stdin.isatty():
            logger.warning(
                "Session not ready and no interactive credentials, this will probably fail")
        #    return None

        # Start interactive login
        print(
            "Please enter credentials for Isilon https://{}:{}\nUsername (CR={}): ".format(
                self.server,
                self.port,
                getuser()),
            file=sys.stderr,
            end='')
        username = input()
        if username == "":
            username = getuser()
        password = getpass("{} Password : ".format(username), sys.stderr)

        self.username = username
        self.password = password

        return self.create_session()

    def request(
            self,
            method,
            endpoint,
            x_append_prefix=True,
            raise_on_error=True,
            ready_check=True,
            json=None,
            stream=False,
            **params):
        ''' Perform a RESTful method on the Isilon '''
        if ready_check and not self.is_ready():
            logger.warning("Unauthenticates REST call, will probably fail")

        if x_append_prefix:
            url = 'https://{}:{}/{}'.format(self.server,
                                            self.port, quote(endpoint))
        else:
            url = endpoint
        logger.debug("%s %s <- %s", method, url, repr(json)[:20])
        out = self._s.request(
            method,
            url,
            json=json,
            stream=stream,
            params=params)
        # monkeypatch for iterating over the Isilon data
        out.iter_json = partial(self.iter_out, out)
        logger.debug("Results from %s status %i preview %s",
                     out.url, out.status_code, out.text[:20])
        if raise_on_error and out.status_code != requests.codes.ok:
            raise IsiApiError(out)
        return out

    # Primary calls are just wrappers around request
    get = partialmethod(request, 'GET')
    head = partialmethod(request, 'HEAD')
    post = partialmethod(request, 'POST')
    delete = partialmethod(request, 'DELETE')

    @staticmethod
    def get_resume_id(out):
        try:
            return out.json()['resume']
        except BaseException:
            return None

    @staticmethod
    def find_collection(data):
        ''' Find the collection in the json '''
        if 'resume' in data:
            for key, value in data.items():
                if isinstance(value, list):
                    return key
        if 'directory' in data:
            return 'directory'
        if 'children' in data:
            return 'children'
        if 'summary' in data:
            return 'summary'
        return None

    def iter_out(self, out, tag=None):
        ''' Page through the results on the named tag
            attempt to guess the fag if not give '''
        data = out.json()

        if not tag:
            # autodetect tag
            tag = IsiClient.find_collection(data)

        if not tag:
            yield data
            return

        # Page through results yielding the tag
        # this should be yield from but that's not py2 safe
        for page in self.page_out(out):
            # python3 only, so unwind it
            # yield from page.json()[tag]
            for item in page.json()[tag]:
                yield item

    def page_out(self, out):
        ''' helper to page results that have a resume entity '''

        # Return the input
        yield out
        resume = IsiClient.get_resume_id(out)
        try:
            url = out.url.split('?', 1)[0]
        except BaseException:
            url = out.url
        # While the input containes a resume token keep refreshing it
        # via additional get calls
        while resume:
            out = self.get(url, x_append_prefix=False, resume=resume)
            yield out
            resume = IsiClient.get_resume_id(out)


class PapiClient(object):
    ''' Basic PAPI client which will allow you to query
        api endpoints in an effecient manner '''

    def __init__(self, client):
        self.client = client
        self.papi_autoscan()

    def papi_autoscan(self):
        try:
            self.endpoints = list(
                self.client.get(
                    'platform',
                    describe='',
                    list='',
                    json='').iter_json())
            self.papi_version = max(
                version for _, version, _ in (
                    x.split(
                        '/', 2) for x in self.endpoints))
            self.cluster_config = self.get('cluster/config').json()
            logger.info(
                "Connected to PAPI backed with version %i", int(
                    self.papi_version))
        except BaseException:
            logger.exception("Unable to connect to PAPI")

    def call(self, method, endpoint, version=None, *vars, **params):
        # call the papi
        version = version if version else self.papi_version
        if not isinstance(endpoint, list):
            endpoint = [endpoint]
        return self.client.request(
            method, '/'.join(['platform', str(version)] + endpoint).format(*map(str, vars)), **params)

    get = partialmethod(call, 'GET')
    head = partialmethod(call, 'HEAD')
    post = partialmethod(call, 'POST')
    delete = partialmethod(call, 'DELETE')


lsfmt = '{mode_str} {owner:8} {group:8} {hsize:8} {mtime_val} {name}'


class NsClient(object):
    ''' Basic namespace client takes an IsiClient and the namespace
        prefix as setup '''

    def __init__(self, client, prefix):
        self.client = client
        self.prefix = prefix

    def call(self, method, path, **params):
        # call the papi
        return self.client.request(
            method, '/'.join(['namespace', self.prefix, path]), **params)

    get = partialmethod(call, 'GET')
    head = partialmethod(call, 'HEAD')
    post = partialmethod(call, 'POST')
    delete = partialmethod(call, 'DELETE')

    def scandir(self, path,
                detail=['name', 'owner', 'group',
                        'type', 'mode', 'size', 'block_size',
                        'mtime_val', 'atime_val', 'ctime_val',
                        'btime_val', 'uid', 'gid', 'id', 'nlink']):
        ''' iterate over a directory.
            workalike to os.scandir '''
        out = self.get(path, detail=','.join(detail))
        if out.headers['x-isi-ifs-target-type'] != 'container':
            raise ValueError("NOT DIRECTORY: {}".format(path))
        # py2 compatibility since no yield from
        for item in out.iter_json():
            yield item

    def walk(self, top, topdown=True, **scandir_options):
        ''' walk the directory tree
            workalike to os.walk '''
        dir_stack = [top]
        while dir_stack:
            cur = dir_stack.pop(0)
            dirs = []
            files = []
            for item in self.scandir(cur, **scandir_options):
                if 'type' in item and item['type'] == 'container':
                    dirs.append(item)
                else:
                    files.append(item)
            yield cur, dirs, files
            for item in dirs:
                dir_stack.append(os.path.join(cur, item['name']))

    @staticmethod
    def expand_dirent(entry):
        ''' Utility function to interpret the json values as python where approprate '''

        # these should be int() converted
        convert_to_int = set((
            'size',
            'block_size',
            'mtime_val',
            'atime_val',
            'ctime_val',
            'btime_val',
            'uid',
            'gid',
            'id',
            'nlink'))
        # there should be fromtimestamp() converted
        convert_to_time = set((
            'mtime_val',
            'atime_val',
            'ctime_val',
            'btime_val'))
        # this is the mapping of type to mode
        type_to_flag = {'container': 0o0040000, 'object': 0o0100000,
                        'pipe': 0o0010000, 'character_device': 0o0020000,
                        'block_device': 0o0060000, 'symbolic_link': 0o0120000,
                        'socket': 0o0140000, 'whiteout_file': 0}
        for key in convert_to_int:
            if key in entry:
                entry[key] = int(entry[key])
        for key in convert_to_time:
            if key in entry:
                entry[key] = datetime.fromtimestamp(entry[key])
        if 'size' in entry:
            entry['hsize'] = sfmt(entry['size'])
        if 'mode' in entry:
            entry['mode'] = int(entry['mode'], 8)
            try:
                entry['mode'] = entry['mode'] | type_to_flag[entry['type']]
            except BaseException:
                pass
            entry['mode_str'] = filemode(entry['mode'])

    def ll(self, path):
        ''' list a single directory '''
        for entry in self.scandir(path):
            NsClient.expand_dirent(entry)
            print(lsfmt.format(**entry))

    def llr(self, top):
        ''' list a directory recursively '''
        for path, dirs, files in self.walk(top):
            print("DIR: ", path)
            for entry in dirs:
                NsClient.expand_dirent(entry)
                print(lsfmt.format(**entry))
            for entry in files:
                NsClient.expand_dirent(entry)
                print(lsfmt.format(**entry))
