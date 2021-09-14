import asyncio
import websockets
import sqlite3
import imagehash
import requests
from PIL import Image
import json
import os
from bs4 import BeautifulSoup
import random
from google.cloud import vision

from time import sleep

MAXNUMOFPAGES = 3

NONSUSPECT = 0
NOINFO = 1
SUSPECT = 2

scamwordlist = [
    'scam',
    'fraud'
]

# taken from https://github.com/ashchristopher/python-tineye/blob/master/__init__.py
USER_AGENTS = [
    'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)',
    'Mozilla/4.61 [en] (X11; U; ) - BrowseX (2.0.0 Windows)',
    'Mozilla/5.0 (Macintosh; U; Intel Mac OS X; en; rv:1.8.1.6) Gecko/20070809 Camino/1.5.1',
    'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_5_7; en-US) AppleWebKit/531.0 (KHTML, like Gecko) Chrome/3.0.183 Safari/531.0',
    'Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/525.19 (KHTML, like Gecko) Chrome/1.0.154.53 Safari/525.19',
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/525.19 (KHTML, like Gecko) Chrome/1.0.154.36 Safari/525.19',
    'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8) Gecko/20051111 Firefox/1.5 BAVM/1.0.0',
    'Mozilla/5.0 (X11; U; Linux armv61; en-US; rv:1.9.1b2pre) Gecko/20081015 Fennec/1.0a1',
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.1) Gecko/20090624 Firefox/3.5 (.NET CLR 3.5.30729)',
    'Mozilla/5.0 (X11; U; OpenBSD i386; en-US; rv:1.8.1.14) Gecko/20080821 Firefox/2.0.0.14',
    'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; WOW64; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)',
    'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; Meridio for Excel 5.0.251; Meridio for PowerPoint 5.0.251; Meridio for Word 5.0.251; Meridio Protocol; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.04506.30; .NET CLR 3.0.04506.648; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729)',
    'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; Business Everywhere 7.1.2; GTB6; .NET CLR 1.0.3705; .NET CLR 1.1.4322; Media Center PC 4.0)',
    'Mozilla/1.22 (compatible; MSIE 2.0; Windows 95)',
]

# authenticate google vision API
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/alfgram/scamidentifier-e3ceaa57e230.json'

# Start google vision client
client = vision.ImageAnnotatorClient()

# Connect to scam database
connection = sqlite3.connect('user_database.db')
cursor = connection.cursor()


def gathermatches_tineye(image_url):
    searchurl = "https://tineye.com/result_json/"
    r = requests.post(searchurl, data={'url' : image_url}, headers={"User-Agent": random.choice(USER_AGENTS)})
    query_string = json.loads(r.content)['query_hash']
    matches_url = searchurl + query_string + "?sort=score&order=desc&page=1"
    response = requests.get(matches_url)
    try:
        matches = json.loads(response.content)['matches']
        pagelist = []
        for match in matches[:MAXNUMOFPAGES]:
            pagelist.append(match['backlinks'][0]['backlink'])
        return pagelist
    except Exception as e:
        return



def geturl_yandex(image_url):
    # adaptation from https://newbedev.com/reverse-search-an-image-in-yandex-images-using-python
    filePath = "/home/alfgram/test.jpg"
    searchUrl = 'https://yandex.com/images/search'
    # save image to file to be posted
    with open(filePath, "wb") as file:
        response = requests.get(image_url)
        file.write(response.content)
    files = {'upfile': ('blob', open(filePath, 'rb'), 'image/jpeg')}
    params = {'rpt': 'imageview', 'format': 'json', 'request': '{"blocks":[{"block":"b-page_type_search-by-image__link"}]}'}
    response = requests.post(searchUrl, params=params, files=files)
    try:
        query_string = json.loads(response.content)['blocks'][0]['params']['url']
    except Exception as e:
        return
    url = searchUrl + '?' + query_string
    return url


