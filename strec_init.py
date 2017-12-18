#!/usr/bin/env python

import argparse
import sqlite3
import os.path
import sys
import datetime
import getpass
import configparser
import urllib.request
import urllib.error
import urllib.parse
import urllib.parse
import tempfile
import tarfile
import gzip
import shutil
import re

from strec.mtreader import createDataFile, appendDataFile
import strec.utils

SLABURL = 'ftp://hazards.cr.usgs.gov/web/data/slab/models/allslabs.tgz'
HIST_GCMT_URL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/jan76_dec10.ndk.gz'
MONTHLY_GCMT_URL = 'http://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/NEW_MONTHLY/'


def getMonthList(year, rmonth):
    strmonth = ['jan', 'feb', 'mar', 'apr', 'may',
                'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    yearurl = urllib.parse.urljoin(MONTHLY_GCMT_URL, str(year))
    try:
        fh = urllib.request.urlopen(yearurl)
        data = fh.read().decode('utf-8')
        mlist = re.findall('[a-z]{3}[0-9]{2}.ndk', data)
        mlist = unique(mlist)
        monthlist = []
        for m in mlist:
            mon = strmonth.index(m[0:3]) + 1
            if mon >= rmonth:
                monthlist.append(mon)
        fh.close()
        monthlist.sort()
        return monthlist
    except Exception as msg:
        raise Exception(msg)


def unique(inlist):
    # order preserving
    uniques = []
    for item in inlist:
        if item not in uniques:
            uniques.append(item)
    return uniques


def getMostRecent(dbfile):
    connection = sqlite3.connect(dbfile)
    cursor = connection.cursor()
    query = 'SELECT max(origin) FROM event'
    cursor.execute(query)
    row = cursor.fetchone()
    mostrecent = datetime.datetime.strptime(row[0][0:19], '%Y-%m-%d %H:%M:%S')
    cursor.close()
    connection.close()
    return mostrecent


def getMonthlyGCMT(year, month):
    strmonth = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                'jul', 'aug', 'sep', 'oct', 'nov', 'dec'][month - 1]
    stryear = str(year)
    url = urllib.parse.urljoin(MONTHLY_GCMT_URL, os.path.join(
        stryear, strmonth + stryear[2:] + '.ndk'))
    try:
        fh = urllib.request.urlopen(url)
        bytes = fh.read().decode('utf-8')
        fh.close()
        f, fname = tempfile.mkstemp()
        os.close(f)
        f = open(fname, 'wt')
        f.write(bytes)
        f.close()
        return fname
    except Exception as msg:
        raise Exception(msg)


def getHistoricalGCMT():
    try:
        fh = urllib.request.urlopen(HIST_GCMT_URL)
        bytes = fh.read()
        fh.close()
        f, zipname = tempfile.mkstemp()
        os.close(f)
        f = open(zipname, 'wb')
        f.write(bytes)
        f.close()
        gz = gzip.GzipFile(zipname, 'rb')
        f, fname = tempfile.mkstemp()
        os.close(f)
        f = open(fname, 'wb')
        try:
            bytes = gz.read()
        except Exception as msg:
            pass
        f.write(bytes)
        gz.close()
        f.close()
        return fname
    except Exception as msg:
        raise Exception(msg)


def fetchSlabs(datafolder):
    try:
        fh = urllib.request.urlopen(SLABURL)
        bytes = fh.read()
        fh.close()
        f, fname = tempfile.mkstemp()
        os.close(f)
        f = open(fname, 'wb')
        f.write(bytes)
        f.close()
        tar = tarfile.open(name=fname, mode='r:gz')
        tar.extractall(path=datafolder)
        tar.close()
        os.remove(fname)
    except Exception as msg:
        raise Exception(msg)


