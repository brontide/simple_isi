import requests
import logging
from types import MethodType
from getpass import getpass, getuser
import sys
from http.cookiejar import LWPCookieJar
import os
    
# FIXME, this should go away once we figure out how to get the
# certificate to validate
requests.packages.urllib3.disable_warnings()

logger = logging.getLogger(__name__)

class IsiApiError(ValueError):
    def __init__(self, out):
        self.request_response = out
        try:
            data = out.json()
            ValueError.__init__(self, "Error {}/{} when connecting to url {}".format(data['errors'][0]['code'], data['errors'][0]['message'], out.url))
        except:
            ValueError.__init__(self, "URL: {} status code {}".format(out.url, out.status_code))

class IsiClient:
    # Bare bones Isilon RESTful client designed for utter simplicity

    def __init__(self, server=None, username='', password='', port=8080, verify=None):
        self._cookiejar_path = os.path.join(os.path.expanduser('~'), '.isilon_cookiejar')
        self._s = requests.Session()
        self._s.cookies = LWPCookieJar()
        try:
            self._s.cookies.load(self._cookiejar_path, ignore_discard=True, ignore_expires=True)
        except:
            pass
        self._server = server
        self._username = username
        self._password = password
        self._port = port
        self._s.verify = verify
        self.ready = False
        if len(self._s.cookies):
            logger.debug("Attempting to use cached credentials")
            length = self.session()

    @property
    def server(self):
        # Servername for Isilon
        return self._server

    @server.setter
    def server(self, value):
        if value != self.server:
            self.server = value
            self.ready = False

    @property
    def port(self):
        # Portnumber for isilon, defaults to 8080
        return self._port

    @port.setter
    def port(self, value):
        if self.port != value:
            self.port = value
            self.ready = False

    @property
    def username(self):
        # username for restful session
        return self._username

    @username.setter
    def username(self, value):
        if self.username != value:
            self._username = value
            self.ready = False

    @property
    def password(self):
        # password for connection ( getter returns dummy info )
        if self._password:
            return "*"*len(self._password)
        else:
            return "********"

    @password.setter
    def password(self, value):
        self._password = value
        self.ready = False

    @property
    def verify(self):
        # Sets requests verify flag, set to False to disable SSL verification of the connection
        return self._s.verify

    @verify.setter
    def verify(self,value):
        if self.verify != value:
            if verify == False:
                logger.warning("Connection to %s:%i proceeding without SSL verification", server, port)
            self._s.verify = value
            self.ready = False

    def session(self):
        # returns the time remaining in the session
        try:
            out = self.get('session/1/session')
            data = out.json()
            self.username = data['username']
            length = max(data["timeout_absolute"], data["timeout_inactive"])
            if length > 60:
                # good senssion
                self.ready = True
                self._s.cookies.save(self._cookiejar_path, ignore_discard=True, ignore_expires=True)
                return length
        except:
            pass
        return None

    def create_session(self):
        # attempts to authenticate with session module
        login = { 'username': self.username, 'password': self._password, 'services': ['platform', 'namespace'] }
        try:
            self.post(login, 'session/1/session')
            self.ready = True
        except:
            logger.debug("Login failure")
        return self.session()
        

    def __repr__(self):
        if self._s.auth:
            auth = "with auth of {}/{}".format(self.username, self.password)
        else:
            auth = "NO AUTHENTICATION TOKEN"
        return "IsiClient-https://{}:{} {}".format(self.server, self.port, auth) 

    def auth(self):
        # Query for interactive credentials
        
        # Are we already authed?
        length = self.session()
        if length:
            return length 

        # only works for ttys
        if not sys.stdin.isatty():
            logger.warning("Session not ready and no interactive credentials, this will probably fail")
            return None

        # Start interactive login
        print("Please enter credentials for Isilon https://{}:{}\nUsername (CR={}): ".format(self.server, self.port, getuser()), file=sys.stderr, flush=True, end='')
        username = input()
        if username == "":
            username = getuser()
        print("Password : ", file=sys.stderr, flush=True, end='')
        password = getpass('')

        self.username = username
        self.password = password

        return self.create_session()

    def get(self, path, append_prefix=True, raise_on_error=True, stream=False, **params):
        # Perform a RESTful get on the Isilo
        # 
        if append_prefix:
            url = 'https://{}:{}/{}'.format(self.server, self.port, path)
        else:
            url = path
        logger.debug("GET %s", url)
        out = self._s.get(url, stream=stream, params=params)
        logger.debug("Results from %s status %i preview %s", out.url, out.status_code, out.text[:20])
        if raise_on_error and out.status_code != requests.codes.ok:
            raise IsiApiError(out)
        return out

       
    def post(self, json_data, path, append_prefix=True, raise_on_error=True, stream=False, **params):
        # Perform a RESTful post on the Isilo
        # 
        if append_prefix:
            url = 'https://{}:{}/{}'.format(self.server, self.port, path)
        else:
            url = path
        logger.debug("PUT %s <- %s", url, repr(json_data)[:20])
        out = self._s.post(url, json=json_data, stream=stream, params=params)
        logger.debug("Results from %s status %i preview %s", out.url, out.status_code, out.text[:20])
        if raise_on_error and out.status_code != requests.codes.ok:
            raise IsiApiError(out)
        return out

    @staticmethod
    def get_resume_id(out):
        try:
            return out.json()['resume']
        except:
            return None

    @staticmethod
    def find_collection(data):
        ''' Find the collection in the json '''
        if 'resume' in data:
            for key, value in data.items():
                if isinstance( value, list ):
                    return key
        if 'directory' in data:
            return 'directory'
        if 'children' in data:
            return 'children'
        if 'summary' in data:
            return 'summary'
        return None

    def iter_out(self, out, tag=None):
        # Page through the results on the named tag
        # attempt to guess the fag if not give
        data = out.json()

        if not tag:
            # autodetect tag
            tag = IsiClient.find_collection(data)

        if not tag:
            yield data
            return

        # Page through results yielding the tag
        for page in self.page_out(out):
            yield from page.json()[tag]

    def page_out(self, out):
        # helper to page results that have a resume entity
        yield out
        resume = IsiClient.get_resume_id(out)
        while resume:
            out = self.get(out.url, append_prefix=False, resume=resume)
            yield out
            resume = IsiClient.get_resume_id(out)
   

