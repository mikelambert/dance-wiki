bgaewiki
========

BGAEWiki is a Google Appengine Wiki suitable for mobile devices

BGAEWiki is built on top of [GaeWiki](https://github.com/BauweBijl/gaewiki) where, in addition to the upgrade for current Appengine with Python 2.7, Bootstrap is used as frontend.


Demo
====

[Live DEMO with screenshots](http://vgaewiki.appspot.com)


Install
=======

    git clone https://github.com/vladiuz1/bgaewiki
    cd bgaewiki
    gcloud config set project <your-gae-project>
    gcloud app deploy index.yaml
    gcloud app deploy app.yaml

License
=======

The wiki itself is distributed under GNU GPL v3.

pytz is distributed under the MIT license.