if __name__ == '__main__':
    usage = 'Initialize STREC data directory with USGS NEIC Slab data and (optionally) GCMT data.'
    parser = argparse.ArgumentParser(
        description=usage, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-g", "--gcmt",
                        action="store_true", dest="getGCMT", default=False,
                        help="Download all GCMT moment tensor data")
    parser.add_argument("-c", "--comcat",
                        action="store_true", dest="getComCat", default=False,
                        help="Download all USGS ComCat moment tensor data (sans GCMT)")
    parser.add_argument("-n", "--noslab",
                        action="store_true", dest="noSlab", default=False,
                        help="Do NOT download slab data")
    parser.add_argument("-r", "--reinit",
                        action="store_true", dest="reInitialize", default=False,
                        help="Re-initialize STREC application.")
    parser.add_argument("-u", "--update",
                        action="store_true", dest="update", default=False,
                        help="Update gcmt data.")

    args = parser.parse_args()

    if args.getGCMT:
        args.update = True

    if args.reInitialize:
        config, configfile = strec.utils.getConfig()
        if config is not None:
            datafolder = config.get('DATA', 'folder')
            print('Deleting existing data folder %s' % datafolder)
            shutil.rmtree(datafolder)
        print('Deleting config file...')
        strec.utils.deleteConfig()
    try:
        config, configfile = strec.utils.getConfig()
    except Exception as msg:
        print(msg)
        sys.exit(1)
    if config is not None and config.has_option('DATA', 'folder'):
        datafolder = config.get('DATA', 'folder')
    else:
        datafolder = input(
            'Enter the desired storage location for STREC data: ')
        if not os.path.isdir(datafolder):
            answer = input(
                '%s does not exist.  Would you like me to create it for you? y/[n]?: ' % datafolder)
            if answer.lower() != 'y':
                print('Stopping.')
                sys.exit(0)
            try:
                datafolder = os.path.normpath(os.path.expanduser((datafolder)))
                os.makedirs(datafolder)
            except Exception as msg:
                print('Could not make %s due to error "%s".  Stopping.' %
                      (datafolder, msg))
                sys.exit(1)
        else:
            datafolder = os.path.normpath(os.path.expanduser((datafolder)))
        config.add_section('DATA')
        config.set('DATA', 'folder', datafolder)
        config.write(open(configfile, 'wt'))
    try:
        if not args.noSlab:
            print('Downloading all required slab data (this may take a while...)')
            fetchSlabs(datafolder)
            print('Finished downloading slab data.')
    except Exception as msg:
        print('Error "%s" while downloading NEIC Slab data. Stopping.' %
              msg.message)
        sys.exit(1)

    outfile = os.path.join(datafolder, strec.utils.GCMT_OUTPUT)
    if args.getGCMT:
        try:
            print('Downloading and converting historical GCMT data...')
            histfile = getHistoricalGCMT()
        except Exception as msg:
            print('Error "%s" when downloading data from %s.  Stopping.' %
                  (msg, HIST_GCMT_URL))
            sys.exit(1)
        createDataFile(histfile, outfile, 'ndk', 'gcmt', hasHeader=False)
        print('Finished converting historical GCMT data.')
        os.remove(histfile)
    if args.getComCat:
        pass

    if args.update:
        mostrecent = getMostRecent(outfile)
        ryear = mostrecent.year
        rmonth = mostrecent.month + 1
        if rmonth == 13:
            ryear += 1
            rmonth = 1
        tnow = datetime.datetime.now()
        tyear = tnow.year
        tmonth = tnow.month
        strmonth = ['Jan', 'Feb', 'Mar', 'Apr', 'May',
                    'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for year in range(ryear, tyear + 1):
            try:
                monthlist = getMonthList(year, rmonth)
            except Exception as msg:
                print('Could not find a URL (starting with %s) for year %i.  Stopping.' % (
                    MONTHLY_GCMT_URL, year))
                sys.exit(0)
            for month in monthlist:
                try:
                    print('Attempting to download data from %s, %i...' %
                          (strmonth[month - 1], year))
                    histfile = getMonthlyGCMT(year, month)
                    appendDataFile(histfile, outfile, 'ndk',
                                   'gcmt', hasHeader=False)
                    os.remove(histfile)
                except Exception as msg:
                    fmt = 'Could not download GCMT data for %s, %i.  (It may not be posted yet)'
                    print(fmt % (strmonth[month - 1], year))
                    continue
        mostrecent = getMostRecent(outfile)
        print('GCMT database contains events through %s.' % str(mostrecent))
        sys.exit(0)
