# GitHub Discussion Notifier Platform for ASF Infrastructure

This service picks up on GitHub Discussions payloads (sent via webhooks) and distributes to pubsub and (if configured) mailing lists at the ASF.
It is designed as a [PipService](https://cwiki.apache.org/confluence/display/INFRA/Pipservices) but can be run manually using pipenv or python3.

All activity is relayed through [PyPubSub](https://github.com/Humbedooh/pypubsub/) at pubsub.apache.org, and to the appropriate mailing lists if such have been set up via .asf.yaml.

To enable notifications for a repository, the `notifications` directive in .asf.yaml should be appended with a `discussions` target, like so:

~~~yaml
notifications:
  commits: commits@foo.apache.org
  discussions: issues@foo.apache.org

custom_subjects:
    new_discussion: "Created: Discussion {repository}: {title}"
    edit_discussion: "Edited: Discussion {repository}: {title}"
    close_discussion: "Closed: Discussion {repository}: {title}"
    close_discussion_with_comment: "Closed: Discussion with comment {repository}: {title}"
    reopen_discussion: "Reopened: Discussion {repository}: {title}"
    new_comment_discussion: "Commented: Discussion {repository}: {title}"
    edit_comment_discussion: "Edited a comment: Discussion {repository}: {title}"
    delete_comment_discussion: "Deleted a comment: Discussion {repository}: {title}"
  ~~~

## Possible Actions

The different actions I identified and how to detect them:

- Discussion Created:
  - Action: "created"
  - No "comment" element
- Discussion Edited:
  - Action: "edited"
  - No "comment" element
- Discussion Closed without comment:
  - Action: "closed"
  - No "comment" element
- Discussion Closed with comment:
  - Action: "created"
  - Existing "comment" element
  - Discussion/State: "closed"
- Comment Added:
  - Action: "created"
  - Existing "comment" element
  - Discussion/State: "open"
- Comment Edited:
  - Action: "edited"
  - Existing "comment" element
  - Discussion/State: "open"
- Comment Deleted:
  - Action: "deleted"
  - Existing "comment" element
  - Discussion/State: "open"

NOTE: Problem is, that it seems impossible to distinguish between someone adding a comment to a closed discussion and someone closing a discussion with a comment.
For simplicity reasons, we'll assume that if a comment is added and the discussion state is "closed", that this is someone closing a discussion with a comment.
  
