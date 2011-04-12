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
    
class StoryTag(db.Model):
    name = db.StringProperty()
    count = db.IntegerProperty()
    
