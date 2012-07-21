"""
Copyright 2012 Mozes, Inc.

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
import logging
import time

from stompest.error import StompConnectionError
from stompest.protocol.session import StompSession as _StompSession
from stompest.simple import Stomp as _Stomp

LOG_CATEGORY = 'stompest.sync'

class Stomp(object):
    """A less simple implementation of a failover STOMP session with potentially more than one client"""
    def __init__(self, uri, login='', passcode=''):
        self.log = logging.getLogger(LOG_CATEGORY)
        self._login = login
        self._passcode = passcode
        self._session = _StompSession(uri, _Stomp)
        self._stomp = None
        
    def connect(self):
        if self._stomp:
            try: # preserve existing connection
                self._stomp.canRead(0)
                self.log.warning('already connected to %s:%d' % (self._stomp.host, self._stomp.port))
                return
            except StompConnectionError as e:
                self.log.warning('lost connection to %s:%d [%s]' % (self._stomp.host, self._stomp.port, e))
        try:
            for (stomp, connectDelay) in self._session.connections():
                self._stomp = stomp
                if connectDelay:
                    self.log.debug('delaying connect attempt for %d ms' % int(connectDelay * 1000))
                    time.sleep(connectDelay)
                try:
                    return self._connect()
                except StompConnectionError as e:
                    self.log.warning('could not connect to %s:%d [%s]' % (self._stomp.host, self._stomp.port, e))
        except StompConnectionError as e:
            self.log.error('reconnect failed [%s]' % e)
            raise

    def _connect(self):
        self.log.debug('connecting to %s:%d ...' % (self._stomp.host, self._stomp.port))
        result = self._stomp.connect(self._login, self._passcode)
        for headers in self._session.replay():
            self.log.debug('replaying subscription %s' % headers)
            self.subscribe(headers)
        self.log.info('connection established to %s:%d' % (self._stomp.host, self._stomp.port))
        return result
    
    def disconnect(self):
        self._subscriptions = []
        return self._stomp.disconnect()

    def canRead(self, timeout=None):
        return self._stomp.canRead(timeout)
        
    def send(self, dest, msg, headers=None):
        return self._stomp.send(dest, msg, headers)
        
    def subscribe(self, headers):
        headers = dict(headers)
        self._stomp.subscribe(headers=headers)
        self._session.subscribe(headers)
        
    def unsubscribe(self, headers):
        headers = dict(headers)
        self._stomp.unsubscribe(headers=headers)
        self._session.unsubscribe(headers)
    
    def begin(self, transactionId):
        self._stomp.begin(transactionId)
        
    def commit(self, transactionId):
        self._stomp.commit(transactionId)
        
    def abort(self, transactionId):
        self._stomp.abort(transactionId)
    
    def transaction(self, transactionId):
        self._stomp.transaction(transactionId)
        
    def ack(self, frame):
        self._stomp.ack(frame)
    
    def sendFrame(self, message):
        self._stomp.sendFrame(message)
    
    def receiveFrame(self):
        return self._stomp.receiveFrame()
