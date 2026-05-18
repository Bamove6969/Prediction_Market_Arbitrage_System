import urllib.request
import json
try:
    x = json.loads(urllib.request.urlopen("http://127.0.0.1:4040/api/requests/http").read().decode())
    for r in x["requests"]:
        print(f"{r['request']['method']} {r['request']['uri']} {r['response']['status_code']}")
except Exception as e:
    print(e)
