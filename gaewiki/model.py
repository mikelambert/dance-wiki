# -*- coding: utf-8 -*-
# encoding=utf-8

import datetime
import logging
import random
import re
import cgi

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.api.images import get_serving_url
from google.appengine.ext import blobstore

import settings
import util


class WikiUser(db.Model):
    wiki_user = db.UserProperty()
    joined = db.DateTimeProperty(auto_now_add=True)
    wiki_user_picture = db.BlobProperty()
    user_feed = db.StringProperty()
    nickname = db.StringProperty()
    public_email = db.StringProperty()

    def get_nickname(self):
        if self.nickname:
            return self.nickname
        return self.wiki_user.email().split('@', 1)[0]

    def get_public_email(self):
        return self.public_email or self.wiki_user.email()

    def put(self):
        if self.nickname:
            other = self.gql('WHERE nickname = :1', self.nickname).get()
            if other is not None and other.key() != self.key():
                raise RuntimeError('This nickname is already taken, please choose a different one.')
        return super(WikiUser, self).put()

    @classmethod
    def get_all(cls):
        return cls.all().order('wiki_user').fetch(1000)

    @classmethod
    def get_or_create(cls, user):
        if user is None:
            return None
        wiki_user = cls.gql('WHERE wiki_user = :1', user).get()
        if wiki_user is None:
            wiki_user = cls(wiki_user=user)
            wiki_user.nickname = cls.get_unique_nickname(wiki_user)
            wiki_user.put()
        return wiki_user

    @classmethod
    def get_unique_nickname(cls, user):
        nickname = user.get_nickname()
        while cls.gql('WHERE nickname = :1', nickname).get() is not None:
            nickname = user.get_nickname() + str(random.randrange(1111, 9999))
        return nickname


class WikiUserReference(db.ReferenceProperty):
    """For some reason db.ReferenceProperty itself fails to validate
    references, thinking that model.WikiUser != __main__.model.WikiUser,
    whatever that means.  Disabled until a solution is found.
    """
    def __init__(self):
        db.ReferenceProperty.__init__(self, WikiUser)

    def validate(self, value):
        return value

class WikiUpload(db.Model):
    user = WikiUserReference()
    created = db.DateTimeProperty(auto_now_add=True)
    short_key = db.StringProperty(required=True)
    blob_key = db.StringProperty(required=True)
    content_type = db.StringProperty(required=False)
    filename = db.StringProperty(required=False)
    size = db.IntegerProperty(required=False)
    is_latest = db.BooleanProperty(default=True)

    # the rest of info in blob_storage
    def __init__(self, *args, **kwargs):
        super(WikiUpload, self).__init__(*args, **kwargs)
        self._blob = None

    @property
    def blob(self):
        if self._blob is not None:
            return self._blob
        else:
            if self.__dict__.has_key('blob_key') and self.blob_key is not None:
                self._blob = blobstore.BlobInfo(blobstore.BlobKey(self.blob_key))
                return self._blob
            else:
                return None

    @property
    def size_fmt(self):
        return util.sizeof_fmt(self.size)

    @property
    def is_image(self):
        return self.content_type[:5] == "image"

    @property
    def is_audio(self):
        return self.content_type[:5] == "audio"

    @property
    def is_video(self):
        return self.content_type[:5] == "video"

    @property
    def thumb_url(self):
        if self.is_image:
            url = get_serving_url(self.blob_key, 25, True)
            #return url
            if url.startswith('http://'):
                url = url[5:]
            return url
        else:
            return "//google.com/"

    @classmethod
    def get_recently_added(cls, limit=100):
        return cls.all().order('-created').fetch(limit)

    @classmethod
    def get_by_key(cls, key):
        return cls.gql("WHERE short_key = :1", key).get()

    @classmethod
    def get_by_name(cls, name):
        return cls.gql("WHERE is_latest = TRUE AND filename = :1", name).get()

    @classmethod
    def find_all(cls, limit=100):
        all = blobstore.BlobInfo.all().fetch(limit)
        return [cls(i) for i in all]


    def get_url(self, size=None, crop=False):
        """Returns a URL for accessing the image/file with specified parameters.
        Size limits width and height, crop=True makes it square."""
        url = get_serving_url(self.blob_key, size, crop)
        if url.startswith('http://'):
            url = url[5:]
        return url

    def get_code(self, size=None, crop=False):
        """Returns the wiki code to embed this file."""
        if self.is_image:
            code = "Image:" + self.filename
            if size is not None:
                code += ";size=" + str(size)
            if crop:
                code += ";crop"
        elif self.is_audio:
            code = "Audio:" + self.filename
        elif self.is_video:
            code = "Video:" + self.filename
        else:
            code = "File:" + self.filename
        return "[[" + code + "]]"

    def get_html(self, tag = "File", title = "", size = None, crop = False, align = "left"):
        attrs = "src='%s' alt='%s'" % (self.get_url(size, crop),
                                       cgi.escape(self.filename))
        if align is not None:
            attrs += " align='%s'" % align

        return '<a href="/w/file/view/%s" title="%s" ><img class="img-responsive" %s/></a>' % (cgi.escape(self.short_key, True), title, attrs)


