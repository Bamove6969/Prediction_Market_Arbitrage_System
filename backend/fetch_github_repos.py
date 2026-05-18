import urllib.request
import json
import time

def fetch_repos(topic):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/search/repositories?q=topic:{topic}&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                if 'items' not in data or len(data['items']) == 0:
                    break
                repos.extend(data['items'])
                page += 1
                time.sleep(1) # rate limit prevention
        except Exception as e:
            print(f"Error fetching page {page} for {topic}: {e}")
            break
    return repos

all_repos = []
all_repos.extend(fetch_repos('prediction-markets'))
all_repos.extend(fetch_repos('polymarket'))
all_repos.extend(fetch_repos('kalshi'))

# Deduplicate
seen = set()
unique_repos = []
for r in all_repos:
    if r['id'] not in seen:
        seen.add(r['id'])
        unique_repos.append(r)

# Sort by stars
unique_repos.sort(key=lambda x: x['stargazers_count'], reverse=True)

print(f"Total unique repos found tying into prediction markets: {len(unique_repos)}\n")

print("--- TOP REPOS BY STARS ---")
for r in unique_repos[:50]:
    desc = r['description'] or 'No description'
    print(f"⭐ {r['stargazers_count']} - {r['full_name']}")
    print(f"   URL: {r['html_url']}")
    print(f"   Desc: {desc}")
    print(f"   Topics: {', '.join(r['topics'])}")
    print("-" * 50)
