"""#942 native-image gate, run only against the smoke test's disposable container."""

import json
import os
import subprocess
import sys


expected = {
    key: os.environ["STREAMVAULT_EXPECTED_" + key.upper()]
    for key in ("version", "branch", "commit_sha", "build_date")
}
container = sys.argv[1]
labels = json.loads(
    subprocess.check_output(
        ["docker", "inspect", "--format", "{{json .Config.Labels}}", container],
        text=True,
    )
)
for field, label in {
    "version": "version",
    "branch": "ref.name",
    "commit_sha": "revision",
    "build_date": "created",
}.items():
    assert labels["org.opencontainers.image." + label] == expected[field], field
assert (
    labels["org.opencontainers.image.source"]
    == "https://github.com/Serph91P/StreamVault"
)

# Standard HTTP, real bootstrap/login/session middleware and the production router.
# No provider account, browser shim, injected response or emitted session value.
probe = r"""
import http.client,json,os,sys
from http.cookies import SimpleCookie
from urllib.parse import urlsplit
expected=json.loads(sys.argv[1])
for field,value in expected.items():
    assert os.environ['STREAMVAULT_'+field.upper()]==value, field
host=urlsplit(os.environ['BASE_URL']).netloc
connection=http.client.HTTPConnection('127.0.0.1',7000,timeout=15)
headers={'Host':host,'Content-Type':'application/json','Origin':os.environ['BASE_URL']}
body=json.dumps({'username':'image_probe842','password':'Synthetic842!test-only'})
connection.request('POST','/auth/setup',body,headers)
response=connection.getresponse()
response.read()
if response.status==400:
    connection.request('POST','/auth/login',body,headers)
    response=connection.getresponse()
    response.read()
assert response.status==200, 'synthetic image bootstrap/login failed: '+str(response.status)
cookie=SimpleCookie()
for key,value in response.getheaders():
    if key.lower()=='set-cookie': cookie.load(value)
assert 'session' in cookie or 'access_token' in cookie, 'no authenticated cookie'
identity_cookie='; '.join(key+'='+cookie[key].value for key in ('session','access_token') if key in cookie)
connection.request('GET','/api/version',headers={'Host':host,'Cookie':identity_cookie})
response=connection.getresponse()
assert response.status==200, 'authenticated version failed: '+str(response.status)
actual=json.loads(response.read())
connection.close()
for field,value in expected.items():
    assert actual[field]==value, field
print(json.dumps({field:actual[field] for field in expected},sort_keys=True))
"""
result = subprocess.check_output(
    ["docker", "exec", container, "python", "-c", probe, json.dumps(expected)],
    text=True,
)
assert json.loads(result) == expected
print("Native OCI/ENV/authenticated /api/version identity PASS: " + result.strip())