class WikiContent(db.Model):
    """Stores current versions of pages."""
    GEOLABEL = 'gaewiki:geopt'

    title = db.StringProperty(required=True)
    body = db.TextProperty(required=False)
    author = WikiUserReference()
    updated = db.DateTimeProperty(auto_now_add=True)
    created = db.DateTimeProperty(auto_now_add=True)
    pread = db.BooleanProperty()
    # Place on the map.
    geopt = db.GeoPtProperty()
    # The name of the page that this one redirects to.
    redirect = db.StringProperty()
    # Labels used by this page.
    labels = db.StringListProperty()
    # Pages that this one links to.
    links = db.StringListProperty()

    def __init__(self, *args, **kwargs):
        super(WikiContent, self).__init__(*args, **kwargs)
        self._parsed_page = None

    def get_property(self, key, default=None):
        """Returns the value of a property."""
        if self._parsed_page is None:
            self._parsed_page = self.parse_body(self.body or '')
        return self._parsed_page.get(key, default)

    def set_property(self, key, value):
        """Changes the value of a property."""
        if self._parsed_page is None:
            self._parsed_page = self.parse_body(self.body or '')
        self._parsed_page[key] = value
        self.body = self.format_body(self._parsed_page)

        user = users.get_current_user()
        if user:
            logging.debug('%s changed property %s of page "%s" to: %s' % (user.email(), key, self.title, value))
        else:
            logging.debug('somebody changed property %s of page "%s" to: %s' % (key, self.title, value))

    def get_actual_body(self):
        """Returns the page body with updated properties "date" and "author"."""
        body = self.parse_body(self.body or '')
        body['date'] = self.created.strftime('%Y-%m-%d %H:%M:%S')
        body['name'] = self.title
        return self.format_body(body)

    @property
    def comments_enabled(self):
        """Returns True if the page has a comments:yes property and the
        comments_code global settings is not empty."""
        if self.get_property('comments') == ['yes']:
            return True

    @property
    def summary(self):
        """Returns the formatted body unless there's an explicit "summary"
        property."""
        data = self.get_property('summary')
        if not data:
            data = util.wikify_filter(self.body, display_title='')
        return data

    def get_display_title(self):
        return self.get_property('display_title', self.title)

    def get_file(self):
        return self.get_property('file')

    def get_file_type(self):
        filetype = self.get_property('file_type')
        if filetype is None:
            url = self.get_file() or ''
            if url.endswith('.mp3'):
                return 'audio/mpeg'
            if url.endswith('.ogg'):
                return 'audio/vorbis'
        return filetype or 'application/octet-stream'

    def get_file_length(self):
        return self.get_property('file_length')

    def put(self):
        """Adds the gaewiki:parent: labels transparently."""
        if self.body is not None:
            options = util.parse_page(self.body)
            self.redirect = options.get('redirect')
            self.pread = options.get('public') == 'yes' and options.get('private') != 'yes'
            self.labels = options.get('labels', [])
            if 'date' in options:
                try:
                    self.created = datetime.datetime.strptime(options['date'], '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass
            if 'name' in options and options['name'] != self.title:
                if self.get_by_title(options['name'], create_if_none=False) is not None:
                    raise ValueError('A page named "%s" already exists.' % options['name'])
                self.title = options['name']
            self.__update_geopt()

        self.links = util.extract_links(self.body)
        self.add_implicit_labels()
        db.Model.put(self)
        settings.check_and_flush(self)

    def __update_geopt(self):
        """Updates the geopt property from the appropriate page property.
        Maintains the gaewiki:geopt label."""
        if self.GEOLABEL in self.labels:
            self.labels.remove(self.GEOLABEL)

        tmp = self.get_property('geo')
        if tmp is not None:
            parts = tmp.split(',', 1)
            self.geopt = db.GeoPt(float(parts[0]), float(parts[1]))
            self.labels.append(self.GEOLABEL)
            logging.debug(u'Put %s on the map: %s' % (self.title, self.geopt))

    def add_implicit_labels(self):
        labels = [l for l in self.labels if not l.startswith('gaewiki:parent:')]
        if '/' in self.title:
            parts = self.title.split('/')[:-1]
            while parts:
                label = 'gaewiki:parent:' + '/'.join(parts)
                labels.append(label)
                parts.pop()
                break  # remove to add recursion
        self.labels = labels

    def backup(self):
        """Archives the current page revision."""
        logging.debug(u'Backing up page "%s"' % self.title)
        archive = WikiRevision(title=self.title, revision_body=self.body, author=self.author, created=self.updated)
        archive.put()

    def update(self, body, author, delete):
        if self.is_saved():
            self.backup()
            if delete:
                logging.debug(u'Deleting page "%s"' % self.title)
                self.delete()
                return

        logging.debug(u'Updating page "%s"' % self.title)

        self.body = body
        self.author = WikiUser.get_or_create(author)
        self.updated = datetime.datetime.now()

        # TODO: cross-link

        self.put()

    def get_history(self):
        return WikiRevision.gql('WHERE title = :1 ORDER BY created DESC', self.title).fetch(100)

    def get_backlinks(self):
        return self.find_backlinks_for(self.title)

    @classmethod
    def find_backlinks_for(cls, title, limit=1000):
        return WikiContent.gql('WHERE links = :1', title).fetch(limit)

    def load_template(self, user, is_admin):
        template = '# PAGE_TITLE\n\n**PAGE_TITLE** is ...'
        template_names = ['gaewiki:anon page template']
        if user is not None:
            template_names.insert(0, 'gaewiki:user page template')
        if users.is_current_user_admin():
            template_names.insert(0, 'gaewiki:admin page template')
        for template_name in template_names:
            page = WikiContent.gql('WHERE title = :1', template_name).get()
            if page is not None:
                logging.debug('Loaded template from %s' % template_name)
                template = page.body.replace(template_name, 'PAGE_TITLE')
                break
        if user is not None:
            template = template.replace('USER_EMAIL', user.email())
        self.body = template.replace('PAGE_TITLE', self.title)

    def is_locked(self):
        """Returns True if the page has the locked:yes property."""
        return self.get_property('locked') == 'yes'

    def get_redirected(self):
        """Returns the page that this one redirects to (if at all)."""
        if self.redirect:
            page = self.get_by_title(self.redirect)
            if page.is_saved():
                return page
        return self

    @classmethod
    def get_by_title(cls, title, default_body=None, create_if_none=True):
        """Finds and loads the page by its title, creates a new one if nothing
        could be found."""
        title = title.replace('_', ' ')
        page = cls.gql('WHERE title = :1', title).get()
        if page is None and create_if_none:
            page = cls(title=title)
            if default_body is not None:
                page.body = default_body
        return page

    @classmethod
    def get_by_label(cls, label):
        """Returns a list of pages that have the specified label."""
        return cls.gql('WHERE labels = :1', label).fetch(100)

    @classmethod
    def get_publicly_readable(cls):
        if settings.get('open-reading') == 'yes':
            pages = cls.all()
        else:
            pages = cls.gql('WHERE pread = :1', True).fetch(1000)
        return sorted(pages, key=lambda p: p.title.lower())

    @classmethod
    def get_all(cls):
        return sorted(cls.all().order('title').fetch(1000), key=lambda p: p.title.lower() if ':' in p.title else ':' + p.title.lower())

    @classmethod
    def get_recently_added(cls, limit=100):
        return cls.all().order('-created').fetch(limit)

    @classmethod
    def get_recent_by_label(cls, label, limit=100):
        return cls.gql('WHERE labels = :1 ORDER BY created DESC', label).fetch(limit)

    @classmethod
    def get_changes(cls):
        if settings.get('open-reading') in ('yes', 'login'):
            pages = cls.all().order('-updated').fetch(20)
        else:
            pages = cls.gql('WHERE pread = :1 ORDER BY updated DESC', True).fetch(20)
        return pages

    @classmethod
    def get_error_page(cls, error_code, default_body=None):
        return cls.get_by_title('gaewiki:error-%u' % error_code, default_body)

    @staticmethod
    def parse_body(page_content):
        options = {}
        parts = re.split('[\r\n]+---[\r\n]+', page_content, 1)
        if len(parts) == 2:
            for line in re.split('[\r\n]+', parts[0]):
                if not line.startswith('#'):
                    kv = line.split(':', 1)
                    if len(kv) == 2:
                        k = kv[0].strip()
                        v = kv[1].strip()
                        if k.endswith('s'):
                            v = re.split(',\s*', v)
                        options[k] = v
        options['text'] = parts[-1]
        return options

    @staticmethod
    def format_body(parsed):
        """Returns the text representation of a parsed body dictionary."""
        def format_property(value):
            if type(value) == list:
                value = u', '.join(sorted(value))
            return value
        head = u'\n'.join(sorted([u'%s: %s' % (k, format_property(v)) for k, v in parsed.items() if k != 'text']))
        text = parsed['text']
        if head:
            text = head + u'\n---\n' + text
        return text

    @classmethod
    def find_geotagged(cls, label=None, limit=100):
        """Returns geotagged pages."""
        if label is None:
            label = cls.GEOLABEL
        label = label.replace('_', ' ')
        pages = cls.gql('WHERE labels = :1 ORDER BY created DESC', label).fetch(limit)
        pages = [p for p in pages if cls.GEOLABEL in p.labels]
        return pages


class WikiRevision(db.Model):
    """
    Stores older revisions of pages.
    """
    title = db.StringProperty()
    wiki_page = db.ReferenceProperty(WikiContent)
    revision_body = db.TextProperty(required=True)
    author = db.ReferenceProperty(WikiUser)
    created = db.DateTimeProperty(auto_now_add=True)
    pread = db.BooleanProperty()

    @classmethod
    def get_by_key(cls, key):
        return db.Model.get(db.Key(key))