def gathermatches_yandex(image_url):
    search_url = geturl_yandex(image_url)
    if (not search_url):
        return
    page = requests.get(search_url)
    if (page.status_code != 200):
        print("could not scrape page")
        return
    soup = BeautifulSoup(page.content, 'html.parser')
    # If no matching images found this class is present
    if soup.find("div", {"class": "CbirOtherSizes-EmptyMessage"}):
        return

    # Extract list of matching pages
    pageheader = soup.find("section", {"class": "CbirItem CbirOtherSizes"})
    matchingpages = pageheader.findAll('a', {"tone": "gray"}, {"rel": "noopener"})
    numofmatchingpages = len(matchingpages)
    matchingpagelinks = soup.findAll('a', {"class": "Link Link_theme_normal"})
    pagelist = []
    for link in matchingpagelinks[:min(numofmatchingpages, MAXNUMOFPAGES)]:
        pagelist.append(link['href'])
    return pagelist

def insertintodatabase(profile_details, matching_page_url, is_fraudulent):
    phashcode = get_phash_from_url(profile_details['image_url'])
    cursor.execute("INSERT INTO scam_list(name,image_source_url,image_url,phash,is_fraudulent) VALUES(?,?,?,?,?)", (profile_details["name"], matching_page_url, profile_details["image_url"], str(phashcode), is_fraudulent))
    connection.commit()


def gathermatches_googlevision(image_url):
    # Send url to google vision API
    image = vision.Image()
    image.source.image_uri = image_url
    # Receive results and check if any matching pages
    webdetectionresults = client.web_detection(image=image).web_detection
    # if there are pages with matching image
    if webdetectionresults.pages_with_matching_images:
        pagelist = []
        for page in webdetectionresults.pages_with_matching_images[:MAXNUMOFPAGES]:
            pagelist.append(page.url)
        return pagelist

def analyse_page(profile_details, matching_page_url):
    try:
        page = requests.get(matching_page_url,headers={"User-Agent": random.choice(USER_AGENTS)})
    except requests:
        print("NO INFO: could not get page " + str(profile_details['image_url']))
        return NOINFO
    page_text = page.text.lower()
    if any(scamword in page_text for scamword in scamwordlist): 
        print("SCAM WORD at: " + matching_page_url)
        return SUSPECT
    if profile_details['name']:
        if profile_details['name'].lower() in page_text:
            print("NAME MATCH at " +  matching_page_url)
            return NONSUSPECT
        else:
            print("NAME MISMATCH at " +  matching_page_url)
            return SUSPECT
    print("NO INFO on " + matching_page_url)
    return NOINFO

def verifyprofile(profile_details):
    scamlistresult = checkscamlist(profile_details['image_url'])
    if scamlistresult:
        if ((scamlistresult[4] == True) or (scamlistresult[0].lower() != profile_details['name'].lower())): 
            return make_alert_HTML(warning_message, scamlistresult[1])

    # Collect all matching pages from the 3 search engines
    matchingurls = []
    
    googlematches = gathermatches_googlevision(profile_details['image_url'])
    if googlematches:
        matchingurls.extend(googlematches)

    yandexmatches = gathermatches_yandex(profile_details['image_url'])
    if yandexmatches:
        matchingurls.extend(yandexmatches)

    tineyematches = gathermatches_tineye(profile_details['image_url'])
    if tineyematches:
        matchingurls.extend(tineyematches)

    if not matchingurls:
        return no_info_message

    suspect_pages = []
    nonsuspect_pages = []    
    for matchingurl in matchingurls:
        outcome = analyse_page(profile_details, matchingurl)
        if (outcome == SUSPECT):
            print("dodgy: " + matchingurl)
            suspect_pages.append(matchingurl)
        if (outcome == NONSUSPECT):
            print("good: " + matchingurl)
            nonsuspect_pages.append(matchingurl)
    if suspect_pages:
        insertintodatabase(profile_details, matchingurl, True)
        return make_alert_HTML(warning_message, suspect_pages)
    if nonsuspect_pages:
        insertintodatabase(profile_details, matchingurl, False)
        return make_alert_HTML(non_fraudulent_message, nonsuspect_pages)
    return no_info_message

