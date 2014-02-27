import Queue
import re
import socket
import sys
import threading
import time
import urllib2


MAX_ACTIVE_FETCHERS = 2


class Fetcher(threading.Thread):
    _lock = threading.Lock()
    _num_active = 0

    def __init__(self, url, queue):
        super(Fetcher, self).__init__()
        self._url = url
        self._queue = queue

    def run(self):
        with Fetcher._lock:
            if Fetcher._num_active > MAX_ACTIVE_FETCHERS:
                return
            Fetcher._num_active += 1

        try:
            return self._run()
        finally:
            with Fetcher._lock:
                Fetcher._num_active -= 1

    def _run(self):
        try:
            text = self._read_url()
        except Exception as e:
            print 'got exception:', e
            return

        m = re.match(r'^.*?<title>(.*?)</title>.*$', text,
                     re.MULTILINE | re.DOTALL)
        if m:
            msg = ''.join(c for c in m.group(1).strip() if c >= ' ')
            self._queue.put(msg)

    def _read_url(self):
        x = urllib2.urlopen(self._url)
        text = x.read()
        x.close()
        return text


class IRCLinkBot(object):
    def __init__(self, server_addr, server_port, chan, nick):
        self._server_addr = server_addr
        self._server_port = server_port
        self._chan = chan
        self._nick = nick
        self._queue = Queue.Queue()

    def run(self):
        s = socket.create_connection((self._server_addr, self._server_port,),)

        n = self._nick
        s.send('USER %s %s %s :%s\n' % (n, n, n, n,))
        s.send('NICK %s\n' % n)
        s.send('JOIN %s\n' % self._chan)

        while True:
            s.settimeout(0.01)
            irc_line = ''
            try:
                irc_line = s.recv(512).strip()
            except socket.timeout:
                pass
            if irc_line and irc_line.startswith('PING'):
                response = irc_line.strip().split(' ')[1]
                s.send('PONG %s\n' % response)
            m = re.match(r'^.*?(https?://\S+).*$', irc_line)
            if m:
                Fetcher(m.group(1), self._queue).start()
            s.settimeout(10)

            line = self._readline()
            if line and line.strip():
                print '"%s"' % line
                s.send('PRIVMSG %s :%s\n' % (self._chan, line,))

            time.sleep(0.1)

    def _readline(self):
        try:
            return self._queue.get(False)
        except Queue.Empty:
            return None

    def rerun(self):
        while True:
            try:
                self.run()
            except Exception as e:
                print ('exception raised in bot thread, sleeping and ' +
                       're-starting...')
                print e
                print type(e)
                time.sleep(60)


def main(argv):
    try:
        bot = IRCLinkBot(*(argv[1:]))
        bot.rerun()
    except KeyboardInterrupt:
        print 'got interrupt signal from user, exiting...'
        sys.exit(0)


if __name__ == '__main__':
    main(sys.argv)
