Behold! This is a scrubber for CHIRP Radio's audio stream.
It uses EchoNest to fingerprint the audio and figure out what's playing.
If it doesn't get a match then it tells EchoNest what the DJ is currently
playing.

Install some libs::

    sudo apt-get update
    sudo apt-get install ffmpeg libboost1.50-dev libtag1-dev zlib1g-dev

Grab this source: https://github.com/echonest/echoprint-codegen
and install it::

    cd echoprint-codegen/src
    make
    sudo make install

This gets you the ``echoprint-codegen`` binary.

Install the Python stuff::

    pip install -r requirements.txt
    python setup.py develop

Run it::

    ch-echo
