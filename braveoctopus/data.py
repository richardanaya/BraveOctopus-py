from google.appengine.ext import db

class Account(db.Model):
    user = db.UserProperty()
    name = db.StringProperty()
    email = db.EmailProperty()

class Story(db.Model):
    account = db.ReferenceProperty(Account)
    title = db.StringProperty()
    description = db.StringProperty()
    date = db.DateTimeProperty()
    votes = db.IntegerProperty()
    tags = db.StringListProperty()

class StoryPage(db.Model):
    story = db.ReferenceProperty(Story)
    name = db.StringProperty()
    page_text = db.TextProperty()
    page_link_text = db.StringListProperty()
    page_link = db.StringListProperty()
    page_link_count = db.StringListProperty()
    page_hit = db.IntegerProperty()

class StoryPageLink(db.Model):
    page = db.ReferenceProperty(StoryPage)
    text = db.TextProperty()
    name = db.StringProperty()
    count = db.IntegerProperty()
    flags = db.StringListProperty()
    
class StoryTagCount(db.Model):
    name = db.StringProperty()
    count = db.IntegerProperty()

class StorySession(db.Model):
    account = db.ReferenceProperty(Account)
    story = db.ReferenceProperty(Story)
    flags = db.StringListProperty()
