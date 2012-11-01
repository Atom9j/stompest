stomp, stomper, stompest!

Stompest is a [STOMP](http://stomp.github.com/) [1.0](http://stomp.github.com//stomp-specification-1.0.html) and [1.1](http://stomp.github.com//stomp-specification-1.1.html) implementation for Python including both synchronous and [Twisted](http://twistedmatrix.com/) clients.

Modeled after the Perl [Net::Stomp](http://search.cpan.org/dist/Net-Stomp/lib/Net/Stomp.pm) module, the synchronous client is dead simple. It does not assume anything about your concurrency model (thread vs process) or force you to use it any particular way. It gets out of your way and lets you do what you want.

The Twisted client is a full-featured STOMP protocol client. It supports destination-specific message and error handlers (with default "poison pill" error handling), concurrent message processing, graceful shutdown, and TCP level and STOMP session level connect and disconnect timeout.

Both clients make use of a generic set of components which can be used independently to roll your own STOMP client, viz.

* a faithful implementation of the syntax of the [STOMP](http://stomp.github.com/) [1.0](http://stomp.github.com//stomp-specification-1.0.html) and [1.1](http://stomp.github.com//stomp-specification-1.1.html) protocols with a simple stateless function API,

* a separate implementation of the [STOMP](http://stomp.github.com/) [1.0](http://stomp.github.com//stomp-specification-1.0.html) and [1.1](http://stomp.github.com//stomp-specification-1.1.html) session state semantics, such as protocol version negotiation at connect time, transaction and subscription handling (including a generic subscription replay scheme which may be used to reconstruct the session state after a forced disconnect),

* a wire-level [STOMP](http://stomp.github.com/) frame parser and compiler,

* and a [failover transport](http://activemq.apache.org/failover-transport-reference.html) URI scheme akin to [ActiveMQ](http://activemq.apache.org/).

This module is thoroughly unit tested and production hardened for the functionality used by [Mozes](http://www.mozes.com/): persistent queueing on [ActiveMQ](http://activemq.apache.org/). Minor enhancements may be required to use this STOMP adapter with other brokers.

Examples
======== 

Note
----
If you use [ActiveMQ](http://activemq.apache.org/) to run these examples, make sure you enable the Stomp connector in the [ActiveMQ](http://activemq.apache.org/) config file, activemq.xml.
   
    <transportConnector name="stomp"  uri="stomp://0.0.0.0:61613"/>
   
See http://activemq.apache.org/stomp.html for details.

Synchronous Producer
--------------------

    from stompest.protocol import StompConfig
    from stompest.sync import Stomp
    
    CONFIG = StompConfig('tcp://localhost:61613')
    QUEUE = '/queue/test'
    
    client = Stomp(CONFIG)
    client.connect()
    client.send(QUEUE, 'test message 1')
    client.send(QUEUE, 'test message 2')
    client.disconnect()
        
Sychronous Consumer
-------------------

    from stompest.protocol import StompConfig
    from stompest.sync import Stomp
    
    CONFIG = StompConfig('tcp://localhost:61613')
    QUEUE = '/queue/test'
    
    client = Stomp(CONFIG)
    client.connect()
    client.subscribe(QUEUE, {'ack': 'client'})
    
    while True:
        frame = client.receiveFrame()
        print 'Got %s' % frame.info()
        client.ack(frame)
        
    client.disconnect()
    
Twisted Producer
----------------

    import logging
    import json
    
    from twisted.internet import defer, reactor, task
    
    from stompest.async import Stomp
    from stompest.protocol import StompConfig
    
    class Producer(object):
        QUEUE = '/queue/testIn'
    
        def __init__(self, config=None):
            if config is None:
                config = StompConfig('tcp://localhost:61613')
            self.config = config
            
        @defer.inlineCallbacks
        def run(self):
            # establish connection
            stomp = yield Stomp(self.config).connect()
            # enqueue 10 messages
            try:
                for j in range(10):
                    stomp.send(self.QUEUE, json.dumps({'count': j}))
            finally:
                # give the reactor time to complete the writes
                yield task.deferLater(reactor, 1, stomp.disconnect)
        
    if __name__ == '__main__':
        logging.basicConfig(level=logging.DEBUG)
        Producer().run()
        reactor.run()
                 
Twisted Transformer
-------------------

    import logging
    import json
    
    from twisted.internet import reactor, defer
    
    from stompest.async import Stomp
    from stompest.protocol import StompConfig
    
    class IncrementTransformer(object):    
        IN_QUEUE = '/queue/testIn'
        OUT_QUEUE = '/queue/testOut'
        ERROR_QUEUE = '/queue/testTransformerError'
    
        def __init__(self, config=None):
            if config is None:
                config = StompConfig('tcp://localhost:61613')
            self.config = config
            
        @defer.inlineCallbacks
        def run(self):
            # establish connection
            client = yield Stomp(self.config).connect()
            # subscribe to inbound queue
            headers = {
                # client-individual mode is only supported in AMQ >= 5.2 but necessary for concurrent processing
                'ack': 'client-individual',
                # this is the maximal number of messages the broker will let you work on at the same time
                'activemq.prefetchSize': 100, 
            }
            client.subscribe(self.IN_QUEUE, self.addOne, headers, errorDestination=self.ERROR_QUEUE)
        
        def addOne(self, client, frame):
            """
            NOTE: you can return a Deferred here
            """
            data = json.loads(frame.body)
            data['count'] += 1
            client.send(self.OUT_QUEUE, json.dumps(data))
        
    if __name__ == '__main__':
        logging.basicConfig(level=logging.DEBUG)
        IncrementTransformer().run()
        reactor.run()
        
Twisted Consumer
----------------

    import logging
    import json
    
    from twisted.internet import reactor, defer
    
    from stompest.async import Stomp
    from stompest.protocol import StompConfig
    
    class Consumer(object):
        QUEUE = '/queue/testOut'
        ERROR_QUEUE = '/queue/testConsumerError'
    
        def __init__(self, config=None):
            if config is None:
                config = StompConfig('tcp://localhost:61613')
            self.config = config
            
        @defer.inlineCallbacks
        def run(self):
            # establish connection
            stomp = yield Stomp(self.config).connect()
            # subscribe to inbound queue
            headers = {
                # client-individual mode is only supported in AMQ >= 5.2 but necessary for concurrent processing
                'ack': 'client-individual',
                # this is the maximal number of messages the broker will let you work on at the same time
                'activemq.prefetchSize': 100, 
            }
            stomp.subscribe(self.QUEUE, self.consume, headers, errorDestination=self.ERROR_QUEUE)
        
        def consume(self, client, frame):
            """
            NOTE: you can return a Deferred here
            """
            data = json.loads(frame.body)
            print 'Received frame with count %d' % data['count']
        
    if __name__ == '__main__':
        logging.basicConfig(level=logging.DEBUG)
        Consumer().run()
        reactor.run()
            
Features
========

Commands layer
--------------
* Transport and client agnostic
* Full-featured implementation of all STOMP 1.0 and 1.1 client commands and
* Client-side handling of STOMP 1.0 and 1.1 commands received from the broker
* Stateless and simple function API

Session layer
-------------
* Manages the state of a connection
* Replays subscriptions upon reconnect
* Not yet fully client agnostic (currently only works on top of the simple client; support for the Twisted client is planned)
* Heartbeat handling (not yet implemented)

Failover layer
--------------
* Mimics the [failover transport](http://activemq.apache.org/failover-transport-reference.html) behavior of the [ActiveMQ](http://activemq.apache.org/) Java client
* Produces a possibly infinite sequence of broker network addresses and connect delay times

Parser layer
------------
* Abstract frame definition
* Transformation between these abstract frames and a wire-level byte stream of STOMP frames

Sync
----
* Built on top of the abstract layers, the synchronous client adds a TCP connection and a synchronous API.
* The concurrency scheme (synchronous, threaded, ...) is free to choose by the user.

Twisted
-------
* Graceful shutdown - On disconnect or error, the client stops processing new messages and waits for all outstanding message handlers to finish before issuing the DISCONNECT command.
* Error handling - fully customizable on a per-subscription level:
    * Disconnecting - if you do not configure an errorDestination and an exception propagates up from a message handler, then the client will gracefully disconnect. 
    
    This is effectively a NACK for the message. You can [configure ActiveMQ](http://activemq.apache.org/message-redelivery-and-dlq-handling.html) with a redelivery policy to avoid the "poison pill" scenario where the broker keeps redelivering a bad message infinitely.

    * Default error handling - passing the errorDestination parameter to the subscribe() method will cause unhandled messages to be forwarded to that destination.
    * Custom hook - you can override the default behavior with any error handling scheme you can think of.
    
* Fully unit-tested including a simulated STOMP broker
* Configurable connection timeout

Caveats
=======
* Tested with ActiveMQ versions 5.5 and 5.6. Mileage may vary with other STOMP implementations.
* stompest 2 is also very well tested and used in production by one of the contributors, but it has gained heavily on functionality, so it should be considered Alpha software. In the thorough redesign, the authors valued consistency, simplicity and symmetry over full backward compatibility to stompest 1.x, but the migration is very simple and straightforward.  
* Automatic heartbeat handling is in the pipeline for the Twisted client, but not yet implemented.

Changes
=======
* 1.0.4 - Bug fix thanks to [Njal Karevoll](https://github.com/nkvoll).  No longer relies on newline after the null-byte frame separator.  Library is now compatible with RabbitMQ stomp adapter.
* 1.1.1 - Thanks to [nikipore](https://github.com/nikipore) for adding support for binary messages.
* 1.1.2 - Fixed issue with stomper adding a space in ACK message-id header. ActiveMQ 5.6.0 no longer tolerates this.
* 2.0a1 - Complete redesign: feature-complete implementation of STOMP 1.0 and 1.1 (except heartbeat). Broker failover. Decoupled from [stomper](http://code.google.com/p/stomper/).