def make_alert_HTML(message_HTML, url_list):
    new_alert = message_HTML
    soup = BeautifulSoup(new_alert, 'html.parser')
    hyperlink_element = "<br> <a href=\"{url_string}\">{url_string}</a>"
    if isinstance(url_list, list):
        for url in url_list:
            warning = BeautifulSoup(hyperlink_element.format(url_string = url), 'html.parser')
            soup.find(id='FaceCheck_alert').append(warning)
    else:
        warning = BeautifulSoup(hyperlink_element.format(url_string = url_list), 'html.parser')
        soup.find(id='FaceCheck_alert').append(warning)
    return str(soup)

def get_phash_from_url(image_url):
    img = Image.open(requests.get(image_url, stream=True).raw)
    return imagehash.phash(img)

def checkscamlist(image_url):
    cursor.execute("SELECT * FROM scam_list WHERE phash =?", (str(get_phash_from_url(image_url)),))
    matching_profile = cursor.fetchone()
    return matching_profile

async def server(websocket, path):
    while True:
        response = await websocket.recv()
        try:
            profile_details = json.loads(response)
            HTML_alert = verifyprofile(profile_details)
            await websocket.send(HTML_alert)
        except Exception as e:
            print("client disconnected: " + str(e)) 


# These alert messages are made using an adaptation of code taken from https://www.w3schools.com/howto/howto_js_alert.asp
no_info_message = """
    <head>
<style>
.alert {
  padding: 20px;
  background-color: yellow;
  color: black;
  z-index:100; 
  position: fixed;
  bottom: 0px;
}

.closebtn {
  margin-left: 15px;
  color: black;
  font-weight: bold;
  float: right;
  font-size: 22px;
  line-height: 20px;
  cursor: pointer;
  transition: 0.3s;
  z-index: -1;
}

.closebtn:hover {
  color: white;
}
</style>
</head>
<body>
<div id='FaceCheck_alert', class="alert">
  <span class="closebtn" onclick="this.parentElement.style.display='none';">&times;</span> 
  FaceCheck couldn't find any information to determine whether this profile could be potentially fraudulent. 
</div>
</body>
"""

non_fraudulent_message = """
    <head>
<style>
.alert {
  padding: 20px;
  background-color: green;
  color: white;
  z-index:100; 
  position: fixed;
  bottom: 0px;
}

.closebtn {
  margin-left: 15px;
  color: white;
  font-weight: bold;
  float: right;
  font-size: 22px;
  line-height: 20px;
  cursor: pointer;
  transition: 0.3s;
  z-index: -1;
}

.closebtn:hover {
  color: black;
}
</style>
</head>
<body>
<div id='FaceCheck_alert', class="alert">
  <span class="closebtn" onclick="this.parentElement.style.display='none';">&times;</span> 
  FaceCheck hasn't found any information to suggest this profile is fraudulent. All other occurrences of the picture on this profile appear to be linked to the name listed on this profile. This does not guarantee that the profile is not fraudulent, please investigate the following links:    
</div>
</body>
"""

warning_message = """
<head>
<style>
.alert {
  padding: 20px;
  background-color: #f44336;
  color: white;
  z-index:100; 
  position: fixed;
  bottom: 0px;
}

.closebtn {
  margin-left: 15px;
  color: white;
  font-weight: bold;
  float: right;
  font-size: 22px;
  line-height: 20px;
  cursor: pointer;
  transition: 0.3s;
  z-index: -1;
}

.closebtn:hover {
  color: black;
}
</style>
</head>
<body>
<div id='FaceCheck_alert', class="alert">
  <span class="closebtn" onclick="this.parentElement.style.display='none';">&times;</span> 
  <strong>WARNING!</strong> This profile is potentially fraudulent. The profile image was connected to the following suspicious pages:
</div>
</body>

"""

asyncio.get_event_loop().run_until_complete(
    websockets.serve(server, 'localhost', 8700))
asyncio.get_event_loop().run_forever()


