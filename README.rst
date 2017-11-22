Super Simple Isilon Rest Library
================================

Both the comand line tool `isicmd` and the libraris are designed for utter simplicity and
comprehensibility.  Where possible we do as little as possible to get you talking with the
PAPI on the host.

WHY?
---

Why would I write this when there is an official sdk?  Because I just needed one thing and
I felt like the official API was very heavyweight and lacked the finess of that some quick
python could acheive.  What started as some helper functions that I wrote quickly became
a class and that spawned additional features. 

**Standout feature**

- iterators:  A successful call can be iterated over with `.iter_json()` and it will
  automatically re-call the API if needed
- session cookies:  No need to hardcode credentials this utiliy will call for credentials
  when needed, if needed.  If there is a valid isisessid cookie stashed it will not
  prompt
- structures as dict:  Since we're just iterative over json the values returned are all
  python dicts for easy manipulation.
- Not bound to a particilar version of the platform.  This module should work against any
  version of the api as long as the endpoints are not signifigantly different.
- Python 2/3 compatible:  I'm developing in python 3 and presuming it's not a total hack
  job I'm patching to make sure it runs on python 2 as well.


Python usage
------------

.. code-block::
    from __future__ import print_function

    import logging
    logger = logging.getLogger()
    logging.basicConfig(
                level=20,
                format='%(relativeCreated)6.1f %(processName)12s: %(levelname).1s %(module)8.8s:%(lineno)-4d %(message)s')

    # For py2 interactive, ugly hack to enable utf-8 at the repl
    try:
        import sys
        reload(sys)
        sys.setdefaultencoding('utf-8')
    except:
        pass

    # Library code
    import simple_isi

    # disable warnings if your host doesn't have a full SSL
    simple_isi.quiet()

    # Create a client session and make it ready for actions 
    client = simple_isi.IsiClient(server='ritstor.rit.albany.edu', verify=False)
    # Prompt for creds if needed
    client.is_ready()

    # Create a PAPI session
    papi = simple_isi.PapiClient(client)
    # Get first quota
    print(next(papi.get('quota/quotas').iter_json()))
    # Get first accounting quota
    print(next(papi.get('quota/quotas', enforced=False).iter_json()))

    # Create a NS client and list some directories
    # the ns object has scandir and walk workalikes
    ns = simple_isi.NsClient(client, 'ifs')
    ns.ll('testing')
    ns.llr('primary/homes/ew2193/testing')


isicmd - command line
---------------------

**INSTALL**

::

    pip install simple_isi

1. Create a isilon.yaml in the cwd or ~/.isilon_yaml with your isilon host settings
2. (OPTIONAL) Install jq for more advanced post processing

That's it.

.. code-block:: console

    $ isicmd -h
    usage: isicmd [-h] [--raw] [--verbose] [--server SERVER] [--noverify]
                  endpoint [paramaters [paramaters ...]]

                  positional arguments:
                  endpoint         PAPI endpoint
                  paramaters       endpoint paramters

                 optional arguments:
                  -h, --help       show this help message and exit
                  --raw            Pass json through, no resume support
                  --verbose, -v
                  --server SERVER  server name
                  --noverify       Turn off SSL verification


Some examples of the isicmd::

    $ isicmd 'cluster/config' | jq . | head -n 9
     204.1  MainProcess: W      api:29   Connection to MYCLUSTER:8080 proceeding without SSL verification
    [
      {
          "description": "Storage Cluster",
          "devices": [
            {
                "devid": 9,
                "guid": "000e1e83d3f05cf388585d00907d2cc743b4",
                "is_up": true,
                "lnn": 1

    $ isicmd 'quota/quotas' | jq 'sort_by(.path)' | head                                                                                                                              
     215.0  MainProcess: W      api:29   Connection to MYCLUSTER:8080 proceeding without SSL verification
     [
       {
       "container": false,
       "enforced": false,
       "id": "BQBbAQEAAAAAAAAAAAAAQBsDAAAAAAAA",
       "include_snapshots": false,
       "linked": null,
       "notifications": "default",
       "path": "/ifs/backup",
       "persona": null,

If you need to pass get options you can just type them out on the command line::

    $ isicmd 'quota/quotas' exceeded=true | jq 'sort_by(.path)' | head
     198.8  MainProcess: W      api:29   Connection to MYCLUSTER:8080 proceeding without SSL verification
     [
       {
       "container": true,
       "enforced": true,
       "id": "QlzoFQEAAAAAAAAAAAAAQEoEAAAAAAAA",
       "include_snapshots": false,
       "linked": null,
       "notifications": "default",
       "path": "/ifs/primary/homes/xxxxxxxxxx",
       "persona": null,

You can even get a listing of all endpoints::

    $ isicmd '' describe list all | jq 'sort' | head
     205.1  MainProcess: W      api:29   Connection to MYCLUSTER:8080 proceeding without SSL verification
     [
       "/3/antivirus/policies",
       "/3/antivirus/policies/<NAME>",
       "/3/antivirus/quarantine/<PATH+>",
       "/3/antivirus/reports/scans",
       "/3/antivirus/reports/scans/<ID>",
       "/3/antivirus/reports/threats",
       "/3/antivirus/reports/threats/<ID>",
       "/3/antivirus/scan",
       "/3/antivirus/servers",

And even get online help for any endpoing::

    $ isicmd 'antivirus/scan' describe  | head -n 13
     198.1  MainProcess: W      api:29   Connection to MYCLUSTER:8080 proceeding without SSL verification
     Resource URL: /platform/3/antivirus/scan

     Overview: This resource allows a client to run an anitvirus scan on a
               single file.

     Methods: POST

     ********************************************************************************

     Method POST: Manually scan a file.

     URL: POST /platform/3/antivirus/scan

     There are no query arguments for this method.

