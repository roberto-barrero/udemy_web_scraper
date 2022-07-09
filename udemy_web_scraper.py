from __future__ import print_function
import time, re, os, sys, io

## SELENIUM IMPORTS
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

## GOOGLE DRIVE IMPIRTS
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.http import MediaFileUpload

## --------------------  GOOGLE DRIVE API --------------------

# Copied from Google Drive's tutorial. Only modified the required parameter.

SCOPES = ['https://www.googleapis.com/auth/drive.metadata', 'https://www.googleapis.com/auth/drive'] # Change readonly


# CREATIVE NAME FOR THE DATABASE. The database file stores the identifiers of all Promodescuentos posts about
# Udemy courses than have already been redeemed / checked.
database = 'database.txt'

"""Shows basic usage of the Drive v3 API.
Prints the names and ids of the first 10 files the user has access to.
"""
creds = None
# The file token.pickle stores the user's access and refresh tokens, and is
# created automatically when the authorization flow completes for the first
# time.
if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

service = build('drive', 'v3', credentials=creds)

##  DOWNLOAD DATABASE
file_id = '*********************' #Specific file ID for the database on my Google Drive.
request = service.files().get_media(fileId=file_id)
fh = io.BytesIO()
x = open(database, 'wb')
downloader = MediaIoBaseDownload(x, request)
done = False
while done is False:
    status, done = downloader.next_chunk()
    print("Download", int(status.progress() * 100))
x.close()

##  --------------------  REGEXES  --------------------
##    These are used to search Promodescuentos's posts and determine which ones talk about
##    Udemy discounts / promo codes, and also to retrieve the posts ID from the URL

regex = re.compile('udemy\.com/course/(.*)/')
regexU = re.compile('/thread/(.*)')
regexV = re.compile('(varios|cursos|lista|etc)', re.I)
regexL = re.compile('.*-(\d\d\d\d\d\d)')

##  -------------------- WEB SCRAPING  --------------------
##  INITIALIZE WEB SCRAPER
browser = webdriver.Chrome()
browser.maximize_window()

##  PROMODESCUENTOS LOGIN
browser.get('https://www.promodescuentos.com/search?q=Udemy')
time.sleep(3) # Manual wait for the page to load. Not the best practice.
browser.find_element_by_css_selector('a.test-loginButton').click()
time.sleep(2)
username = browser.find_element_by_name('identity')
username.send_keys('')                                 ## Sensitive
browser.find_element_by_name('password').send_keys('')       ## Sensitive
time.sleep(0.3)
browser.find_element_by_name('form_submit').click()
time.sleep(5)

##  LOAD ALL POSTS
##    This section scrolls to the end of the page. Promodescuentos's website dynamically loads more posts
##    when the bottom is reached, so this section reaches the bottom of the page twice, which is enough to load all 
##    posts, based on my experience with the number of active posts.

root = browser.find_element_by_tag_name('html')
root.send_keys(Keys.END)
time.sleep(2)
root.send_keys(Keys.HOME)
time.sleep(2)
root.send_keys(Keys.END)
time.sleep(5)

##  GET PROMODESCUNTOS URLS
##    This section searches the post for the hyperlinks to the actual Udemy Course(s) URLs that the post talks about.
coupons = browser.find_elements_by_css_selector('.cept-vcb')
deals = browser.find_elements_by_css_selector('.cept-dealBtn')
varios = browser.find_elements_by_css_selector('.thread-title--card')
varios2 = [v for v in varios if regexV.search(v.get_attribute('innerHTML'))]

urls = []
variosLinks = []

##  LOAD DATABASE
##    This section determines if a URL has been already visited.
file = open(os.path.join(sys.path[0], database), 'r')
visited = file.read().split(",")
file.close()

##  RETREIVE URLS
for coupon in coupons:
    urls.append(coupon.get_attribute('href'))

for deal in deals:
    urls.append(deal.get_attribute('href'))

for vario in varios2:
    variosLinks.append(vario.get_attribute('href'))

##  CHECK FOR VISITED
urls2 = [i for i in urls if regexU.search(i).group(1) not in visited]
urls3 = [i for i in urls if regexU.search(i).group(1) not in visited]
variosLinks2 = [v for v in variosLinks if regexL.search(v).group(1) not in visited]

##  LOOK FOR COURSES IN DESCRIPTION
##    Because of the way Promodescuentos's posts work, only one course can be directly referenced, so sometimes
##    users will link all remaining promos / discounts in a signle post, using the post's description to list all
##    the courses. This section takes into account this situation and searches for Udemy hyperlinks in the post 
##    description.

for link in variosLinks2:
    browser.get(link)
    time.sleep(5)
    possibleLinks = browser.find_elements_by_css_selector('div.cept-description-container a')
    print(str(len(possibleLinks)) + ' cursos encontrados.')
    for p in possibleLinks:
        urls2.append(p.get_attribute('href'))
    
