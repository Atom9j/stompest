"""
Twisted STOMP client

Copyright 2011 Mozes, Inc.

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either expressed or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
import functools
import warnings

from twisted.internet import defer, reactor, task
from twisted.internet.endpoints import clientFromString

class StompConfig(object):
    def __init__(self, host=None, port=None, uri=None, login='', passcode=''):
        if not uri:
            if not (host and port):
                raise ValueError('host and port missing')
            uri = 'tcp://%s:%d' % (host, port)
            warnings.warn('host and port arguments are deprecated. use uri=%s instead!' % uri)
        self.uri = uri
        self.login = login
        self.passcode = passcode

def endpointFactory(broker):
    return clientFromString(reactor, '%(protocol)s:host=%(host)s:port=%(port)d' % broker)

def exclusive(f):
    @functools.wraps(f)
    def _exclusive(*args, **kwargs):
        if not _exclusive.running.called:
            raise RuntimeError('%s still running' % f.__name__)
        _exclusive.running = task.deferLater(reactor, 0, f, *args, **kwargs)
        return _exclusive.running
    
    _exclusive.running = defer.Deferred()
    _exclusive.running.callback(None)
    return _exclusive
