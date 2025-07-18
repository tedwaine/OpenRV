import os
import platform
import ssl
import logging

import pika
from PySide6 import QtCore, QtWidgets
from rv import qtutils
from rv.commands import (
    DisabledMenuState,
    NeutralMenuState,
    defineModeMenu,
    sendInternalEvent,
    theTime,
)
from rv.rvtypes import MinorMode

import sys
sys.path.append(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "..", "SupportFiles", "live_review_experiement"
    )           
)               
from mq_consumer import MQReconnectingConsumer
from mq_publisher import MQPublisher

class MessageQueueImplementation(MinorMode, QtCore.QObject):
    def __init__(self):
        MinorMode.__init__(self)
        QtCore.QObject.__init__(self, qtutils.sessionWindow())

        self.__pika_credentials = os.environ.get("RV_AMQP_CREDENTIALS", "")
        self.__pika_current_exchange = os.environ.get("RV_AMQP_DEFAULT_EXCHANGE", "")
        self.__pika_consumer = None
        self.__pika_pub_connection = None
        self.__pika_channel = None
        self.__pika_consumer_tag = None
        self.__pika_current_queue = None

        self.__uuid = theTime()

        self.init(
            self.menu_name.replace(" ", ""),
            self.global_bindings,
            self.local_bindings,
            self.menu,
        )

    #
    # MinorMode properties
    #

    @property
    def menu_name(self):
        return "ASWF Live Review"

    @property
    def global_bindings(self):
        return [
            (
                "sync-review-change",
                self.send_payload_to_queue,
                "Turn the playack settings into a sync review payload",
            )
        ]

    @property
    def local_bindings(self):
        return None

    @property
    def menu(self):
        if not self.mq_consumer:
            return [
                (
                    self.menu_name,
                    [
                        (
                            "Join Review Server",
                            self.join_review_server,
                            None,
                            lambda: NeutralMenuState,
                        )
                    ],
                )
            ]
        elif not self.in_session:
            return [
                (
                    self.menu_name,
                    [
                        (
                            "Create Review",
                            self.create_review,
                            None,
                            lambda: NeutralMenuState,
                        ),
                        (
                            "Join Review",
                            self.join_review,
                            None,
                            lambda: NeutralMenuState,
                        ),
                        (
                            "Leave Review Server",
                            self.leave_review_server,
                            None,
                            lambda: NeutralMenuState,
                        ),
                    ],
                )
            ]
        else:
            return [
                (
                    self.menu_name,
                    [
                        (
                            f"Leave {self.mq_exchange}",
                            self.leave_review,
                            None,
                            lambda: NeutralMenuState,
                        )
                    ],
                )
            ]

    def send_payload_to_queue(self, event):
        if self.in_session:
            self.mq_publisher.send_message(event.contents())

    def join_review_server(self, event=None):
        sw = qtutils.sessionWindow()
        creds, ok = QtWidgets.QInputDialog.getText(
            sw,
            "Joining Review Server",
            "Review Server Credentials",
            text=self.mq_credentials,
        )

        if ok:
            self.mq_credentials = creds
            self.mq_consumer = MQReconnectingConsumer(self, self.review_uuid, creds)
            self.mq_consumer.mq_message.connect(self.incoming_message)
            self.mq_publisher = MQPublisher(self, self.review_uuid, creds)
            
    def incoming_message(self, body):
        sendInternalEvent("sync-review-change-received", body)

    def create_review_session(self, session_name):
        mq_exchange = session_name
        self.mq_consumer.mq_connect(mq_exchange)
        self.mq_publisher.mq_connect(mq_exchange)

    def create_review(self, event=None):
        sw = qtutils.sessionWindow()
        id, ok = QtWidgets.QInputDialog.getText(
            sw,
            "Creating a Review Session",
            "Review Session ID:",
            text=self.mq_exchange,
        )
        if ok:
            self.create_review_session(id)

    def join_review_session(self, session_name):
        mq_exchange = session_name
        self.mq_consumer.mq_connect(session_name)
        self.mq_publisher.mq_connect(session_name)

    def join_review(self, event=None):
        sw = qtutils.sessionWindow()
        id, ok = QtWidgets.QInputDialog.getText(
            sw,
            "Joining a Review Session",
            "Review Session ID:",
            text=self.mq_exchange,
        )

        if ok:
            self.join_review_session(id)

    def leave_review(self, event=None):
        pass

    def leave_review_server(self, event=None):
        pass

    #
    # Review Session properties
    #

    @property
    def review_uuid(self):
        return f"{os.getlogin()}@{platform.uname().node}/{self.__uuid}"

    @property
    def in_session(self):
        return bool(self.mq_consumer) and self.mq_consumer.connected

    @property
    def mq_credentials(self):
        return self.__pika_credentials

    @mq_credentials.setter
    def mq_credentials(self, value):
        self.__pika_credentials = value

    @property
    def mq_consumer(self):
        return self.__pika_consumer

    @mq_consumer.setter
    def mq_consumer(self, value):
        self.__pika_consumer = value
        defineModeMenu(self.menu_name.replace(" ", ""), self.menu, True)

    @property
    def mq_publisher(self):
        return self.__pika_pub_connection

    @mq_publisher.setter
    def mq_publisher(self, value):
        self.__pika_pub_connection = value

    @property
    def mq_exchange(self):
        return self.__pika_current_exchange or ""

    @mq_exchange.setter
    def mq_exchange(self, value):
        self.__pika_current_exchange = value
        defineModeMenu(self.menu_name.replace(" ", ""), self.menu, True)


_mode = None


def createMode():
    global _mode
    _mode = MessageQueueImplementation()
    return _mode


def getMode():
    return _mode
