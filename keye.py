#!/usr/bin/python

import argparse
import requests
import sqlite3
import os
from slackconfig import *
import json
requests.packages.urllib3.disable_warnings()

import sys
if sys.version_info[0] < 3:
    raise Exception("Must be using Python 3")

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--singleurl', help='Single URL to add. E.g: http://google.com', dest='singleurl')
parser.add_argument('-ul', '--urlslist', help='File with new urls to add. E.g: urls.txt', dest='urlslist')
parser.add_argument('-rm', '--remove', help='URL to remove from database. E.g: http://google.com', dest='urltoremove')
parser.add_argument('-d', '--display', help='Display all monitored URLs', required =  False, nargs='?', const="True", dest='displayurls')
parser.add_argument('-x', '--add-conn-error', help='Add urls to db even when connection fails at the time of adding', required =  False, action='store_true', dest='addOnConnError')
parser.add_argument('-p', '--req-percent-change',help='Percentage required to be changed in content-type for notification', required = False, default=1, type=float, dest='requiredPercentChange')

args = parser.parse_args()

def getContentLength(response):
        responseHeaders = response.headers
        if "content-length" in responseHeaders:
            newcontentlength = responseHeaders["content-length"]
        else:
            newcontentlength = len(response.content)
        return int(newcontentlength)

def db_install():
    if (os.path.isfile('./keye.db')) == False:
        db = sqlite3.connect('keye.db')
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE urls(id INTEGER PRIMARY KEY, url TEXT,
                               contentlength INTEGER)''')
        db.commit()
        db.close()
    else:
        pass

def addsingleurl():
    url = args.singleurl
    all_rows=getFromDB()
    for row in all_rows:
        urlDB = row[1]
        if urlDB == url:
            print("url already present in db : "+url)
            return
    request(url)

def addurlsfromlist():
    all_rows=getFromDB()
    urlsDB=[]
    urlsFile=[]

    for row in all_rows:
        urlDB = row[1]
        urlsDB.append(urlDB)

    urlslist = open(args.urlslist, "r")
    for urlFile in urlslist:
        urlFile = urlFile.rstrip()
        urlsFile.append(urlFile)
    
    for url in set(urlsFile).difference(set(urlsDB)):
        request(url)

def request(url):
    oURL = url  # saving original url for later use
    try:
        if not "http" in url:
            url = "http://" + url
        response=requests.get(url, allow_redirects=True, verify=False, timeout=5)
        contentlength = getContentLength(response)
        try:
            committodb(oURL, contentlength)
            print("We have successfully added " + url +" to be monitored.")
        except Exception as e:
            print(e)
    except:
        try:
            url = url.replace("http://", "https://")
            response = requests.get(url, allow_redirects=True, timeout=5)
            contentlength=getContentLength(response)
            committodb(oURL, contentlength)
            print("We have successfully added " + url +" to be monitored.")
        except Exception as e:
        	if args.addOnConnError:
        		committodb(oURL, '-1')
        		print("We have successfully added the " + oURL + " to be monitored despite of error.")
        	print("We could not connect to {} due to following error: {}".format(url, e))

def committodb(url, contentlength):
    try:
        cursor.execute('''INSERT INTO urls(url, contentlength)
                          VALUES(?,?)''', (url, contentlength))
        db.commit()
    except Exception as e:
        print(e)

def getFromDB():
        cursor.execute('''SELECT id, url, contentlength FROM urls''')
        all_rows = cursor.fetchall()
        return all_rows

def main():
    try:
            all_rows=getFromDB()
            for row in all_rows:
                id = row[0]
                url = row[1]
                contentlength = int(row[2])
                connect(id, url, contentlength)
    except Exception as e:
        print(e)

def connect(id, url, contentlength):
    if "http" not in url:
        url = 'http://'+url

    try:
        response = requests.get(url, allow_redirects=True, verify=False, timeout=5)
    except:
        url = url.replace("http://", "https://")
        try:
            response = requests.get(url, allow_redirects=True, verify=False, timeout=5)
        except Exception as e:
            print (e)
            return
    newcontentlength = getContentLength(response)
    if newcontentlength == contentlength:
        print ("No change , URL " + url + " New "+str(newcontentlength)+" Old "+str(contentlength))
        pass
    else:
        percentChange=(newcontentlength-contentlength)*100/contentlength
        if abs(percentChange) > args.requiredPercentChange:
            notify(url,contentlength,newcontentlength)
            cursor.execute('''UPDATE urls SET contentlength = ? WHERE id = ? ''', (newcontentlength, id))
            db.commit()
        else:   
            print ("Some change , URL " + url + " NEW: "+str(newcontentlength)+", OLD: "+str(contentlength)+" Percent Change : " + str(abs(percentChange)) + " Notification not send as minimum threashold to notify not met. ")
    

def removefromdb():
    urltoremove = args.urltoremove
    try:
        cursor.execute('''DELETE FROM urls WHERE url = ? ''', (urltoremove,))
        db.commit()
        print("\nWe have successfully removed the URL from the database.")
    except Exception as e:
        print(e)

def displayurls():
    try:
        cursor.execute('''SELECT url from urls''')
        all_rows = cursor.fetchall()
        for row in all_rows:
            print(row[0])
    except Exception as e:
        print("We couldn't retrieve URLs due to following error {}".format(e))


def notify(url,previousCL,newCL):
    webhook_url = posting_webhook
    slack_data = {'text': 'Changes detected on: ' + url +'. Previous CL: '+ str(previousCL) + ', New CL: ' + str(newCL)}
    sendnotification = requests.post(webhook_url, data=json.dumps(slack_data), headers={'Content-Type': 'application/json'})

db_install()
db = sqlite3.connect('keye.db')
cursor = db.cursor()

if args.singleurl:
    addsingleurl()
elif args.urlslist:
    addurlsfromlist()
elif args.urltoremove:
    removefromdb()
elif args.displayurls:
    displayurls()
else:
    main()

db.close()
