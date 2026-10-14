#!/usr/bin/env python3
"""Refresh portfolio/videos.json from the KRNBRY Studio YouTube channel.
Runs daily via .github/workflows/youtube.yml. No API key needed: it reads
YouTube's public RSS feed. Set "channelId" in videos.json to skip the lookup."""
import json, re, sys, time, urllib.request, xml.etree.ElementTree as ET

PATH = 'portfolio/videos.json'
UA = {'User-Agent': 'Mozilla/5.0 (KRNBRY Studio site sync)', 'Accept-Language': 'en'}

def get(url):
    last = None
    for wait in (0, 5, 20, 60):          # YouTube sometimes turns GitHub's servers away; try a few times
        time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            print(f'  attempt failed: {e}')
    raise last

def give_up(why):
    # never fail the run: keep the films list as it is and try again tomorrow
    print(f'Skipped today: {why}. The films list was left as it is.')
    sys.exit(0)

try:
    data = json.load(open(PATH))
except Exception:
    data = {}
handle = data.get('channel', 'krnbrystudio').lstrip('@')
data.setdefault('channel', handle)
data.setdefault('channelUrl', f'https://www.youtube.com/@{handle}')

cid = data.get('channelId')
if not cid:
    try:
        page = get(f'https://www.youtube.com/@{handle}')
    except Exception as e:
        give_up(f'could not reach the channel page ({e})')
    m = (re.search(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', page)
         or re.search(r'"(?:externalId|channelId)":"(UC[\w-]{22})"', page))
    if not m:
        give_up(f'could not find a channel ID for @{handle}')
    cid = m.group(1)
    data['channelId'] = cid

ns = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
      'media': 'http://search.yahoo.com/mrss/'}
try:
    root = ET.fromstring(get(f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}'))
except Exception as e:
    give_up(f'YouTube did not send the video list ({e})')
videos = []
for e in root.findall('a:entry', ns):
    vid = e.findtext('yt:videoId', '', ns)
    link = e.find('a:link', ns)
    href = link.get('href', '') if link is not None else ''
    if not vid or '/shorts/' in href:
        continue  # keep Shorts out of the films page
    videos.append({
        'id': vid,
        'title': e.findtext('a:title', '', ns),
        'published': e.findtext('a:published', '', ns)[:10],
        'description': (e.findtext('media:group/media:description', '', ns) or '').strip()[:400],
    })

try:
    old = json.dumps(json.load(open(PATH)), sort_keys=True)
except Exception:
    old = ''
data['videos'] = videos
new = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
if json.dumps(data, sort_keys=True) != old:
    open(PATH, 'w').write(new)
    print(f'Updated: {len(videos)} videos')
else:
    print('No change')
