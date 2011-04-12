import cherrypy
import wsgiref.handlers
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import os
from braveoctopus.data import StoryPage, Story, StoryTag, Account
from google.appengine.ext import db
import string
from os import environ
from braveoctopus import captcha
from google.appengine.api import mail
import re
import BeautifulSoup
from google.appengine.api import users
import urllib, hashlib
import datetime
import base64
import feedparser

## features/bugs
## specify content license
## query strings not fully storred in signin return url

## share a link to a story's front page
## add comments to story's front page
## add tag cloud and ability to undo a tag filter in library
## need to create xml dump of story
## need to implement statistics with previous action stored in base64
## add jquery suggester for tags
## add ability to vote a story up

def validate_email(email):
	if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email) != None:
            return True
	return False

def validate_letters_and_numbers(s):
	if re.match("^[A-Za-z0-9_-]*$", s) != None:
            return True
	return False

template_dirs = []
template_dirs.append(os.path.join(os.path.dirname(__file__), 'templates'))
default_username = "Anonymous"

def render_template(name, **params):
    user_id = None
    user = users.get_current_user()
    if user:
        user_id = user.nickname()
    
    mydict = dict(params)
    mydict.update({'stories':get_top_stories(),'login': get_login_html(),'latest_stories':get_latest_stories(), 'top_tags':get_top_story_tags()})
    return get_template(name).render(**mydict)

def get_template(name):
    env = Environment(loader = FileSystemLoader(template_dirs))
    try:
        return env.get_template(name)
    except TemplateNotFound:
        raise TemplateNotFound(name)


def get_login_html():
    user = users.get_current_user()
    if user:
        name = user.nickname()
        fix_name =""
        account = get_current_account()
        if account != None and account.name != default_username:
            name = account.name
        else:
            fix_name = "<br/><small>You can set your username by going <a href='/account'>here</a></small>"
        
        return ("Welcome, <a href='/account'>%s</a>! (<a href=\"%s\">Logout</a>)%s" %
                    (name, users.create_logout_url("/"),fix_name))
    else:
        return ("<a href='/login?%s'>Sign in or register</a>." % (urllib.urlencode({'return_url':base64.b64encode(cherrypy.url()+"?"+cherrypy.request.query_string)})))
        
def increment_tag_count(tag_name):
    adjust_tag_count(tag_name,1)

def decrement_tag_count(tag_name):
    adjust_tag_count(tag_name,-1)

def adjust_tag_count(tag_name, val):
    q = db.GqlQuery("SELECT * FROM StoryTag WHERE name = :1",tag_name)
    results = q.fetch(1)
    tag = None
    if len(results) > 0:
        tag = results[0]
    else:
        tag = StoryTag()
        tag.name = tag_name
        tag.count = 0
    
    tag.count = tag.count + val
    if tag.count == 0:
        tag.delete()
    else:
        tag.put()

def get_all_stories_with_tag(tag_name):
    q = db.GqlQuery("SELECT * FROM Story WHERE tags= :1 ORDER BY title ASC ", tag_name)
    titles = []
    for p in q.fetch(1000):
            titles.append( (p.title,get_gravatar(get_story_email_or_none(p)),get_story_owner_name_or_default(p)) )
    return titles

def get_all_stories():
    q = db.GqlQuery("SELECT * FROM Story ORDER BY title ASC")
    titles = []
    for p in q.fetch(1000):
            titles.append( (p.title,get_gravatar(get_story_email_or_none(p)),get_story_owner_name_or_default(p)) )
    return titles
        
def get_top_stories():
    q = db.GqlQuery("SELECT * FROM Story ORDER BY votes DESC")
    titles = []
    for p in q.fetch(5):
            titles.append( (p.title,get_gravatar(get_story_email_or_none(p)),get_story_owner_name_or_default(p)) )
    return titles

def get_account_stories(account):
    q = db.GqlQuery("SELECT * FROM Story WHERE account= :1 ORDER BY votes DESC",account.key())
    titles = []
    for p in q.fetch(1000):
            titles.append( (p.title,get_gravatar(account.name),account.name) )
    return titles

def get_top_story_tags():
    q = db.GqlQuery("SELECT * FROM StoryTag ORDER BY count DESC")
    names = []
    for p in q.fetch(5):
            names.append( (str.lower(str(p.name)), str.capitalize(str(p.name))) )
    return names

