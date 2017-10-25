Super Simple Isilon Rest Library
================================

Both the comand line tool `isicmd` and the libraris are designed for utter simplicity and
comprehensibility.  Where possible we do as little as possible to get you talking with the
PAPI on the host.

isicmd - command line
---------------------

**INSTALL**

::

    pip3 install simple_isi

1. Create a isilon.yaml in the cwd or ~/.isilon_yaml with your isilon host settings
2. (OPTIONAL) Install jq for more advanced post processing

That's it.

.. code-block:: console

    $ isicmd -h
    usage: isicmd [-h] [--raw] [--verbose] [--server SERVER] [--tag TAG]
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
                  --tag TAG        Parse and return tag from results with resume support


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

