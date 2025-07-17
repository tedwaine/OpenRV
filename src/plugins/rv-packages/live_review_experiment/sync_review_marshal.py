from rv import commands, extra_commands
from rv import rvtypes
from rv.rvtypes import MinorMode

from datetime import datetime, timezone

import os
import json
import re
import uuid

import otio_writer
import otio_reader


class SyncReviewMarshal(MinorMode):
    sending_event = False
    updating_playbacksettings = False
    muted = False
    queue_name = ""

    stroke_uuid = None
    pen_down = False
    received_strokes = {}
    point_width = None
    point_coords = []

    def __init__(self):
        super(SyncReviewMarshal, self).__init__()

        self.init(
            "sync_review_marshal",
            [
                (
                    "after-progressive-loading",
                    self.send_graph_change,
                    "Turn the visible graph into a sync review payload",
                ),
                (
                    "play-start",
                    self.send_playback_start,
                    "Turn the playack settings into a sync review payload",
                ),
                (
                    "play-stop",
                    self.send_playback_stop,
                    "Turn the playack settings into a sync review payload",
                ),
                (
                    "frame-changed",
                    self.send_frame_changed,
                    "Turn the playack settings into a sync review payload",
                ),
                (
                    "sync-review-change-received",
                    self.receive_change_event,
                    "",
                ),
                (
                    "sync-review-queue-name-change",
                    self.set_queue_name,
                    "",
                ),
                (
                    "before-clear-session",
                    self.send_clear_session,
                    "Send clear sync review payload",
                ),
                # Annotations
                (
                    "graph-state-change",
                    self.send_graph_state_change,
                    "Turn the graph state change into a sync review payload",
                ),
                (
                    "pointer--control--leave",
                    self.check_paint_end,
                    "Turn the graph state change into a sync review payload",
                ),
                (
                    "pointer--leave",
                    self.check_paint_end,
                    "Turn the graph state change into a sync review payload",
                ),
                (
                    "pointer-1--release",
                    self.check_paint_end,
                    "Turn the graph state change into a sync review payload",
                ),
            ],
            None,
        )

    @staticmethod
    def get_otio_time(value):
        """
        Return an OTIO RationalTime corresponding to the current time
        """
        # TODO: There's no __dict__ method on RationalTime, so do it manually for now
        return {
            "OTIO_SCHEMA": "RationalTime.1",
            "rate": commands.fps(),
            "value": value,
        }

    @staticmethod
    def get_current_otio_time():
        """
        Return an OTIO RationalTime corresponding to the current time
        """
        # TODO: There's no __dict__ method on RationalTime, so do it manually for now
        return SyncReviewMarshal.get_otio_time(commands.frame())

    @staticmethod
    def get_current_otio_time_range(duration=1):
        """
        Return an OTIO RationalTime corresponding to the current time
        """
        # TODO: There's no __dict__ method on RationalTime, so do it manually for now
        return {
            "OTIO_SCHEMA": "TimeRange.1",
            "start_time": SyncReviewMarshal.get_current_otio_time(),
            "duration": SyncReviewMarshal.get_otio_time(1),
        }

    @staticmethod
    def get_otio_point(x, y, size):
        """
        Return an OTIO RationalTime corresponding to the current time
        """
        # TODO: There's no __dict__ method on RationalTime, so do it manually for now
        return {
            "OTIO_SCHEMA": "TimeRange.1",
            "x": x,
            "y": y,
            "size": size,
        }

    @staticmethod
    def extract_frame_payload(payload):
        """
        Return an OTIO RationalTime corresponding to the current time
        """
        # TODO: There's no __dict__ method on RationalTime, so do it manually for now

        return {
            "OTIO_SCHEMA": "RationalTime.1",
            "rate": commands.fps(),
            "value": commands.frame(),
        }

    @staticmethod
    def send_sync_review_event(event_name, payload):
        """
        Sends an event with a json payload
        """
        if SyncReviewMarshal.sending_event or SyncReviewMarshal.muted:
            return

        if os.environ.get("DEBUG_SYNC_REVIEW"):
            print(f"SEND MESSAGE to session {SyncReviewMarshal.queue_name}: {payload}")

        commands.sendInternalEvent(
            event_name,
            json.dumps(
                {
                    "schema": "SYNC_REVIEW_1.0",
                    "session": SyncReviewMarshal.queue_name,
                    "payload": payload,
                },
                separators=(",", ":"),
                indent=1,
                sort_keys=True,
            ),
        )

    @staticmethod
    def marshal_node(node):
        """
        Converts a node graph into a sync review session message
        """
        SyncReviewMarshal.send_sync_review_event(
            "sync-review-change",
            {
                "command_schema": "OTIO_SESSION_1.0",
                "command": {
                    "event": "SET",
                    "payload": {
                        "otio": json.loads(otio_writer.write_otio_string(node)),
                    },
                },
            },
        )

    @staticmethod
    def marshal_playback_settings(**kwargs):
        """
        Takes the kwargs turns it into sync review playback message
        """
        SyncReviewMarshal.send_sync_review_event(
            "sync-review-change",
            {
                "command_schema": "PLAYBACK_SETTINGS_1.0",
                "command": {
                    "event": "SET",
                    "payload": kwargs,
                },
            },
        )

    @staticmethod
    def marshal_paint_event(paint_event, **kwargs):
        """
        Takes the kwargs turns it into a paint message
        """
        SyncReviewMarshal.send_sync_review_event(
            "sync-review-change",
            {
                "command_schema": "Annotation.1",
                "command": {
                    "event": paint_event,
                    "payload": kwargs,
                },
            },
        )

    @staticmethod
    def send_paint_start(point_prop):
        prop_base = point_prop[:-7]

        SyncReviewMarshal.marshal_paint_event(
            "PaintStart",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            # source_index = 0, # not needed for now, so not setting it
            paint={
                "OTIO_SCHEMA": "Paint.1",
                "uuid": str(SyncReviewMarshal.stroke_uuid),
                "rgba": commands.getFloatProperty(f"{prop_base}.color"),
                "type": "COLOR",
                "brush": commands.getStringProperty(f"{prop_base}.brush")[0],
                "visible": True,
                "name": "Paint",
                "effect_name": "Paint",
                "layer_range": SyncReviewMarshal.get_current_otio_time_range(
                    duration=commands.getIntProperty(f"{prop_base}.duration")
                ),
                "hold": commands.getIntProperty(f"{prop_base}.hold")[0] != 0,
                "ghost": commands.getIntProperty(f"{prop_base}.ghost")[0] != 0,
                "ghost_before": commands.getIntProperty(f"{prop_base}.ghostBefore")[0],
                "ghost_after": commands.getIntProperty(f"{prop_base}.ghostAfter")[0],
            },
        )

    @staticmethod
    def send_paint_point(prop):
        prop_base = ".".join(prop.split(".")[:-1])

        width_prop = commands.getFloatProperty(f"{prop_base}.width")
        if len(width_prop) > 0:
            SyncReviewMarshal.point_width = width_prop[0]

        point_prop = commands.getFloatProperty(f"{prop_base}.points")
        if len(point_prop) > 0:
            SyncReviewMarshal.point_coords = point_prop

        # Wait until both width and point coordinates are set before sending the event
        if (
            len(SyncReviewMarshal.point_coords) == 0
            or SyncReviewMarshal.point_width is None
        ):
            return

        SyncReviewMarshal.marshal_paint_event(
            "PaintPoint",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            point_target={
                # "source_index": 0, # not needed for now so not setting it
                "uuid": str(SyncReviewMarshal.stroke_uuid),
                "range": SyncReviewMarshal.get_current_otio_time_range(
                    duration=commands.getIntProperty(f"{prop_base}.duration")
                ),
            },
            point=SyncReviewMarshal.get_otio_point(
                SyncReviewMarshal.point_coords[-2],
                SyncReviewMarshal.point_coords[-1],
                SyncReviewMarshal.point_width,
            ),
        )
        SyncReviewMarshal.point_width = None
        SyncReviewMarshal.point_coords = []

    @staticmethod
    def send_paint_end():
        SyncReviewMarshal.marshal_paint_event(
            "PaintEnd",
            uuid=str(SyncReviewMarshal.stroke_uuid),
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            points=[],
        )

    @staticmethod
    def extract_payload(message):
        """
        Extracts a message payload for the supplied command_schema
        """
        if os.environ.get("DEBUG_SYNC_REVIEW"):
            print(
                f"RECEIVE MESSAGE from session {SyncReviewMarshal.queue_name}: {message}"
            )

        message_json = json.loads(message)
        if message_json.get("schema") != "SYNC_REVIEW_1.0":
            print(f"Unhandled message schema: {message_json.get('schema')}")
            return "", ""

        payload = message_json.get("payload")
        if payload is None:
            print(f"Message has no payload: {message}")
            return "", ""

        command_schema = payload.get("command_schema")
        if command_schema is None:
            print(f"Message has no command_schema: {message}")
            return "", ""

        command = payload.get("command")
        if command is None:
            print(f"message has no command: {message}")
            return "", ""

        return command_schema, command

    @staticmethod
    def send_graph_change(event):
        """
        Takes the currently viewed node and turns it into sync review message
        """
        event.reject()
        SyncReviewMarshal.marshal_node(commands.viewNode())

    @staticmethod
    def stroke_end():
        if SyncReviewMarshal.stroke_uuid is not None:
            SyncReviewMarshal.send_paint_end()
            SyncReviewMarshal.stroke_uuid = None

    @staticmethod
    def send_graph_state_change(event):
        """
        Takes the currently viewed node and turns it into sync review message
        """
        event.reject()
        if SyncReviewMarshal.sending_event:
            return

        match event.contents():
            case prop if re.search(r"paint\.nextId$", prop):
                SyncReviewMarshal.stroke_end()
                SyncReviewMarshal.stroke_uuid = uuid.uuid4()
                SyncReviewMarshal.pen_down = True

            case prop if re.search(r".pen:\d+:\d+:.+points$", prop) or re.search(
                r".pen:\d+:\d+:.+width$", prop
            ):
                if SyncReviewMarshal.pen_down == True:
                    SyncReviewMarshal.pen_down = False
                    SyncReviewMarshal.send_paint_start(prop)
                SyncReviewMarshal.send_paint_point(prop)

    @staticmethod
    def check_paint_end(event):
        event.reject()
        SyncReviewMarshal.stroke_end()

    @staticmethod
    def send_playback_start(event):
        """
        Sends a synced review message that playback started
        """
        event.reject()

        if SyncReviewMarshal.updating_playbacksettings:
            return

        SyncReviewMarshal.marshal_playback_settings(
            playing=True, current_time=SyncReviewMarshal.get_current_otio_time()
        )

    @staticmethod
    def send_playback_stop(event):
        """
        Sends a synced review message that playback stopped
        """
        event.reject()

        if SyncReviewMarshal.updating_playbacksettings:
            return

        SyncReviewMarshal.marshal_playback_settings(
            playing=False, current_time=SyncReviewMarshal.get_current_otio_time()
        )

    @staticmethod
    def receive_change_event(event):
        """
        Receives a change message and updates the graph
        """
        event.reject()
        command_schema, command = SyncReviewMarshal.extract_payload(event.contents())
        if not command_schema or not command:
            return

        if command_schema.startswith("OTIO_SESSION_1"):
            print("Processing OTIO_SESSION_1 Change")
            return SyncReviewMarshal.receive_graph_change(command)
        elif command_schema.startswith("PLAYBACK_SETTINGS_1"):
            print("Processing PLAYBACK_SETTINGS_1 Change")
            return SyncReviewMarshal.receive_playback_change(command)
        elif command_schema.startswith("Annotation.1"):
            print("Processing Annotations")
            return SyncReviewMarshal.receive_annotation_change(command)

    @staticmethod
    def set_queue_name(event):
        """
        Receives the current name of the message queue
        """
        event.reject()
        SyncReviewMarshal.queue_name = event.contents()

    @staticmethod
    def receive_graph_change(command):
        """
        Receives a graph change message and updates the graph
        """
        event_type = command.get("event")
        if event_type not in ["CLEAR", "SET"]:
            return

        payload = command.get("payload")

        if payload:
            new_otio = payload.get("otio")
            new_otio = json.dumps(new_otio, indent=1, sort_keys=True)
        else:
            new_otio = "{}"

        # Not really optimal, but required to compare both otio strings
        old_otio = otio_writer.write_otio_string(commands.viewNode())
        old_otio = json.loads(old_otio)
        old_otio = json.dumps(old_otio, indent=1, sort_keys=True)

        if new_otio == old_otio:
            return

        print(f"Updating Graph using OTIO\n{new_otio}")

        SyncReviewMarshal.sending_event = True
        try:
            commands.clearSession()

            if new_otio != "{}":
                root_node = otio_reader.read_otio_string(new_otio)
                commands.setViewNode(root_node)
        finally:
            SyncReviewMarshal.sending_event = False

    @staticmethod
    def receive_playback_change(command):
        """
        Recieves a playback settings messages and updates the playback settings
        """

        if command.get("event") != "SET":
            return

        payload = command.get("payload")
        if payload is None:
            return

        SyncReviewMarshal.updating_playbacksettings = True
        try:
            playing = payload.get("playing")
            if playing is not None:
                if playing:
                    commands.play()
                else:
                    commands.stop()
                    current_time = payload.get("current_time")
                    if current_time:
                        frame = current_time.get("value")
                        if frame:
                            commands.setFrame(frame)
        finally:
            SyncReviewMarshal.updating_playbacksettings = False

    @staticmethod
    def receive_annotation_change(command):
        """
        Receives annotation message and updates the graph
        """
        payload = command.get("payload")
        if payload is None:
            return

        SyncReviewMarshal.sending_event = True
        try:
            match command.get("event"):
                case "PaintStart":
                    SyncReviewMarshal.receive_paint_start(payload)
                case "PaintPoint":
                    SyncReviewMarshal.receive_paint_point(payload)
                case "PaintEnd":
                    SyncReviewMarshal.receive_paint_end(payload)

        finally:
            SyncReviewMarshal.sending_event = False

    @staticmethod
    def receive_paint_start(payload):
        """
        Receives paint start command and starts the strok
        """
        paint = payload.get("paint", {})
        layer_range = paint.get("layer_range", {})

        start_frame = layer_range.get("start_time", {}).get("value")
        duration = layer_range.get("duration", {}).get("value")
        uuid = paint.get("uuid")

        if start_frame is None or duration is None or uuid is None:
            return

        frame = start_frame + duration - 1  # assuming same rate here

        source_node = commands.sourcesAtFrame(frame)[0]

        # RV expects the frame id in the source node to be in source timing, so 
        # convert global time to source time, assuming global time starts at 1 here
        source_data = commands.sourceMediaInfoList(source_node)[0]
        source_frame = source_data["startFrame"] + start_frame - 1

        paint_node = extra_commands.associatedNode("RVPaint", source_node)

        paint_component = f"{paint_node}.paint"
        stroke_id = commands.getIntProperty(f"{paint_component}.nextId")[0]

        # No user id in payload, so just using "annotation" for now
        pen_component = f"{paint_node}.pen:{stroke_id}:{source_frame}:annotation"

        SyncReviewMarshal.received_strokes[uuid] = pen_component

        if not commands.propertyExists(f"{pen_component}.brush"):
            commands.newProperty(f"{pen_component}.brush", commands.StringType, 1)

        commands.setStringProperty(f"{pen_component}.brush", [paint["brush"]], True)

        if not commands.propertyExists(f"{pen_component}.color"):
            commands.newProperty(f"{pen_component}.color", commands.FloatType, 4)

        commands.setFloatProperty(
            f"{pen_component}.color", [float(x) for x in paint["rgba"]], True
        )

        if not commands.propertyExists(f"{pen_component}.debug"):
            commands.newProperty(f"{pen_component}.debug", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.debug", [False], True)

        if not commands.propertyExists(f"{pen_component}.join"):
            commands.newProperty(f"{pen_component}.join", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.join", [3], True)

        if not commands.propertyExists(f"{pen_component}.cap"):
            commands.newProperty(f"{pen_component}.cap", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.cap", [1], True)

        if not commands.propertyExists(f"{pen_component}.splat"):
            commands.newProperty(f"{pen_component}.splat", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.splat", [0], True)

        if not commands.propertyExists(f"{pen_component}.mode"):
            commands.newProperty(f"{pen_component}.mode", commands.IntType, 1)

        commands.setIntProperty(
            f"{pen_component}.mode", [0 if paint["type"] == "COLOR" else 1], True
        )

        if not commands.propertyExists(f"{pen_component}.startFrame"):
            commands.newProperty(f"{pen_component}.startFrame", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.startFrame", [source_frame], True)

        if not commands.propertyExists(f"{pen_component}.duration"):
            commands.newProperty(f"{pen_component}.duration", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.duration", [duration], True)

        if not commands.propertyExists(f"{pen_component}.hold"):
            commands.newProperty(f"{pen_component}.hold", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.hold", [paint["hold"]], True)

        if not commands.propertyExists(f"{pen_component}.ghost"):
            commands.newProperty(f"{pen_component}.ghost", commands.IntType, 1)

        commands.setIntProperty(f"{pen_component}.ghost", [paint["ghost"]], True)

        if not commands.propertyExists(f"{pen_component}.ghostBefore"):
            commands.newProperty(f"{pen_component}.ghostBefore", commands.IntType, 1)

        commands.setIntProperty(
            f"{pen_component}.ghostBefore", [paint["ghost_before"]], True
        )

        if not commands.propertyExists(f"{pen_component}.ghostAfter"):
            commands.newProperty(f"{pen_component}.ghostAfter", commands.IntType, 1)

        commands.setIntProperty(
            f"{pen_component}.ghostAfter", [paint["ghost_after"]], True
        )

    @staticmethod
    def receive_paint_point(payload):
        uuid = payload.get("point_target", {}).get("uuid")
        point = payload.get("point")

        if uuid is None or point is None:
            return

        pen_component = SyncReviewMarshal.received_strokes[uuid]

        frame_component = (
            f"{pen_component.split('.pen')[0]}.frame:{pen_component.split(':')[2]}"
        )
        if not commands.propertyExists(f"{frame_component}.order"):
            commands.newProperty(f"{frame_component}.order", commands.StringType, 1)

        order = pen_component.split(".")[1]
        order_property = commands.getStringProperty(f"{frame_component}.order")
        if order not in order_property:
            commands.insertStringProperty(f"{frame_component}.order", [order])

        if not commands.propertyExists(f"{pen_component}.points"):
            commands.newProperty(f"{pen_component}.points", commands.FloatType, 2)

        commands.insertFloatProperty(
            f"{pen_component}.points", [point["x"], point["y"]], True
        )

        if not commands.propertyExists(f"{pen_component}.width"):
            commands.newProperty(f"{pen_component}.width", commands.FloatType, 1)

        commands.insertFloatProperty(f"{pen_component}.width", [point["size"]], True)

    @staticmethod
    def receive_paint_end(payload):
        uuid = payload.get("uuid")
        if uuid is None:
            return

        pen_component = SyncReviewMarshal.received_strokes[uuid]
        paint_component = f"{pen_component.split('.')[0]}.paint"
        stroke_id = commands.getIntProperty(f"{paint_component}.nextId")[0]

        commands.setIntProperty(f"{paint_component}.nextId", [stroke_id + 1], True)
        commands.setIntProperty(f"{paint_component}.show", [True], True)

        del SyncReviewMarshal.received_strokes[uuid]

    @staticmethod
    def send_frame_changed(event):
        """
        Sends a synced review message that frame has changed when
        not playing
        """
        event.reject()

        if commands.isPlaying():
            return

        if SyncReviewMarshal.updating_playbacksettings:
            return

        SyncReviewMarshal.marshal_playback_settings(
            playing=commands.isPlaying(),
            current_time=SyncReviewMarshal.get_current_otio_time(),
        )

    @staticmethod
    def send_clear_session(event):
        """
        Send a sync review playback message to clear the session
        """
        event.reject()
        SyncReviewMarshal.send_sync_review_event(
            "sync-review-change",
            {
                "command_schema": "OTIO_SESSION_1.0",
                "command": {
                    "event": "CLEAR",
                    "payload": None,
                },
            },
        )

    @staticmethod
    def set_muted(value):
        """
        Send a sync review playback message to clear the session
        """
        event.reject()
        SyncReviewMarshal.muted = value


_mode = None


def createMode():
    global _mode
    _mode = SyncReviewMarshal()
    return _mode


def getMode():
    return _mode or createMode()