def get_latest_stories():
    q = db.GqlQuery("SELECT * FROM Story ORDER BY date DESC")
    titles = []
    for p in q.fetch(5):
            titles.append( (p.title,get_gravatar(get_story_email_or_none(p)),get_story_owner_name_or_default(p)) )
    return titles

def get_story_email_or_none(story):
    if not story.account:
        return None    
    return story.account.email
    

def get_story_owner_name_or_default(story):
    if not story.account:
        return default_username
    return story.account.name
    

def get_or_create_account(user):
    q = db.GqlQuery("SELECT * FROM Account WHERE user = :1",user)
    results = q.fetch(1)
    account = None
    if len(results) > 0:
        account = results[0]
    else:
        account = Account()
        account.user = user
        account.name = default_username
        account.put()
    return account

def does_user_name_exist(name):
    q = db.GqlQuery("SELECT * FROM Account WHERE name = :1",name)
    results = q.fetch(1)
    return len(results) > 0

def get_gravatar(email,size=32):
    if not email:
        email = ""
    default = "http://www.braveoctopus.com/images/anonymous__r32x32.jpg"

    gravatar_url = "http://www.gravatar.com/avatar.php?"
    gravatar_url += urllib.urlencode({'gravatar_id':hashlib.md5(email.lower()).hexdigest(), 'default':default, 'size':str(size)})
    return gravatar_url

def redirect(url):
    raise cherrypy.HTTPRedirect(url)
    
def get_current_account():
    user = users.get_current_user()
    if user == None:
        return None
    return get_or_create_account(user)
    
def xstr(s):
    if s is None:
        return ''
    return str(s)
    
def list_to_space_separted_string(l):
    return " ".join(l)

def do_access_check(url="/index"):
    user = users.get_current_user()
    if user == None:
        redirect(url)

def is_story_owned(title):
    story = get_story_or_none(title)
    return story.account != None
    
def do_i_own_story(title):
    account = get_current_account()
    story = get_story_or_none(title)
    if account == None:
        return story.account==None
    else:
        if story.account == None:
            return True
        else:
            return story.account.key() == account.key()
        
def do_access_check_by_title(title):
    if not do_i_own_story(title):
        redirect("/index")

def get_captcha_html(recaptcha_code=None):
    return captcha.displayhtml(
        public_key = "6LeugrwSAAAAAKY4beTHvumY8l77XQKyHuTDeMGD",
        use_ssl = False,
        error = recaptcha_code)

def is_all_whitespace_or_none(s):
    if s == None:
        return True
    return len(string.join(s.split(), ""))==0
    
def get_story_or_none(title):
    q = db.GqlQuery("SELECT * FROM Story WHERE title = :1 ", title )
    results = q.fetch(1)
    story = None
    
    if len(results) > 0: 
        for p in results:
            story = p
    return story
    
def get_page_or_none(story, page):
    q = db.GqlQuery("SELECT * FROM StoryPage WHERE name = :1 AND story = :2 ", page, story.key() )
    results = q.fetch(1)
    story_page = None
    
    if len(results) > 0: 
        for p in results:
            story_page = p
    return story_page

def get_page_by_title_and_page_or_none(title, page):
    story = get_story_or_none(title)
    
    if story == None:
        return None
    
    return get_page_or_none(story,page)

def unique(a):
    """ return the list with duplicate elements removed """
    return list(set(a))

def intersect(a, b):
    """ return the intersection of two lists """
    return list(set(a) & set(b))

def union(a, b):
    """ return the union of two lists """
    return list(set(a) | set(b))

def recalculate_tag_counts(old_tags,new_tags):
    old_tags = unique(old_tags)
    new_tags = unique(new_tags)
    common_tags = intersect(old_tags,new_tags)
    tags_to_decrement = filter(lambda x: x not in common_tags,old_tags)
    tags_to_increment = filter(lambda x: x not in common_tags,new_tags)
    for t in tags_to_decrement:
        decrement_tag_count(t)
    for t in tags_to_increment:
        increment_tag_count(t)
    
def ensure_string_no_longer(str,len):
    if str == None:
        return None
    return str[:len]

