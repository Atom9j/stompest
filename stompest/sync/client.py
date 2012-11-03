# -*- coding: iso-8859-1 -*-
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
import contextlib
import logging
import time

from stompest.error import StompConnectionError
from stompest.protocol import StompFailoverProtocol, StompSession

from .transport import StompFrameTransport
from stompest.protocol import commands
from stompest.sync.util import connected

LOG_CATEGORY = 'stompest.sync'

# TODO: introduce connect/connected/disconnect timeouts as in async.Stomp

class Stomp(object):
    factory = StompFrameTransport
    
    def __init__(self, config):
        self.log = logging.getLogger(LOG_CATEGORY)
        self._config = config
        self._session = StompSession(self._config.version, self._config.check)
        self._failover = StompFailoverProtocol(config.uri)
        self._transport = None
    
    def connect(self, headers=None, versions=None, host=None):
        try: # preserve existing connection
            self._transport
            self.log.warning('Already connected to %s' % self._transport)
            return
        except StompConnectionError as e:
            self.log.warning('Lost connection [%s]' % e)
        try:
            for (broker, connectDelay) in self._failover:
                transport = self.factory(broker['host'], broker['port'], self._session.version)
                if connectDelay:
                    self.log.debug('Delaying connect attempt for %d ms' % int(connectDelay * 1000))
                    time.sleep(connectDelay)
                self.log.info('Connecting to %s ...' % transport)
                try:
                    transport.connect()
                except StompConnectionError as e:
                    self.log.warning('Could not connect to %s [%s]' % (transport, e))
                else:
                    self.log.info('Connection established')
                    self._transport = transport
                    self._connect(headers, versions, host)
                    break
        except StompConnectionError as e:
            self.log.error('Reconnect failed [%s]' % e)
            raise
        
    def _connect(self, headers=None, versions=None, host=None):
        frame = self._session.connect(self._config.login, self._config.passcode, headers, versions, host)
        self.sendFrame(frame)
        frame = self.receiveFrame()
        self._session.connected(frame)
        self.log.info('STOMP session established with broker %s' % self._transport)
        for (dest, headers, _) in self._session.replay():
            self.log.info('Replaying subscription %s' % headers)
            self.subscribe(dest, headers)
    
    @connected
    def disconnect(self, receipt=None):
        self.sendFrame(self._session.disconnect(receipt))
        if not receipt:
            self.close()
    
    # STOMP frames

    @connected
    def send(self, destination, body='', headers=None, receipt=None):
        self.sendFrame(commands.send(destination, body, headers, receipt))
        
    @connected
    def subscribe(self, destination, headers, receipt=None, context=None):
        frame, token = self._session.subscribe(destination, headers, receipt, context)
        self.sendFrame(frame)
        return token
    
    @connected
    def unsubscribe(self, token, receipt=None):
        self.sendFrame(self._session.unsubscribe(token, receipt))
        
    @connected
    def ack(self, headers, receipt=None):
        self.sendFrame(self._session.ack(headers, receipt))
    
    @connected
    def nack(self, headers, receipt=None):
        self.sendFrame(self._session.nack(headers, receipt))
    
    @connected
    def begin(self, transaction, receipt=None):
        self.sendFrame(self._session.begin(transaction, receipt))
        
    @connected
    def abort(self, transaction, receipt=None):
        self.sendFrame(self._session.abort(transaction, receipt))
        
    @connected
    def commit(self, transaction, receipt=None):
        self.sendFrame(self._session.commit(transaction, receipt))
    
    @contextlib.contextmanager
    @connected
    def transaction(self, transaction=None, receipt=None):
        transaction = self._session.transaction(transaction)
        self.begin(transaction, receipt)
        try:
            yield transaction
            self.commit(transaction, receipt)
        except:
            self.abort(transaction, receipt)
    
    def message(self, frame):
        return self._session.message(frame)
    
    def receipt(self, frame):
        return self._session.receipt(frame)
    
    # frame transport
    
    def close(self, flush=True):
        self._session.close(flush)
        try:
            self.__transport and self.__transport.disconnect()
        finally:
            self._transport = None
    
    def canRead(self, timeout=None):
        return self._transport.canRead(timeout)
        
    def sendFrame(self, frame):
        if self.log.isEnabledFor(logging.DEBUG):
            self.log.debug('Sending %s' % frame.info())
        self._transport.send(frame)
            
    def receiveFrame(self):
        frame = self._transport.receive()
        if frame and self.log.isEnabledFor(logging.DEBUG):
            self.log.debug('Received %s' % frame.info())
        return frame
    
    @property
    def _transport(self):
        transport = self.__transport
        if not transport:
            raise StompConnectionError('Not connected')
        try:
            transport.canRead(0)
        except Exception as e:
            self.close(flush=False)
            raise e
        return transport
    
    @_transport.setter
    def _transport(self, transport):
        self.__transport = transport
        