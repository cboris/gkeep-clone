# gkeep-clone
Moving google keep notes between accounts

Move Google Keep transfers your notes from one google account to another. Useful in case of large number of notes.
Small script still in initial but working phase
Script tested on MacOS. Most of functions and ideas borrowed from [Keep It Markdown|https://github.com/djsudduth/keep-it-markdown]
Notes, labels and images are copied. Reminders still need to be implemented


## Installation
As it growth from keep it markdown ideas and code it follows its installation steps from https://github.com/djsudduth/keep-it-markdown including
obtaining oauth token and installing it into your keyring:

1. checkout https://github.com/djsudduth/keep-it-markdown  separately
2. follow instructions for obtaining master token and setting it into your KeyChain
3. checkout this project
4. Set venv and install requirements
5. Edit main replacing SRC_MAIL and DST_MAIL

## Usage
Congrats! You can now run google keep clone. Simply start by running:  
```bash
> python google-keep-clone.py
```

Happy  google keep cloning!

