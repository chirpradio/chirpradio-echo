Ambient echo of all `CHIRP Radio`_ music data, as it happens.

This is an experiment to see how many audio fingerprints we can seed into the
open `Echo Nest API`_. The echo daemon collects 40 second chunks from the
`CHIRP Radio`_ live stream, makes a fingerprint, then asks the `CHIRP Radio API`_ what song
is playing. It posts the artist, track name, album, and fingerprint to Echo Nest.

CHIRP broadcasts 7 days a week, 18 hours a day; it's all live and we focus on a
lot new releases. If the fingerprint seeding is useful we could try running it
through the history of all CHIRP Radio which is about 19,710 hours of music so
far (since 2010), all archived and each song identified.

.. _`Echo Nest API` : http://developer.echonest.com/index.html
.. _`CHIRP Radio`: http://chirpradio.org/
.. _`CHIRP Radio API`: http://code.google.com/p/chirpradio/wiki/TheChirpApi

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

    ECHO_NEST_API_KEY=... ch-echo

Get In Touch
------------

http://groups.google.com/group/chirpdev/