##  NO NEW COURSES
##    If no new courses (that is, courses that have not been redeemed) are found, the script ends.
if len(urls2) < 1:
    print("No new free courses")
    browser.quit()
    quit()

##  --------------------  UDEMY LOGIC  --------------------
##    This section is reached if at least one new course was found. It changes from Promodescuentos website
##    to Udemy's website, to actually redeem the promos.

##  UDEMY LOGIN
browser.get('https://www.udemy.com/join/login-popup/?locale=es_ES&response_type=html&next=https%3A%2F%2Fwww.udemy.com%2F')
time.sleep(1)
browser.find_element_by_name('email').send_keys('')     # -- SENSITIVE --
browser.find_element_by_name('password').send_keys('')         # -- SENSITIVE --
time.sleep(0.2)
browser.find_element_by_name('submit').click()
    
# DEBUG PRINTS
print(str(len(urls)))
print(str(len(urls2)))

##  OPEN REGISTER FILE
file = open(os.path.join(sys.path[0], database), 'a')

##  ITERATE LINKS
##    This is the actual logic to automatically redeem discount codes on Udemy Courses.
##    It works as follows: It iterates through all the links found in Promodescuentos,
##    searching for an indicator that the course is free. It does so by searching for specific
##    tags containing the course's price, and searching for a 'Free' text.
##    If found, the script clicks on a specific series of buttons to redeem the course for free
##    then, the course is registed as redeemed. If the course is not free or cannot be redeemed, 
##    it is not registered, to leave the possibility of redeeming a future promo.
##    Most of the process if specific to my experience with the Udemy website, and it's not at all
##    polished or elegant, but it works. The following code is the result of some hard working hours
##    of trial and error to get the tags, classes and buttons correctly so the right things were pressed.
##    Other particularity of this code is that multiple tags and classes are used for the same divs / buttons,
##    and the ones that worked today might not work tomorrow, but maybe in two days they'll work,
##    so again, through trial and error, a list of tags that worked at some point was gathered, and the script
##    now tries to find one of the tags / paths that once worked. The list was gathered manually though.

## FOR EVERY LINK
for index, link in enumerate(urls2, start=1):
    if type(link) != str:
        continue
    index = str(index)
    browser.get(link)
    time.sleep(2.5)
    try:
        ##  CHECK IF ALREADY BOUGHT
        if 'comprado' in browser.find_element_by_css_selector('div.purchase-text span:nth-child(2)').get_attribute('innerHTML') or 'comprado' in browser.find_element_by_css_selector('div.udlite-heading-md').get_attribute('innerHTML'):
            print(index + '. Ya lo has coprado')
            continue
    except:
        try:
            ##  DEFAULT CASE
            price = browser.find_element_by_css_selector('div.sidebar-container--purchase-section--17KRp div.ud-component--clp--price-text div.course-price-text > span:nth-child(2)')
            if (price.get_attribute('innerHTML') == 'Gratis' or price.get_attribute('innerHTML') == 'Gratuito'):
                print(index + '. El curso es gratis')
                browser.find_element_by_css_selector('div.ud-component--clp--buy-button button').click()
                time.sleep(5)
            else:
                print(index + '. El curso no es gratis: ' + price.get_attribute('innerHTML'))
        except:
            try:
                ##  CASE WITH CONFIRMATION
                price = browser.find_element_by_css_selector('div.price-text--price-part--Tu6MH > span:nth-child(2)')                              
                if price.get_attribute('innerHTML') == 'Gratis':
                    print(index + '. Gratis de por sí')
                    try:                        
                        browser.find_element_by_css_selector('div.ud-component--clp--buy-button button').click()
                        print('o1')
                    except:
                        browser.find_element_by_css_selector('.styles--btn--express-checkout--28jN4').click()
                        time.sleep(3)
                        try:
                            time.sleep(3)
                            btns = browser.find_elements_by_tag_name('button')
                            webdriver.ActionChains(browser).move_to_element(btns[3]).click().perform()
                            time.sleep(3)
                        except:
                            try:
                                btn = browser.find_element_by_css_selector('div.styles--complete-payment-container--3Jazs')
                                time.sleep(0.2)
                                btn.click()
                            except:
                                print(index + '. No se pudo xd')
            except:
                print(index + '. Probablemente ya lo has comprado')
                continue

##  SAVE VISITED TO DATABASE
for link3 in urls3:
    file.write(',' + regexU.search(link3).group(1))
for link2 in variosLinks2:
    file.write(',' + regexL.search(link2).group(1))

##  END THE SCRIPT
##    Last section of the script. Here the files are saved to the cloud and closed.
file.close()
fail = service.files().get(fileId='*************************').execute()
media_body = MediaFileUpload(database,mimetype="text/plain", resumable=True)
updated_file = service.files().update(
    fileId='***********************',
    media_body=media_body).execute()
browser.quit()        