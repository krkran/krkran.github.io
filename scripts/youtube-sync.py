#!/usr/bin/env python3
"""Keep portfolio/videos.json in step with the KRNBRY Studio YouTube channel.

Runs a few times a day via .github/workflows/youtube.yml. No API key needed:
it reads YouTube's public feed. New videos are added, old ones are kept (the
feed only lists the latest 15), and Shorts are marked so the site can show
them in their own row. Pinning, series and hiding live in portfolio/films.json,
which this script never touches."""
import json, re, sys, time, urllib.request, xml.etree.ElementTree as ET

PATH = 'portfolio/videos.json'
UA = {'User-Agent': 'Mozilla/5.0 (KRNBRY Studio site sync)', 'Accept-Language': 'en'}
NS = {'a': 'http://www.w3.org/2005/Atom', 'yt': 'http://www.youtube.com/xml/schemas/2015',
      'media': 'http://search.yahoo.com/mrss/'}

def get(url, tries=(0, 5, 20)):
    last = None
    for wait in tries:                    # YouTube sometimes turns GitHub's servers away; try a few times
        time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
            print(f'  attempt failed ({url.split("?")[1][:40]}): {e}')
    raise last

def give_up(why):
    # never fail the run: keep the list as it is and try again next time
    print(f'Skipped this time: {why}. The films list was left as it is.')
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

# two ways in: the channel feed, then the channel's "uploads" playlist feed
root = None
for url in (f'https://www.youtube.com/feeds/videos.xml?channel_id={cid}',
            f'https://www.youtube.com/feeds/videos.xml?playlist_id=UU{cid[2:]}'):
    try:
        root = ET.fromstring(get(url)); break
    except Exception as e:
        print(f'  feed not available: {e}')
if root is None:
    give_up('YouTube did not send the video list')

fresh = []
for e in root.findall('a:entry', NS):
    vid = e.findtext('yt:videoId', '', NS)
    if not vid:
        continue
    link = e.find('a:link', NS)
    href = link.get('href', '') if link is not None else ''
    fresh.append({
        'id': vid,
        'title': e.findtext('a:title', '', NS),
        'published': e.findtext('a:published', '', NS)[:10],
        'description': (e.findtext('media:group/media:description', '', NS) or '').strip()[:400],
        'short': '/shorts/' in href,
    })

try:
    old_text = json.dumps(json.load(open(PATH)), sort_keys=True)
except Exception:
    old_text = ''
# merge: fresh details win, older videos that dropped off the feed are kept
by_id = {v['id']: v for v in data.get('videos', []) if v.get('id')}
for v in fresh:
    by_id[v['id']] = {**by_id.get(v['id'], {}), **v}
videos = sorted(by_id.values(), key=lambda v: v.get('published', ''), reverse=True)
data['videos'] = videos
if json.dumps(data, sort_keys=True) != old_text:
    open(PATH, 'w').write(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(f'Updated: {len(videos)} videos ({sum(1 for v in videos if v.get("short"))} Shorts)')
else:
    print('No change')
