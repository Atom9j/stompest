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
import unittest

from stompest.error import StompProtocolError
from stompest.protocol import StompSession, StompSpec, commands
   
class StompSessionTest(unittest.TestCase):
    def test_session_init(self):
        session = StompSession()
        self.assertEquals(session.version, StompSpec.DEFAULT_VERSION)
        session.send('', '', {})
        session.subscribe('bla1', {'bla2': 'bla3'})
        session.unsubscribe((StompSpec.DESTINATION_HEADER, 'bla1'))

        session = StompSession(check=True)
        self.assertRaises(StompProtocolError, lambda: session.send('', '', {}))
        self.assertRaises(StompProtocolError, lambda: session.subscribe('bla1', {'bla2': 'bla3'}))
        self.assertRaises(StompProtocolError, lambda: session.unsubscribe((StompSpec.DESTINATION_HEADER, 'bla1')))
        
        session = StompSession('1.1', check=True)
        self.assertEquals(session.version, '1.1')
        
        self.assertRaises(StompProtocolError, lambda: StompSession(version='1.2'))
        self.assertRaises(StompProtocolError, lambda: session.send('', '', {}))
    
    def test_session_connect(self):
        session = StompSession(StompSpec.VERSION_1_0)
        self.assertEquals(session.server, None)
        self.assertEquals(session.id, None)
        self.assertEquals(session.state, StompSession.DISCONNECTED)
        frame = session.connect(login='', passcode='')
        self.assertEquals(session.state, StompSession.CONNECTING)
        self.assertEquals(frame, commands.connect(login='', passcode='', versions=None))
        session.connected({StompSpec.SESSION_HEADER: 'hi'})
        self.assertEquals(session.state, StompSession.CONNECTED)
        self.assertEquals(session.version, StompSpec.VERSION_1_0)
        self.assertEquals(session.server, None)
        self.assertEquals(session.id, 'hi')
        frame = session.disconnect()
        self.assertEquals(frame, commands.disconnect())
        self.assertEquals(session.server, None)
        self.assertEquals(session.id, None)
        self.assertEquals(session.state, StompSession.DISCONNECTED)

        session = StompSession(version='1.1')
        frame = session.connect(login='', passcode='')
        self.assertEquals(frame, commands.connect('', '', {}, ['1.0', '1.1']))
        self.assertEquals(session.state, StompSession.CONNECTING)
        session.connected({StompSpec.SERVER_HEADER: 'moon', StompSpec.SESSION_HEADER: '4711', StompSpec.VERSION_HEADER: StompSpec.VERSION_1_1})
        self.assertEquals(session.state, StompSession.CONNECTED)
        frame = session.disconnect(4711)
        self.assertEquals(frame, commands.disconnect('4711', '1.1'))
        self.assertEquals(session.server, None)
        self.assertEquals(session.id, None)
        self.assertEquals(session.state, StompSession.DISCONNECTED)

    def test_session_subscribe(self):
        session = StompSession()
        headers = {'bla2': 'bla3'}
        frame, token = session.subscribe('bla1', headers)
        self.assertEquals(frame, commands.subscribe('bla1', headers, version='1.0'))
        
        self.assertEquals(token, (StompSpec.DESTINATION_HEADER, 'bla1'))
        self.assertEquals(token, session.subscription(token))
        self.assertEquals(token, session.subscription(frame))
        self.assertEquals(token, session.subscription(frame.headers))
        
        headersWithId1 = {StompSpec.ID_HEADER: 'bla2', 'bla3': 'bla4'}
        frame, tokenWithId1 = session.subscribe('bla2', headersWithId1)
        self.assertEquals(frame, commands.subscribe('bla2', headersWithId1, version='1.0'))
        self.assertEquals(tokenWithId1, (StompSpec.ID_HEADER, 'bla2'))
        
        headersWithId2 = {StompSpec.ID_HEADER: 'bla3', 'bla4': 'bla5'}
        session.subscribe('bla2', headersWithId2)
        
        subscriptions = list(session.replay())
        self.assertEquals(subscriptions, [('bla1', headers, None), ('bla2', headersWithId1, None), ('bla2', headersWithId2, None)])
        self.assertEquals(list(session.replay()), [])

        session.subscribe('bla2', headersWithId2)
        session.disconnect()
        self.assertEquals(list(session.replay()), [])
        
        subscriptionsWithoutId1 = [('bla1', headers, None), ('bla2', headersWithId2, None)]
        
        s = [session.subscribe(dest, headers_) for dest, headers_, _ in subscriptions]
        session.unsubscribe(s[1][1])
        self.assertEquals(list(session.replay()), subscriptionsWithoutId1)
        
        s = [session.subscribe(dest, headers_) for dest, headers_, _ in subscriptions]
        session.unsubscribe(s[1][0].headers)
        self.assertEquals(list(session.replay()), subscriptionsWithoutId1)

        s = [session.subscribe(dest, headers_) for dest, headers_, _ in subscriptions]
        session.unsubscribe(s[1][0])
        self.assertEquals(list(session.replay()), subscriptionsWithoutId1)
        
        subscriptionWithId2 = [('bla2', headersWithId2, None)]
        
        s = [session.subscribe(dest, headers_) for dest, headers_, _ in subscriptionsWithoutId1]
        session.unsubscribe(s[0][1])
        self.assertEquals(list(session.replay()), subscriptionWithId2)
        
        s = [session.subscribe(dest, headers_) for dest, headers_, _ in subscriptionsWithoutId1]
        session.unsubscribe(s[0][0].headers)
        self.assertEquals(list(session.replay()), subscriptionWithId2)
        
        s = [session.subscribe(dest, headers_) for dest, headers_, _ in subscriptionsWithoutId1]
        session.unsubscribe(s[0][0])
        self.assertEquals(list(session.replay()), subscriptionWithId2)
        
        session.disconnect()

        session = StompSession()
        session.connect(login='', passcode='')
        session.connected({StompSpec.SESSION_HEADER: 'hi'})

        session.subscribe('bla1', headers)
        self.assertRaises(StompProtocolError, lambda: session.unsubscribe((StompSpec.ID_HEADER, 'blub')))
        self.assertRaises(StompProtocolError, lambda: session.unsubscribe(('bla', 'blub')))
        
        frame, token = session.subscribe('bla2', headersWithId1)
        session.subscribe('bla2', headersWithId2)
        session.unsubscribe(token)
        self.assertRaises(StompProtocolError, lambda: session.unsubscribe(token))
        
        session = StompSession(version='1.1')
        session.connect(login='', passcode='')
        session.connected({StompSpec.SERVER_HEADER: 'moon', StompSpec.SESSION_HEADER: '4711', StompSpec.VERSION_HEADER: StompSpec.VERSION_1_1})
        
        self.assertRaises(StompProtocolError, lambda: session.subscribe('bla1', headers))
        self.assertRaises(StompProtocolError, lambda: session.unsubscribe((StompSpec.DESTINATION_HEADER, 'bla1')))
        frame, token = session.subscribe('bla2', headersWithId1)
        session.subscribe('bla2', headersWithId2)
        session.unsubscribe(token)
        self.assertRaises(StompProtocolError, lambda: session.unsubscribe(token))

        subscriptions = list(session.replay())
        self.assertEquals(subscriptions, subscriptionWithId2)
    
    def test_session_disconnect(self):
        session = StompSession('1.1', check=True)
        session.connect(login='', passcode='')
        session.connected({StompSpec.SESSION_HEADER: 'hi'})
        session.subscribe('bla', {StompSpec.ID_HEADER: 4711})
        frame = session.disconnect()
        self.assertEquals(frame, commands.disconnect())
        self.assertEquals(list(session.replay()), [])
        self.assertEquals(session.state, session.DISCONNECTED)
        
        self.assertRaises(StompProtocolError, session.disconnect)
        
    def test_session_nack(self):
        session = StompSession(version='1.1')
        
        for headers in [
            {StompSpec.MESSAGE_ID_HEADER: '4711', StompSpec.SUBSCRIPTION_HEADER: 'bla'},
            {StompSpec.MESSAGE_ID_HEADER: '4711', StompSpec.SUBSCRIPTION_HEADER: 'bla', 'foo': 'bar'}
        ]:
            self.assertEquals(session.nack(headers), commands.nack(headers, version='1.1'))
            
        self.assertRaises(StompProtocolError, session.nack, {})
        self.assertRaises(StompProtocolError, session.nack, {StompSpec.MESSAGE_ID_HEADER: '4711'})
        self.assertRaises(StompProtocolError, session.nack, {StompSpec.SUBSCRIPTION_HEADER: 'bla'})
    
        session = StompSession(version='1.1', check=True)
        self.assertRaises(StompProtocolError, lambda: session.nack({StompSpec.MESSAGE_ID_HEADER: '4711', StompSpec.SUBSCRIPTION_HEADER: 'bla'}))
        
    def test_session_transaction(self):
        session = StompSession()
        
        frame, token = session.begin()
        self.assertEquals(frame, commands.begin(dict([token])))
        self.assertEquals(frame.headers, dict([token]))
        frame, token_ = session.abort(token)
        self.assertEquals(token, token_)
        self.assertEquals(frame, commands.abort(dict([token])))
        self.assertRaises(StompProtocolError, lambda: session.abort(token))
        
        frame, token = session.begin()
        self.assertEquals(frame, commands.begin(dict([token])))
        self.assertEquals(frame.headers, dict([token]))
        frame, token_ = session.abort(dict([token]))
        self.assertEquals(token, token_)
        self.assertEquals(frame, commands.abort(dict([token])))
        self.assertRaises(StompProtocolError, lambda: session.abort(dict([token])))
        
        frame, token = session.begin()
        self.assertEquals(frame, commands.begin(dict([token])))
        self.assertEquals(frame.headers, dict([token]))
        frame, token_ = session.abort(frame)
        self.assertEquals(token, token_)
        self.assertEquals(frame, commands.abort(dict([token])))
        self.assertRaises(StompProtocolError, lambda: session.abort(frame))
        
        frame, token = session.begin()
        self.assertEquals(frame, commands.begin(dict([token])))
        self.assertEquals(frame.headers, dict([token]))
        frame, token_ = session.commit(token)
        self.assertEquals(token, token_)
        self.assertEquals(frame, commands.commit(dict([token])))
        self.assertRaises(StompProtocolError, lambda: session.commit(token))
        
        frame, token = session.begin()
        self.assertEquals(frame, commands.begin(dict([token])))
        self.assertEquals(frame.headers, dict([token]))
        frame, token_ = session.commit(dict([token]))
        self.assertEquals(token, token_)
        self.assertEquals(frame, commands.commit(dict([token])))
        self.assertRaises(StompProtocolError, lambda: session.commit(dict([token])))
        
        frame, token = session.begin()
        self.assertEquals(frame, commands.begin(dict([token])))
        self.assertEquals(frame.headers, dict([token]))
        frame, token_ = session.commit(frame)
        self.assertEquals(token, token_)
        self.assertEquals(frame, commands.commit(dict([token])))
        self.assertRaises(StompProtocolError, lambda: session.commit(frame))
        
        session = StompSession(check=True)
        self.assertRaises(StompProtocolError, session.begin)
        self.assertRaises(StompProtocolError, lambda: session.abort(None))
        self.assertRaises(StompProtocolError, lambda: session.commit(None))

if __name__ == '__main__':
    unittest.main()