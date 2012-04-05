import os
import logging

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api.taskqueue import Task

from twilio import twiml
from twilio import TwilioRestException
from twilio.rest import TwilioRestClient
import configuration

#
# Valid request formats:
#  xx <message>        - minutes until reminder
#  xxd <message>       - days until reminder
#  x:xx[ap] <message>  - time of current day (am or pm)
#

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
            logging.error('Unable to send SMS message! %s'%te)
        
## end

        num1 = random.randint(0,10)
        num2 = random.randint(0,10)
        cookie_question = '%s-%s-m' % (num1,num2)
        cookie_counter = 1
        question = '%s x %s' % (str(num1), str(num2))
        self.response.headers.add_header("Set-Cookie", createCookie('question',cookie_question))
        self.response.headers.add_header("Set-Cookie", createCookie('counter',cookie_counter))
        self.response.out.write(question)
        
## end

class MainHandler(webapp.RequestHandler):
    def post(self):
        self.get()
    def get(self):
      
        # who called? and what did they say?
        phone = self.request.get("From")
        body = self.request.get("Body")
        logging.debug('New request from %s : %s', (phone, body))
        createLog(phone,body)

        cmd = body.split()
        # assume everything to the left of the first space is the command, and
        # everything to the right of the first space is the reminder message
        command = cmd[0]
        msg = cmd[1]  # @fixme - concatenate all elements after zero
            
        # take a look at the request and see if it is valid
        # if it is, process the request

        if command.isdigit():
            # create a task in <command> minutes
            logging.debug("Creating new task to fire in %s minutes" % command)
            createTask(phone, msg, int(command))
        
        elif command.find('d') > 0:
            # create a task in a certain number of days
            mins = command.split('d')[0] * 24 * 60
            logging.debug("Creating new task to fire in %s minutes" % mins)
            createTask(phone, msg, mins)
  
        elif command.find(':') > 0:
            # create a task at a specified time
            logging.debug("Creating new task to fire at %s" % command)
            logging.error("FIX ME - no task is generated for this case")
    
        else:
            response = '<minutes>, <days>d or hh:mm <reminder-message>'
            self.response.out.write(smsResponse(response))

        return
      

## end MainHandler

class IndexHandler(webapp.RequestHandler):
    def get(self):
        self.response.out.write("You've wondered to a strange place my friend. <a href=http://twitter.com/gregtracy>@gregtracy</a>")
## end IndexHandler

def createTask(phone,msg,minutes):
    # @fixme configure task to run in a certain number of minutes
    task = Task(url='/reminder', params={'phone':phone,'msg':msg})
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
