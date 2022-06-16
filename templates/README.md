# GHD Notifier - Email Templates
This directory contains the email templates used for notifying projects of 
updates to GitHub Discussions.

The templates consist of an email topic template (first line), 
followed by a double dash, `--`, 
and then finally the email body template.

If you wish to update the email template(s), please do so via a Pull Request.

You may use the following variables in the templates:

- `{action}`: The generic action that happened (created/deleted/edited)
- `{user}`: The GitHub user than initiated the action
- `{title}`: The title of the discussion that was affected
- `{category}`: The category slug for the discussion
- `{url}`: The URL for the discussion or comment that was affected
- `{body}`: The body of text, either the discussion itself or a comment.
- `{action_human}`: If a comment happened, this is a human readable representation of the action
- `{recipient}`: The mailing list this was sent to
- `{unsub}`: The unsubscribe address of the mailing list this was sent to
