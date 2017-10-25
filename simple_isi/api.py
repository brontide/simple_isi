import requests
import logging
from types import MethodType
from getpass import getpass
import sys
    
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

    def __init__(self, server, auth=None, port=8080, verify=None):
        self._s = requests.Session()
        if auth:
            self._s.auth = auth
        if verify == False:
            logger.warning("Connection to %s:%i proceeding without SSL verification", server, port)
        if verify != None:
            self._s.verify = verify
        self.server = server
        self.port = port

    def __repr__(self):
        if self._s.auth:
            auth = "with auth of {}/{}".format(self._s.auth[0], "*"*len(self._s.auth[1]))
        else:
            auth = "NO AUTHENTICATION TOKEN"
        return "IsiClient-https://{}:{} {}".format(self.server, self.port, auth) 

    def auth(self):
        # Query for interactive credentials

        # only works for ttys
        if not sys.stdin.isatty():
            return
        print("Please enter credentials for Isilon https://{}:{}\nUsername : ".format(self.server, self.port), file=sys.stderr, flush=True, end='')
        username = input()
        print("Password : ", file=sys.stderr, flush=True, end='')
        password = getpass('')

        self._s.auth = (username, password)

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

       
    def put(self, json_data, path, append_prefix=True, raise_on_error=True, stream=False, **params):
        # Perform a RESTful put on the Isilo
        # 
        if append_prefix:
            url = 'https://{}:{}/{}'.format(self.server, self.port, path)
        else:
            url = path
        logger.debug("PUT %s <- %s", url, repr(json_data)[:20])
        out = self._s.put(url, json=json_data, stream=stream, params=params)
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

