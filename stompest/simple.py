"""
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
import contextlib
import select
import socket

from stompest.error import StompConnectionError, StompProtocolError
from stompest.protocol import commands
from stompest.protocol.frame import StompFrame
from stompest.protocol.parser import StompParser
from stompest.protocol.spec import StompSpec

class Stomp(object):
    """A simple implementation of a STOMP client"""
    READ_SIZE = 4096
    
    def __init__(self, host, port, version='1.0'):
        self.host = host
        self.port = port
        self.socket = None
        self.version = version
        self._setParser()
    
    def connect(self, login='', passcode='', headers=None):
        headers = self._createConnectHeaders(headers)
        self._socketConnect()
        self.sendFrame(commands.connect(login, passcode, headers))
        self._setParser()
        return self._handleConnectResponse(self.receiveFrame())
    
    def _createConnectHeaders(self, headers):
        headers = dict(headers or {})
        if self.version != '1.0':
            headers[StompSpec.ACCEPT_VERSION_HEADER] = self.version
        return headers
    
    def _handleConnectResponse(self, frame):
        if frame['cmd'] == StompSpec.CONNECTED:
            if self.version != '1.0':
                try:
                    version = frame['headers'][StompSpec.VERSION_HEADER]
                except:
                    version = '1.0'
                if version != self.version:
                    self.disconnect()
                    raise StompProtocolError('Incompatible server version: %s [client version: %s]' % (version, self.version))
            return frame
        raise StompProtocolError('Unexpected frame received: %s' % frame)
        
    def disconnect(self):
        self.sendFrame(commands.disconnect())
        self._socketDisconnect()

    def canRead(self, timeout=None):
        self._checkConnected()
        if self.parser.canRead():
            return True
        if timeout is None:
            readList, _, _ = select.select([self.socket], [], [])
        else:
            readList, _, _ = select.select([self.socket], [], [], timeout)
        return bool(readList)
        
    def send(self, dest, msg, headers=None):
        headers = dict(headers or {})
        if StompSpec.DESTINATION_HEADER in headers:
            headers.pop(StompSpec.DESTINATION_HEADER)
        self.sendFrame(commands.send(dest, msg, headers))
        
    def subscribe(self, dest=None, headers=None):
        headers = dict(headers or {})
        headers.setdefault(StompSpec.ACK_HEADER, 'auto')
        headers.setdefault('activemq.prefetchSize', 1)
        frame = commands.subscribe(dest, headers, self.version)
        self.sendFrame(frame)
        return frame
        
    def unsubscribe(self, dest=None, headers=None):
        # made dest parameter optional since an unsubscribe frame with ID_HEADER header precludes a DESTINATION_HEADER
        headers = dict(headers or [])
        if dest:
            headers[StompSpec.DESTINATION_HEADER] = dest
        self.sendFrame(commands.unsubscribe(headers, self.version))
    
    def begin(self, transactionId):
        self.sendFrame(commands.begin(commands.transaction(transactionId)))
        
    def commit(self, transactionId):
        self.sendFrame(commands.commit(commands.transaction(transactionId)))        

    def abort(self, transactionId):
        self.sendFrame(commands.abort(commands.transaction(transactionId)))
    
    @contextlib.contextmanager
    def transaction(self, transactionId):
        self.begin(transactionId)
        try:
            yield
            self.commit(transactionId)
        except:
            self.abort(transactionId)
        
    def ack(self, message):
        self.sendFrame(commands.ack(message['headers']))
    
    def nack(self, message):
        self.sendFrame(commands.nack(message['headers']))
    
    def receiveFrame(self):
        while True:
            message = self.parser.getMessage()
            if message:
                return message
            try:
                data = self.socket.recv(self.READ_SIZE)
                if not data:
                    raise StompConnectionError('No more data')
            except (IOError, StompConnectionError) as e:
                self._socketDisconnect()
                raise StompConnectionError('Connection closed [%s]' % e)
            self.parser.add(data)
    
    def sendFrame(self, message):
        self._write(str(self._toFrame(message)))
        
    def _checkConnected(self):
        if not self._connected():
            raise StompConnectionError('Not connected')
       
    def _connected(self):
        return self.socket is not None
        
    def _setParser(self):
        self.parser = StompParser(self.version)
        
    def _socketConnect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
        except IOError as e:
            raise StompConnectionError('Could not establish connection [%s]' % e)
        
    def _socketDisconnect(self):
        try:
            self.socket.close()
        except IOError as e:
            raise StompConnectionError('Could not close connection cleanly [%s]' % e)
        finally:
            self.socket = None
    
    def _toFrame(self, message):
        if not isinstance(message, StompFrame):
            message = StompFrame(**message)
        return message
    
    def _write(self, data):
        self._checkConnected()
        try:
            self.socket.sendall(data)
        except IOError as e:
            raise StompConnectionError('Could not send to connection [%s]' % e)
