#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import flask
import asfpy.messaging
import netaddr
import requests
import logging
import yaml
import os
import uuid

"""GitHub Discussions Notifier"""

REPO_ROOT = "/x1/repos/asf"
VALID_THREAD_ACTIONS = ["created", "edited", "deleted"]
VALID_COMMENT_ACTIONS = ["created", "edited", "deleted"]
THREAD_ACTION = open("templates/thread-action.txt").read()
COMMENT_ACTION = open("templates/comment-action.txt").read()


def get_recipient(repo):
    yaml_path = os.path.join(REPO_ROOT, f"{repo}.git", "notifications.yaml")
    if os.path.exists(yaml_path):
        yml = yaml.safe_load(open(yaml_path, "r").read())
        if "discussions" in yml:
            return yml["discussions"]
    return None


def parse_thread_action(blob):
    """Parses a thread action (thread created/edited/deleted)"""
    action = blob.get("action")
    discussion = blob.get("discussion")
    user = discussion.get("user").get("login")
    title = discussion.get("title")
    category = discussion.get("category").get("slug")
    url = discussion.get("html_url")
    body = discussion.get("body")
    repo = blob.get("repository").get("name")
    node_id = discussion.get("node_id")
    if action in VALID_THREAD_ACTIONS:
        recipient = get_recipient(repo)
        if recipient:
            unsub = recipient.replace("@", "-unsubscribe@")
            subject, text = THREAD_ACTION.split("--", 1)
            subject = subject.format(**locals()).strip()
            text = text.format(**locals()).strip()
            msg_headers = {}
            msgid = "<ghd-%s-%s@gitbox.apache.org>" % (node_id, str(uuid.uuid4()))
            msgid_OP = "<ghd-%s@gitbox.apache.org>" % node_id
            if action == "created":
                msgid = (
                    msgid_OP  # This is the first email, make a deterministic message id
                )
            else:
                msg_headers = {
                    "In-Reply-To": msgid_OP
                }  # Thread from the actual discussion parent
            asfpy.messaging.mail(
                sender="GitBox <git@apache.org>", recipient=recipient, subject=subject, message=text, messageid=msgid, headers=msg_headers
            )
            return f"[send] {user} {action} {url}: {title}"
    return f"[skip] {user} {action} {url}: {title}"


def parse_comment_action(blob):
    """Parses a comment action (comment created/edited/deleted)"""
    action = blob.get("action")
    discussion = blob.get("discussion")
    comment = blob.get("comment")
    user = comment.get("user").get("login")
    title = discussion.get("title")
    category = discussion.get("category").get("slug")
    url = comment.get("html_url")
    body = comment.get("body")
    repo = blob.get("repository").get("name")
    action_human = "???"
    node_id = discussion.get("node_id")
    if action == "created":
        action_human = "added a comment to the discussion:"
    elif action == "edited":
        action_human = "edited a comment on the discussion:"
    elif action == "deleted":
        action_human = "deleted a comment on the discussion:"
    if action in VALID_COMMENT_ACTIONS:
        recipient = get_recipient(repo)
        if recipient:
            msgid = "<ghd-%s-%s@gitbox.apache.org>" % (node_id, str(uuid.uuid4()))
            msgid_OP = "<ghd-%s@gitbox.apache.org>" % node_id
            unsub = recipient.replace("@", "-unsubscribe@")
            subject, text = COMMENT_ACTION.split("--", 1)
            subject = subject.format(**locals()).strip()
            text = text.format(**locals()).strip()
            msg_headers = {
                    "In-Reply-To": msgid_OP
                }  # Thread from the actual discussion parent
            asfpy.messaging.mail(
                sender="GitBox <git@apache.org>", recipient=recipient, subject=subject, message=text, messageid=msgid, headers=msg_headers
            )
            return f"[send] [comment] {user} {action} {url}: {title}"
    return f"[skip] [comment] {user} {action} {url}: {title}"


def main():

    # Grab all GitHub WebHook IP ranges
    webhook_ips = requests.get("https://api.github.com/meta").json()["hooks"]
    allowed_ips = [netaddr.IPNetwork(ip) for ip in webhook_ips]

    # Init Flask...
    app = flask.Flask(__name__)

    @app.route("/hook", methods=["POST", "PUT"])
    def parse_request():
        this_ip = netaddr.IPAddress(flask.request.headers.get("X-Forwarded-For") or flask.request.remote_addr)
        allowed = any(this_ip in ip for ip in allowed_ips)
        if not allowed:
            return "No content\n"
        content = flask.request.json
        act = content.get("action")
        if "discussion" in content:
            if "comment" in content:
                logmsg = parse_comment_action(content)
            else:
                logmsg = parse_thread_action(content)
            log.log(level=logging.WARNING, msg=logmsg)
        return "Delivered\n"

    # Disable werkzeug request logging to stdout
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    # Start up the app
    app.run(host="127.0.0.1", port=8084, debug=False)


if __name__ == "__main__":
    main()
