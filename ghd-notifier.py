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
import yaml.parser
import os
import uuid

"""GitHub Discussions Notifier"""

REPO_ROOT = "/x1/repos/asf"
GHSETTINGS_ROOT = "/x1/asfyaml"
VALID_THREAD_ACTIONS = ["created", "edited", "closed", "reopened"]
VALID_COMMENT_ACTIONS = ["created", "edited", "deleted"]
THREAD_ACTION = open("templates/thread-action.txt").read()
COMMENT_ACTION = open("templates/comment-action.txt").read()


def get_custom_subject(repository, action="catchall"):
    """Gets a subject template for a specific action, if specified via .asf.yaml"""
    gh_settings_path = os.path.join(GHSETTINGS_ROOT, f"ghsettings.{repository}.yml")  # Path to github settings yaml file
    if os.path.isfile(gh_settings_path):
        try:
            yml = yaml.safe_load(open(gh_settings_path))
        except yaml.parser.ParserError:  # Invalid YAML?!
            return
        custom_subjects = yml.get("custom_subjects")
        if custom_subjects and isinstance(custom_subjects, dict):
            if action in custom_subjects:
                return custom_subjects[action]
            elif "catchall_discussions" in custom_subjects:  # If no custom subject exists for this action, but catchall does...
                return custom_subjects["catchall_discussions"]


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
    repository = blob.get("repository").get("name")
    node_id = discussion.get("node_id")
    if action in VALID_THREAD_ACTIONS:
        recipient = get_recipient(repository)
        if recipient:
            # The templates contain templates for the subject (first part)
            # and the content of the email (second part) ... split the template
            # up.
            subject, text = THREAD_ACTION.split("--", 1)

            # Define the name of the template for this action.
            action_name = "new_discussion"
            if action == "created":
                action_name = "new_discussion"
            elif action == "edited":
                action_name = "edit_discussion"
            elif action == "closed":
                action_name = "close_discussion"
            elif action == "reopened":
                action_name = "reopen_discussion"
            # Note: the subjects are checked for validity in
            # https://github.com/apache/infrastructure-p6/blob/production/modules/gitbox/files/asfgit/package/asfyaml.py
            # See VALID_GITHUB_SUBJECT_VARIABLES and validate_github_subject()
            # The variable names listed in VALID_GITHUB_SUBJECT_VARIABLES must be defined
            # here as local variables
            custom_subject_line = get_custom_subject(repository, action_name)  # Custom subject line?
            try:
                # If a custom subject line was defined, use that ...
                if custom_subject_line:
                    subject = custom_subject_line.format(**locals())
                # Otherwise use the default one, which is located in the title of the template.
                else:
                    subject = subject.format(**locals()).strip()
                    # Small "hack" to add a prefix of "Re: " to everything that's not creating a new discussion.
                    if action_name != "new_discussion"
                        subject = "Re: " + subject
            except (KeyError, ValueError) as e:  # Template breakage can happen, ignore
                print(e)
                return

            unsub = recipient.replace("@", "-unsubscribe@")
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
                sender=f"\"{user} (via GitHub)\" <git@apache.org>", recipient=recipient, subject=subject, message=text, messageid=msgid, headers=msg_headers
            )
            return f"[send] {user} {action} {url}: {title}"
    return f"[skip] {user} {action} {url}: {title}"


