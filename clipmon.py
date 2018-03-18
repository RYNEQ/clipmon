#!/usr/bin/python3

import argparse
import browsercookie
import html
import os
import pyperclip
import re
import requests
import subprocess as s
import sys
import threading
import time
from bs4 import BeautifulSoup


class Notifier(threading.Thread):
    def __init__(self, url, cj, notify_title):
        super(Notifier, self).__init__()
        self._url = url
        self._cookie_jar = cj
        self._notify_title = notify_title

    def run(self):
        if self._notify_title:
            r = requests.get(self._url, cookies=self._cookie_jar)
            soup = BeautifulSoup(r.text, 'html.parser')
            t = soup.find('title')
            s.call(['notify-send', 'Found URL', html.escape("Title: %s\nURL: %s" % (t.text, self._url), True)])
        else:
            s.call(['notify-send', 'Found URL', html.escape("URL: %s" % self._url, True)])


class ClipboardWatcher(threading.Thread):
    def is_url_in_list(self, url):
        for i in self._mon_domains:
            if re.match(i, url):
                return True
        return False

    def print_to_stdout_and_store(self, clipboard_content):
        print("Found url: %s" % str(clipboard_content))
        self._of.write(clipboard_content + os.linesep)
        self._of.flush()
        if self._notify:
            n = Notifier(clipboard_content, self._cookie_jar, self._notify_title)
        n.start()

    def __init__(self, mon_domains, pause, of, notify, notify_title, cookie_jar):
        super(ClipboardWatcher, self).__init__()
        self._pause = pause
        self._stopping = False
        self._mon_domains = mon_domains
        self._notify = notify
        self._notify_title = notify_title
        self._cookie_jar = cookie_jar

        try:
            self._of = open(file=of, mode='a')
        except OSError as e:
            print(e)
            exit(1)

    def run(self):
        recent_value = pyperclip.paste()
        while not self._stopping:
            tmp_value = pyperclip.paste()
            if tmp_value != recent_value:
                recent_value = tmp_value
                if self.is_url_in_list(recent_value):
                    self.print_to_stdout_and_store(recent_value)
            time.sleep(self._pause)

    def stop(self):
        self._stopping = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._of.close()


def main():
    parser = argparse.ArgumentParser(description='Monitor clipboard and fetch urls matching regex')
    parser.add_argument('-f', "--file", action='store', help='output file path', default='list.list')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-m', "--match-repository", action='store',
                       help='file containing match patterns, reach line one pattern', default='.regexlist')
    group.add_argument('-r', "--match-regex", action='store',
                       help='Regex to match urls')

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-F', '--firefox-cookies', action='store_true', default=False,
                       help='Use firefox cookies for title fetch requests')
    group.add_argument('-C', '--chrome-cookies', action='store_true', default=False,
                       help='Use Chrome cookies for title fetch requests')
    group.add_argument('-J', '--jar-cookies', action='store', default=False,
                       help='Use JAR file as cookies for title fetch requests')
    parser.add_argument('-t', '--notify-title', required=(not set(sys.argv).isdisjoint(('-F', '--firefox-cookies',
                                                                                        '-C', '--chrome-cookies',
                                                                                        '-J', '--jar-cookies'))),
                        default=False, action='store_true',
                        help='Show page title in desktop notifications (slower notifications)')
    parser.add_argument('-n', '--notify', required=(not set(sys.argv).isdisjoint(('-t', '--notify-title'))),
                        default=False, action='store_true',
                        help='Show desktop notifications')
    args = parser.parse_args()

    outfile = args.file
    if args.match_regex:
        mon_domains = [args.match_regex]
    else:
        mon_domains = tuple(open(args.match_repository, 'r'))

    if args.firefox_cookies:
        cj = browsercookie.firefox()
    elif args.chrome_cookies:
        cj = browsercookie.chrome()
    elif args.jar_cookies:
        cj = args.jar_cookies
    else:
        cj = None

    with ClipboardWatcher(mon_domains, 1., outfile, args.notify, args.notify_title, cj) as watcher:
        print("Start monitoring ...")
        watcher.start()
        while True:
            try:
                # print("Waiting for changed clipboard...")
                time.sleep(.1)
            except KeyboardInterrupt:
                print("Exit request received. cleaning up ...")
                watcher.stop()
                watcher.join()
                print("Finished")
                break


if __name__ == "__main__":
    main()
