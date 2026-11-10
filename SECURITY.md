# Security

Please report a vulnerability privately through GitHub's "Report a vulnerability" button on the
Security tab of this repository, not in a public issue.

Things worth reporting:

- a way for text inside a judged document to make the orchestrator or a judge run a command, write
  a file, or record a lesson;
- a way to make `panel.py verdict` print `SILENCE` without three green replies on the current text;
- a path by which a judge gets write access to the document or to anything outside its staged copy.

The judges are run read-only (`codex -s read-only`, `agy --mode plan`, `claude --tools
Read,Glob,Grep`). The script sends the staged copy of your document to the vendors whose CLIs it
calls; that is its purpose and is described in the README.