# The general difference between this and the general parse_thread_action
# is that in this case we're getting the content in the email as well as the
# user information from the "comment" element instead of the "discussion"
# element.
def parse_comment_action(blob):
    """Parses a comment action (comment created/edited/deleted)"""
    action = blob.get("action")
    discussion = blob.get("discussion")
    discussion_state = discussion.get("state")
    comment = blob.get("comment")
    user = comment.get("user").get("login")
    title = discussion.get("title")
    category = discussion.get("category").get("slug")
    url = comment.get("html_url")
    body = comment.get("body")
    repository = blob.get("repository").get("name")
    action_human = "???"
    node_id = discussion.get("node_id")
    # If the user closes a discussion with a comment, there is
    # currently no way to distinguish this from a user commenting
    # on a closed issue (if this is even possible). We're assuming
    # that this doesn't happen and if the discussion state is
    # "closed" that the user closed with a comment.
    if action == "created" and discussion_state == "closed":
        action_human = "closed the discussion with a comment:"
        action_name = "close_discussion_with_comment"
    elif action == "created":
        action_human = "added a comment to the discussion:"
        action_name = "new_comment_discussion"
    elif action == "edited":
        action_human = "edited a comment on the discussion:"
        action_name = "edit_comment_discussion"
    elif action == "deleted":
        action_human = "deleted a comment on the discussion:"
        action_name = "delete_comment_discussion"
    if action in VALID_COMMENT_ACTIONS:
        recipient = get_recipient(repository)
        if recipient:
            # The templates contain templates for the subject (first part)
            # and the content of the email (second part) ... split the template
            # up.
            subject, text = COMMENT_ACTION.split("--", 1)

            # Note: the subjects are checked for validity in
            # https://github.com/apache/infrastructure-p6/blob/production/modules/gitbox/files/asfgit/package/asfyaml.py
            # See VALID_GITHUB_SUBJECT_VARIABLES and validate_github_subject()
            # The variable names listed in VALID_GITHUB_SUBJECT_VARIABLES must be defined
            # here as local variables
            custom_subject_line = get_custom_subject(repository, action_name)  # Custom subject line?
            try:
                # If a custom subject line was defined, use that ...
                if custom_subject_line:
                    subject = custom_subject_line.format(**locals())
                # Otherwise use the default one, which is located in the title of the template.
                else:
                    subject = subject.format(**locals()).strip()
            except (KeyError, ValueError) as e:  # Template breakage can happen, ignore
                print(e)
                return

            msgid = "<ghd-%s-%s@gitbox.apache.org>" % (node_id, str(uuid.uuid4()))
            msgid_OP = "<ghd-%s@gitbox.apache.org>" % node_id
            unsub = recipient.replace("@", "-unsubscribe@")
            text = text.format(**locals()).strip()
            msg_headers = {
                    "In-Reply-To": msgid_OP
                }  # Thread from the actual discussion parent
            asfpy.messaging.mail(
                sender=f"\"{user} (via GitHub)\" <git@apache.org>", recipient=recipient, subject=subject, message=text, messageid=msgid, headers=msg_headers
            )
            return f"[send] [comment] {user} {action} {url}: {title}"
    return f"[skip] [comment] {user} {action} {url}: {title}"


def main():

    # Grab all GitHub WebHook IP ranges and save them, so we can check if an
    # incoming request is originating from one of these IP addresses.
    webhook_ips = requests.get("https://api.github.com/meta").json()["hooks"]
    allowed_ips = [netaddr.IPNetwork(ip) for ip in webhook_ips]

    # Init Flask...
    app = flask.Flask(__name__)

    # This will make Flask react to requests aimed at /hook, which the GitHub
    # webhook service will be calling.
    @app.route("/hook", methods=["POST", "PUT"])
    def parse_request():
        # Get the IP address, the request is originating from.
        # (I assume the "X-Forwarded-For" is used when using tools like ngrok
        # to forward requests to protected locations, "flask.request.remote_addr"
        # contains the ip in the direct access case)
        this_ip = netaddr.IPAddress(flask.request.headers.get("X-Forwarded-For") or flask.request.remote_addr)

        # Check if this incoming request is originating from one of the
        # GitHub webhook IP addresses. Deny the request, if it's not.
        allowed = any(this_ip in ip for ip in allowed_ips)
        if not allowed:
            return "No content\n"

        # Process the incoming message.
        content = flask.request.json
        # GitHub Discussion notifications are all expected to have a "discussion" element.
        if "discussion" in content:
            # If this is a comment action, it will also contain a "comment" element
            if "comment" in content:
                logmsg = parse_comment_action(content)
            # Otherwise it's a basic "create", "edit", "close" operation.
            else:
                logmsg = parse_thread_action(content)
            log.log(level=logging.WARNING, msg=logmsg)
        return "Delivered\n"

    # Disable werkzeug request logging to stdout
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.WARNING)

    # Start up the app (Starts the Flask webserver)
    app.run(host="127.0.0.1", port=8084, debug=False)


if __name__ == "__main__":
    main()