class BraveOctopus(object):
        
    @cherrypy.expose
    def index(self):
        return render_template('frontpage.html')
    
    @cherrypy.expose
    def search(self,siteurl=None, q=None):
        return render_template('search.html',query=q)
        
    @cherrypy.expose
    def about(self):
        return render_template('about.html')
        
    @cherrypy.expose
    def blog(self):
        d = feedparser.parse("http://blog.braveoctopus.com/feeds/posts/default")
        return render_template('blog.html', entries=d['entries'][:5])
        
    @cherrypy.expose
    def contact(self,recaptcha_code=None, subject="", email="", email_text="", error_message="" ):
        return render_template('contact.html', captcha = get_captcha_html(recaptcha_code), subject=subject, email=email, email_text=email_text, error_message=error_message)
        
    @cherrypy.expose
    def send_contact(self, submit, email, subject, email_text, recaptcha_challenge_field=None, recaptcha_response_field=None):
        email = ensure_string_no_longer(email,250)
        subject = ensure_string_no_longer(subject,50)
        email_text = ensure_string_no_longer(email_text,500)
        
        remoteip  = environ['REMOTE_ADDR']
        
        cResponse = captcha.submit(
                 recaptcha_challenge_field,
                 recaptcha_response_field,
                 "6LeugrwSAAAAAMyvJJL8DKIyUa0sTn5Ywq5WDFlV",
                 remoteip)
        
        if cResponse.is_valid and validate_email(email) and len(email_text.strip()) > 0:
            #send email
            mail.send_mail(sender="Brave Octopus Member <"+email+">",
              to="richard.anaya@gmail.com",
              subject=subject,
              body=email_text)
            redirect("/index")
        else:
            return self.contact(cResponse.error_code, subject, email, email_text, "Make sure your email is correct.")
      
    @cherrypy.expose
    def login(self,return_url=None):
        return render_template('login.html', return_url=return_url)
        
    @cherrypy.expose
    def do_login(self,return_url="/",openid_username=None,openid_identifier=None):
        if openid_identifier == None:
            redirect("/login")    
        
        real_url = "/"
        if return_url != "/":
            real_url = base64.b64decode(return_url)
        
        redirect(users.create_login_url(dest_url=real_url, federated_identity=openid_identifier))
        
    @cherrypy.expose
    def library(self,tags=None):
        
        stories = []
        if tags:
            stories = get_all_stories_with_tag(tags)
        else:
            stories = get_all_stories()
        
        return render_template('library.html',all_stories=stories)
        
    @cherrypy.expose
    def account(self,error_message=""):
        do_access_check("/login")
        account = get_current_account()
          
        return render_template('account.html',username=account.name, email=xstr(account.email), my_stories=get_account_stories(account), error_message=error_message)
    
    @cherrypy.expose
    def do_save_account(self, username="", email="", submit=None):
        do_access_check("/login")
        
        username = ensure_string_no_longer(username.strip(),35)
        email = ensure_string_no_longer(email.strip(),250)
        account = get_current_account()
        
        if validate_letters_and_numbers(username) == False:
            return self.account("Invalid username: only letters, numbers, _ and - may be used.")
            
        if len(email)>0 and validate_email(email) == False:
            return self.account("Invalid email used.")
            
        if username != default_username and (account.name != username and does_user_name_exist(username)):
            return self.account("Username already exists")
        
        if len(username) == 0:
            return self.account("Username must be non-zero length")
            
        if len(username) > 35:
            return self.account("Username is too long (35 character max)")
        
        account.name = username
        account.email = None if email == "" else email
        account.put()
        
        redirect("/account")
    
    @cherrypy.expose
    def cover(self,title):
        story = get_story_or_none(title)
        user = users.get_current_user()
        if story == None:
            redirect("/index")
        is_owner = do_i_own_story(title)
        return render_template('cover.html',title=title,author=get_story_owner_name_or_default(story),description=story.description,is_owner=is_owner, is_registered= user != None)
    
    @cherrypy.expose
    def story(self,title,page):
        story = get_story_or_none(title)
            
        if story == None:
            redirect("/create_story?title="+title) 
        
        user = users.get_current_user()
        p = get_page_by_title_and_page_or_none(title,page)
        
        is_owner = do_i_own_story(title)
        is_owned = is_story_owned(title)
        
        if p != None:
            
            page_text = p.page_text.replace("\n","<br/>")
            pl = zip(p.page_link_text,p.page_link)
            return render_template('story.html', page_text=page_text, page_links=pl, title=title, current_page = page, is_registered = user != None, page_exists=True, is_owner=is_owner, is_owned=is_owned)
        else:
            return render_template('story.html', title=title, current_page = page, registered = user != None, page_exists=False, is_owner=is_owner, is_owned=is_owned)
    
    @cherrypy.expose
    def create_story(self,submit=None, title="", description="", tags="", recaptcha_code=None, error_message="", own_story="single_owner"):
        account = get_current_account()
        return render_template('create_story.html', title=title, description=description, tags=tags, captcha=get_captcha_html(recaptcha_code), error_message=error_message, real_user=account!=None, own_story=own_story )
    
    @cherrypy.expose
    def do_create_story(self, submit=None, story_title=None, own_story=None, story_tags=None, story_description=None, recaptcha_challenge_field=None, recaptcha_response_field=None):
        story_title = ensure_string_no_longer(story_title,100).strip()
        story_tags = ensure_string_no_longer(story_tags,100)
        story_description = ensure_string_no_longer(story_description,500)
        remoteip  = environ['REMOTE_ADDR']
        
        cResponse = captcha.submit(
                 recaptcha_challenge_field,
                 recaptcha_response_field,
                 "6LeugrwSAAAAAMyvJJL8DKIyUa0sTn5Ywq5WDFlV",
                 remoteip)
        story = get_story_or_none(story_title)
        if cResponse.is_valid and story == None and len(story_title) > 0:
            story = Story()
            story.account = get_current_account() if own_story=="single_owner" else None
            story.title = story_title
            story.date = datetime.datetime.now()
            story.description = story_description
            if story_tags != None:
                tag_list = []
                for s in story_tags.split():
                    if validate_letters_and_numbers(s):
                        increment_tag_count(s)
                        tag_list.append(str.lower(s))
                story.tags = unique(tag_list)
            story.put()
            redirect("/edit_story_page?title="+story_title+"&page=FrontPage")

        else:
            error_message = "Please verify you are a human by completing out the captcha below."
            if story != None:
                error_message = "Cannot create story, because it already exists!"
            if len(story_title) == 0:
                error_message = "You must have a story title"
            return self.create_story(None,story_title,story_description,story_tags,cResponse.error_code, error_message, own_story)
            
            
    @cherrypy.expose
    def do_save_story(self, submit=None, current_title=None ,story_title=None, story_tags=None, story_description=None):
        story_title = ensure_string_no_longer(story_title,100)
        story_tags = ensure_string_no_longer(story_tags,100)
        story_description = ensure_string_no_longer(story_description,500)
        
        do_access_check()
        do_access_check_by_title(current_title)
        
        story = get_story_or_none(current_title)
        
        if  story != None:
            
            old_tags = list(story.tags)
            
            story.title = story_title
            story.date = datetime.datetime.now()
            story.description = story_description
            if story_tags != None:
                tag_list = []
                for s in story_tags.split():
                    if validate_letters_and_numbers(s):
                        tag_list.append(str.lower(s))
                story.tags = unique(tag_list)
            story.put()
            
            new_tags = list(story.tags)
            
            recalculate_tag_counts(old_tags,new_tags)
            
        redirect("/account")
    
    @cherrypy.expose
    def delete_story(self,title,submit=None):
        do_access_check()
        do_access_check_by_title(title)
        
        s = get_story_or_none(title)
        if s != None:
            q = db.GqlQuery("SELECT * FROM StoryPage WHERE story = :1 ", s.key() )
            results = q.fetch(1000)
            for r in results:
                r.delete()
            
            for tag in s.tags:
                decrement_tag_count(tag)
            
            s.delete()
        redirect("/account")
        
    @cherrypy.expose
    def edit_story(self,title,submit=None):
        do_access_check()
        do_access_check_by_title(title)
        
        story = get_story_or_none(title)
            
        if story == None:
            redirect("/create_story?title="+title) 

        if story != None:
            q = db.GqlQuery("SELECT * FROM StoryPage WHERE story = :1 ", story.key() )
            results = q.fetch(1000)
            pages = []
            for r in results:
                pages.append(r.name)
            return render_template('edit_story.html', title=title,pages=pages, description=story.description, tags=list_to_space_separted_string(story.tags))
        else:
            redirect("/index")
        
    @cherrypy.expose
    def edit_story_page(self,title,page,page_text=None,action_links=None,submit=None,recaptcha_code=None):
        do_access_check_by_title(title)
        story = get_story_or_none(title)
            
        if story == None:
            redirect("/create_story?title="+title)        
        
        user = users.get_current_user()
        p = get_page_by_title_and_page_or_none(title,page)
        if p != None: 
            pl = zip(p.page_link_text,p.page_link,range(0,len(p.page_link_text)))
            pl = pl if len(pl)>0 else [("","",0)]
            
            if action_links != None and len(action_links) > 0:
                pl = action_links
            
            pt = p.page_text
            if page_text != None:
                pt = page_text;
            
            return render_template('edit_story_page.html', page_text= pt, page_links=pl, title=title, current_page = page, action_link_count=len(pl), new_page=False, captcha = get_captcha_html(recaptcha_code))
        else:
            return render_template('edit_story_page.html', page_text= "", page_links=[("","",0)], title=title, current_page = page, action_link_count=1, new_page=True,  captcha = get_captcha_html(recaptcha_code))
    
    @cherrypy.expose  
    def save_story_page(self, submit=None, title=None, page=None, page_text=None, action_link_0 = None, action_text_0 = None, action_link_1 = None, action_text_1 = None, action_link_2 = None, action_text_2 = None, action_link_3 = None, action_text_3 = None, action_link_4 = None, action_text_4 = None, recaptcha_challenge_field=None, recaptcha_response_field=None):
        page_text = ensure_string_no_longer(page_text,2000)
        do_access_check_by_title(title)
        
        remoteip  = environ['REMOTE_ADDR']
        
        cResponse = captcha.submit(
                 recaptcha_challenge_field,
                 recaptcha_response_field,
                 "6LeugrwSAAAAAMyvJJL8DKIyUa0sTn5Ywq5WDFlV",
                 remoteip)
        
        action_link_0 = ensure_string_no_longer(None if is_all_whitespace_or_none(action_link_0) else action_link_0.strip(),30)
        action_link_1 = ensure_string_no_longer(None if is_all_whitespace_or_none(action_link_1) else action_link_1.strip(),30)
        action_link_2 = ensure_string_no_longer(None if is_all_whitespace_or_none(action_link_2) else action_link_2.strip(),30)
        action_link_3 = ensure_string_no_longer(None if is_all_whitespace_or_none(action_link_3) else action_link_3.strip(),30)
        action_link_4 = ensure_string_no_longer(None if is_all_whitespace_or_none(action_link_4) else action_link_4.strip(),30)
        
        action_text_0 = ensure_string_no_longer(None if action_link_0 == None else action_text_0.strip(),200)
        action_text_1 = ensure_string_no_longer(None if action_link_1 == None else action_text_1.strip(),200)
        action_text_2 = ensure_string_no_longer(None if action_link_2 == None else action_text_2.strip(),200)
        action_text_3 = ensure_string_no_longer(None if action_link_3 == None else action_text_3.strip(),200)
        action_text_4 = ensure_string_no_longer(None if action_link_4 == None else action_text_4.strip(),200)
        
        clean_page_text = ''.join(BeautifulSoup.BeautifulSoup(page_text).findAll(text=True))
        
        links_text =  filter(None,[action_text_0,action_text_1,action_text_2,action_text_3,action_text_4])
        links = filter(None,[action_link_0,action_link_1,action_link_2,action_link_3,action_link_4])
        
        if cResponse.is_valid:
        
            p = get_page_by_title_and_page_or_none(title,page)
            p  = p if p != None else StoryPage()
            
            story = get_story_or_none(title)
            
            if story == None:
                redirect("/create_story?title="+title)
                
            story.date = datetime.datetime.now()
            story.put()
            
            p.story = story
            p.title = title
            p.name = page
            p.page_text = clean_page_text
            p.page_link_text = links_text
            p.page_link = links
            p.put()
            redirect("/story?title="+title+"&page="+page)
        else:
            pl = zip(links_text,links,range(0,len(links_text)))
            return self.edit_story_page(title,page,clean_page_text,pl,None,cResponse.error_code)


#---------------------------------------------------------------------------
# Start the server under Google AppEngine
#---------------------------------------------------------------------------
app = cherrypy.tree.mount(BraveOctopus(), "/")
wsgiref.handlers.CGIHandler().run(app)