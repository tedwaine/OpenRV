from PySide6 import QtCore, QtWidgets
import functools
import pika
import json
from pika.exchange_type import ExchangeType

class MQPublisheImpl(QtCore.QObject):
    """Largely based on Pika example code
    """
    EXCHANGE_TYPE = ExchangeType.fanout
    PUBLISH_INTERVAL = 1

    connection_status = QtCore.Signal(bool, str)

    def __init__(self, parent, publisher_uuid, ampq_uri, exchange):

        QtCore.QObject.__init__(self, parent)

        self._connection = None
        self._channel = None

        self._deliveries = None
        self._acked = None
        self._nacked = None
        self._message_number = None

        self._stopping = False
        self._ampq_uri = ampq_uri
        self._exchange = exchange
        self._publisher_uuid = publisher_uuid

    def mq_connect(self):
        """This method connects to RabbitMQ, returning the connection handle.
        When the connection is established, the on_connection_open method
        will be invoked by pika.

        :rtype: pika.SelectConnection

        """
        
        print('Publisher connecting to ampq:%s' % (self._ampq_uri))

        parameters = pika.URLParameters(self._ampq_uri)
        return pika.SelectConnection(
            parameters,
            on_open_callback=self.on_connection_open,
            on_open_error_callback=self.on_connection_open_error,
            on_close_callback=self.on_connection_closed)

    def on_connection_open(self, _unused_connection):
        """This method is called by pika once the connection to RabbitMQ has
        been established. It passes the handle to the connection object in
        case we need it, but in this case, we'll just mark it unused.

        :param pika.SelectConnection _unused_connection: The connection

        """
        print('Publisher: Connection opened')
        self.open_channel()

    def on_connection_open_error(self, _unused_connection, err):
        """This method is called by pika if the connection to RabbitMQ
        can't be established.

        :param pika.SelectConnection _unused_connection: The connection
        :param Exception err: The error

        """
        print('Publisher: Connection open failed, reopening in 5 seconds: %s' % (err))
        self.connection_status.emit(False, 'Connection failed: {} {}'.format(err, type(err)))
        self._connection.ioloop.call_later(5, self._connection.ioloop.stop)

    def on_connection_closed(self, _unused_connection, reason):
        """This method is invoked by pika when the connection to RabbitMQ is
        closed unexpectedly. Since it is unexpected, we will reconnect to
        RabbitMQ if it disconnects.

        :param pika.connection.Connection connection: The closed connection obj
        :param Exception reason: exception representing reason for loss of
            connection.

        """
        self._channel = None
        if self._stopping:
            self._connection.ioloop.stop()
        else:
            print('Publisher: Connection closed, reopening in 5 seconds: %s' % (reason))
            self._connection.ioloop.call_later(5, self._connection.ioloop.stop)
        self.connection_status.emit(False, 'Connection closed {}'.format(reason))


    def open_channel(self):
        """This method will open a new channel with RabbitMQ by issuing the
        Channel.Open RPC command. When RabbitMQ confirms the channel is open
        by sending the Channel.OpenOK RPC reply, the on_channel_open method
        will be invoked.

        """
        print('Publisher: Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        """This method is invoked by pika when the channel has been opened.
        The channel object is passed in so we can make use of it.

        Since the channel is now open, we'll declare the exchange to use.

        :param pika.channel.Channel channel: The channel object

        """
        print('Publisher: Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self._exchange)

    def add_on_channel_close_callback(self):
        """This method tells pika to call the on_channel_closed method if
        RabbitMQ unexpectedly closes the channel.

        """
        print('Publisher: Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reason):
        """Invoked by pika when RabbitMQ unexpectedly closes the channel.
        Channels are usually closed if you attempt to do something that
        violates the protocol, such as re-declare an exchange or queue with
        different parameters. In this case, we'll close the connection
        to shutdown the object.

        :param pika.channel.Channel channel: The closed channel
        :param Exception reason: why the channel was closed

        """
        print('Publisher: Channel %i was closed: %s', channel, reason)
        self._channel = None
        if not self._stopping:
            self._connection.close()
        self.connection_status.emit(False, 'Channel {} was closed: {}'.format(channel, reason))

    def setup_exchange(self, exchange_name):
        """Setup the exchange on RabbitMQ by invoking the Exchange.Declare RPC
        command. When it is complete, the on_exchange_declareok method will
        be invoked by pika.

        :param str|unicode exchange_name: The name of the exchange to declare

        """
        print('Publisher: Declaring exchange %s', exchange_name)
        # Note: using functools.partial is not required, it is demonstrating
        # how arbitrary data can be passed to the callback when it is called
        cb = functools.partial(self.on_exchange_declareok,
                               userdata=exchange_name)
        self._channel.exchange_declare(exchange=exchange_name,
                                       exchange_type=self.EXCHANGE_TYPE,
                                       auto_delete=True,
                                       callback=cb)

    def on_exchange_declareok(self, _unused_frame, userdata):
        """Invoked by pika when RabbitMQ has finished the Exchange.Declare RPC
        command.

        :param pika.Frame.Method unused_frame: Exchange.DeclareOk response frame
        :param str|unicode userdata: Extra user data (exchange name)

        """
        print('Publisher: Exchange declared: %s', userdata)
        self.setup_queue(self._publisher_uuid)

    def setup_queue(self, queue_name):
        """Setup the queue on RabbitMQ by invoking the Queue.Declare RPC
        command. When it is complete, the on_queue_declareok method will
        be invoked by pika.

        :param str|unicode queue_name: The name of the queue to declare.

        """
        print('Declaring queue %s' % (queue_name))
        self._channel.queue_declare(queue=queue_name,
                                    callback=self.on_queue_declareok)

    def on_queue_declareok(self, _unused_frame):
        """Method invoked by pika when the Queue.Declare RPC call made in
        setup_queue has completed. In this method we will bind the queue
        and exchange together with the routing key by issuing the Queue.Bind
        RPC command. When this command is complete, the on_bindok method will
        be invoked by pika.

        :param pika.frame.Method method_frame: The Queue.DeclareOk frame

        """
        print('Publisher: Binding %s to %s with %s' % (self._exchange, self._publisher_uuid, '#'))
        self._channel.queue_bind(self._publisher_uuid,
                                 self._exchange,
                                 routing_key='#',
                                 callback=self.on_bindok)

    def on_bindok(self, _unused_frame):
        """This method is invoked by pika when it receives the Queue.BindOk
        response from RabbitMQ. Since we know we're now setup and bound, it's
        time to start publishing."""
        print('Publisher: Queue bound')
        self.start_publishing()

    def start_publishing(self):
        """This method will enable delivery confirmations and schedule the
        first message to be sent to RabbitMQ

        """
        print('Publisher: Issuing consumer related RPC commands')
        self.enable_delivery_confirmations()

    def enable_delivery_confirmations(self):
        """Send the Confirm.Select RPC method to RabbitMQ to enable delivery
        confirmations on the channel. The only way to turn this off is to close
        the channel and create a new one.

        When the message is confirmed from RabbitMQ, the
        on_delivery_confirmation method will be invoked passing in a Basic.Ack
        or Basic.Nack method from RabbitMQ that will indicate which messages it
        is confirming or rejecting.

        """
        print('Publisher: Issuing Confirm.Select RPC command')
        self._channel.confirm_delivery(self.on_delivery_confirmation)

    def on_delivery_confirmation(self, method_frame):
        """Invoked by pika when RabbitMQ responds to a Basic.Publish RPC
        command, passing in either a Basic.Ack or Basic.Nack frame with
        the delivery tag of the message that was published. The delivery tag
        is an integer counter indicating the message number that was sent
        on the channel via Basic.Publish. Here we're just doing house keeping
        to keep track of stats and remove message numbers that we expect
        a delivery confirmation of from the list used to keep track of messages
        that are pending confirmation.

        :param pika.frame.Method method_frame: Basic.Ack or Basic.Nack frame

        """
        confirmation_type = method_frame.method.NAME.split('.')[1].lower()
        ack_multiple = method_frame.method.multiple
        delivery_tag = method_frame.method.delivery_tag

        if confirmation_type == 'ack':
            self._acked += 1
        elif confirmation_type == 'nack':
            self._nacked += 1

        del self._deliveries[delivery_tag]

        if ack_multiple:
            for tmp_tag in list(self._deliveries.keys()):
                if tmp_tag <= delivery_tag:
                    self._acked += 1
                    del self._deliveries[tmp_tag]

    def safe_stop(self):

        self._connection.ioloop.add_callback_threadsafe(
            functools.partial(self.stop)
            )

    def queue_message(self, message_data):

        if self._connection:
            self._connection.ioloop.add_callback_threadsafe(
                functools.partial(self.publish_message, message=message_data)
                )

    def publish_message(self, message):
        """If the class is not stopping, publish a message to RabbitMQ,
        appending a list of deliveries with the message number that was sent.
        This list will be used to check for delivery confirmations in the
        on_delivery_confirmations method.

        Once the message has been sent, schedule another message to be sent.
        The main reason I put scheduling in was just so you can get a good idea
        of how the process is flowing by slowing down and speeding up the
        delivery intervals by changing the PUBLISH_INTERVAL constant in the
        class.

        """
        if self._channel is None or not self._channel.is_open:
            return

        properties = pika.BasicProperties(app_id=self._publisher_uuid,
                                          content_type='application/json')

        self._channel.basic_publish(self._exchange, "",
                                    json.dumps(message, ensure_ascii=False),
                                    properties)
        self._message_number += 1
        self._deliveries[self._message_number] = True

    def run(self):
        """Run the example code by connecting and then starting the IOLoop.

        """

        while not self._stopping:
            self._connection = self.mq_connect()
            self._deliveries = {}
            self._acked = 0
            self._nacked = 0
            self._message_number = 0
            self.connection_status.emit(True, 'Publisher loop running')
            self._connection.ioloop.start()
            self._connection = None
        self.connection_status.emit(False, 'IO Loop exited')

    def stop(self):
        """Stop the example by closing the channel and connection. We
        set a flag here so that we stop scheduling new messages to be
        published. The IOLoop is started because this method is
        invoked by the Try/Catch below when KeyboardInterrupt is caught.
        Starting the IOLoop again will allow the publisher to cleanly
        disconnect from RabbitMQ.

        """
        self._stopping = True
        self.close_channel()
        self.close_connection()

    def close_channel(self):
        """Invoke this command to close the channel with RabbitMQ by sending
        the Channel.Close RPC command.

        """
        if self._channel is not None:
            self._channel.close()
            self.connection_status.emit(False, 'Channel closed')

    def close_connection(self):
        """This method closes the connection to RabbitMQ."""
        if self._connection is not None:
            print('Closing connection')
            self._connection.close()
        self.connection_status.emit(False, 'Connection closed')

class MQPublisher(QtCore.QThread):
    """This consumer will reconnect if the nested
    MQConsumer indicates that a reconnect is necessary.
    """

    mq_message = QtCore.Signal(str)
    connection_status = QtCore.Signal(bool, str)
    do_print = QtCore.Signal(str)

    def __init__(self, parent, publisher_uuid, qmpq_uri):
        QtCore.QThread.__init__(self, parent)
        self._publisher = None
        self._publisher_uuid = publisher_uuid
        self._qmpq_uri = qmpq_uri
        self._exchange = None
        self._is_connected = False

    def connection_status(self, is_connected_ok, msg):
        print (f"Connection status changed: {is_connected_ok} - {msg}")
        _is_connected = is_connected_ok

    def mq_connect(self, exchange):
        self._exchange = exchange
        self._publisher = MQPublisheImpl(None, self._publisher_uuid, self._qmpq_uri, self._exchange)
        self._publisher.moveToThread(self)
        self.mq_message.emit("TEST")
        self._publisher.connection_status.connect(self.connection_status)
        self.start()

    def run(self):
        while True:
            try:
                self._publisher.run()
            except Exception as e:
                # python print in a thread can crash RV. Probably to do with
                # the console capturing python output
                self.do_print.emit(e)
                break
            self._maybe_reconnect()

    def printer(self, data):
        print(data)

    def send_message(self, msg):
        self._publisher.queue_message(msg)

    def safe_stop(self):
        self._publisher.safe_stop()

    @property
    def connected(self):
        return self._is_connected

