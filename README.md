# GitHub Discussion Notifier Platform for ASF Infrastructure

This service picks up on GitHub Discussions payloads (sent via webhooks) and distributes to pubsub and (if configured) mailing lists at the ASF.
It is designed as a [PipService](https://cwiki.apache.org/confluence/display/INFRA/Pipservices) but can be run manually using pipenv or python3.

All activity is relayed through [PyPubSub](https://github.com/Humbedooh/pypubsub/) at pubsub.apache.org, and to the appropriate mailing lists if such have been set up via .asf.yaml.

To enable notifications for a repository, the `notifications` directive in .asf.yaml should be appended with a `discussions` target, like so:

~~~yaml
notifications:
  commits: commits@foo.apache.org
  discussions: issues@foo.apache.org
  ~~~
  
