import os
import logging
import time
from datetime import date, datetime

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api.taskqueue import Task

from twilio import twiml
from twilio import TwilioRestException
from twilio.rest import TwilioRestClient

import configuration
import timezone

#
# Valid request formats:
#  xx <message>        - minutes until reminder
#  xxd <message>       - days until reminder
#  x:xx[ap] <message>  - time of current day (am or pm)
#

shortcuts = { 'a':5, 'd':10, 'g':15, 'j':30, 'm':60 }

class RequestLog(db.Model):
  phone = db.StringProperty(indexed=True)
  date  = db.DateTimeProperty(auto_now_add=True)  
  request = db.StringProperty()
## end 

class ReminderTaskHandler(webapp.RequestHandler):
    def post(self):
        phone = self.request.get('phone')
        msg = self.request.get('msg')
        
        try:
            client = TwilioRestClient(configuration.TWILIO_ACCOUNT_SID,
                                      configuration.TWILIO_AUTH_TOKEN)
            logging.debug('sending SMS - %s - to %s' % (msg,phone))
            message = client.sms.messages.create(to=phone,
                                                 from_=configuration.TWILIO_CALLER_ID,
                                                 body=msg)
        except TwilioRestException,te:
            logging.error('Unable to send SMS message! %s' % te)
        
## end


class MainHandler(webapp.RequestHandler):
    def post(self):
      
        # who called? and what did they say?
        phone = self.request.get("From")
        body = self.request.get("Body")
        logging.debug('New request from %s : %s' % (phone, body))
        createLog(phone,body)

        cmd = body.split()
        # assume everything to the left of the first space is the command, and
        # everything to the right of the first space is the reminder message
        command = cmd[0]
        logging.debug('new request command is %s' % command)
        msg = ''
        for m in cmd:
            if m == command:
                continue
            msg += m + ' '

        # parse the command
        
        # a shortcut code request
        if command.isdigit() == False and len(command) == 1:
            # single letters are default minute values
            # a = 5 d = 10 g = 15 j = 30 m = 60
            command = command.lower()
            if command not in shortcuts:
                response = 'illegal shortcut code - a, d, g, j, m are the only valid shortcuts'
            else:
                mins = shortcuts[command]
                createTask(phone, msg, mins * 60)
                response = "got it. we'll remind you in %s minutes" % mins
        
        # a minute request
        elif command.isdigit():
            # create a task in <command> minutes
            createTask(phone, msg, int(command)*60)
            response = "got it. we'll remind you in %s minutes" % command
        
        # an hour request
        elif command.lower().find('h') > 0:
            # create a task in a certain number of days
            hours = command.lower().split('h')[0]
            sec = int(hours) * 60 * 60
            createTask(phone, msg, sec)
            response = "got it. we'll remind you in %s day" % hours

        # a day request
        elif command.lower().find('d') > 0:
            # create a task in a certain number of days
            days = command.lower().split('d')[0]
            sec = int(days) * 24 * 60 * 60
            createTask(phone, msg, sec)
            response = "got it. we'll remind you in %s day" % days

        # a specific time request
        elif command.find(':') > 0:
            # create a task at a specified time
            local = timezone.LocalTimezone()
            tod = datetime.strptime(command, "%H:%M")
            eta = datetime.combine(date.today(), tod.time()).replace(tzinfo=local)
            now = datetime.now(local)
            delta = eta - now
            createTask(phone, msg, delta.seconds)
            response = "got it. we'll remind you at %s" % eta
            
            logging.debug('ETA : %s' % eta)
            logging.debug('... now : %s' % now)
            logging.debug('... delta : %s' % delta.seconds)
    
        else:
            response = '<minutes>, <hours>h, <days>d or hh:mm <reminder-message>'
            
        # ignore positive feedback on new requests
        if response.lower().find('got it') == -1:
            self.response.out.write(smsResponse(response))
        else:
            logging.debug('NOT sending response to caller : %s' % response)

        return
      
## end MainHandler

class IndexHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("You've wondered to a strange place my friend. <a href=http://twitter.com/gregtracy>@gregtracy</a>")

## end IndexHandler

def smsResponse(msg):
    r = twiml.Response()
    r.append(twiml.Sms(msg))
    return r

def createTask(phone,msg,sec):
    logging.debug("Creating new task to fire in %s minutes" % str(int(sec)/60))
    task = Task(url='/reminder', 
                params={'phone':phone,'msg':msg}, 
                countdown=sec)
    task.add('reminders')
# end

def createLog(phone,request):
    log = RequestLog()
    log.phone = phone
    log.request = request
    log.put()


def main():
    logging.getLogger().setLevel(logging.DEBUG)
    application = webapp.WSGIApplication([('/sms', MainHandler),
                                          ('/test', MainHandler),
                                          ('/reminder', ReminderTaskHandler),
                                          ('/.*', IndexHandler)
                                         ],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