class PAPIClient:

    def __init__(self, client):
        self.client = client
        self.function_lookup = {}
        self.papi_autoscan()

    def papi_autoscan(self):
        try:
            self.endpoints = list(self.get('', raw=True, describe='', list='', json='').fetchall())
            self.papi_version = max( version for _, version, _ in (x.split('/',2) for x in self.endpoints) )
            self.cluster_config = self.get('cluster/config').json()
            logger.info("Connected to PAPI backed with version %i", int(self.papi_version))
        except:
            logger.exception("Unable to connect to PAPI")


    def get(self, path, *vars, raw=False, version=-1, **params):
        # call the papi
        if version == -1 and not raw:
            version = self.papi_version
        if not isinstance(path, list):
            path = [path]
        if raw:
            out = self.client.get('/'.join(['platform']+path).format(*map(str,vars)), **params)
        else:
            out = self.client.get('/'.join(['platform', str(version)]+path).format(*map(str,vars)), **params)
        return self.patch(out)

    def patch(self, out):
        # Monkeypath the requests return to facilitate
        # fetching and iterating over results
        def fetchfirst(out, tag=None):
            data = out.json()
            if not tag:
                tag = IsiClient.find_collection(data)
            if not tag:
                return data

            ret = data[tag]
            if isinstance( ret, list):
                return ret[0]
            else:
                return ret

        def fetchall(out, tag=None):
            yield from self.client.iter_out(out,tag)

        if out.headers['content-type'] == 'application/json':
            out.fetchfirst = MethodType(fetchfirst, out)
            out.fetchall = MethodType(fetchall, out)
        return out

