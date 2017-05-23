''' Refer to class HaguEigoBot '''
import os
import re
from shutil import copyfile
from time import sleep
from threading import Thread
import datetime
import json
import csv
from enum import Enum
from flags import Flags
import credentials
import tweepy
from tweepy.api import API

class FunctionFlags(Flags):
    """ Base class for BotFunctions """
    __pickle_int_flags__ = True
    __no_flags_name__ = 'TestOffline'
    __all_flags_name__ = 'Full'

class BotFunctions(FunctionFlags):
    """ Determines the functionality of a bot while running """
    LogStream = 1
    TweetTimed = 2
    Interact = 4 #Unimplemented

#Event JSON: [{time, code, text}]
class BotEvents(Enum):
    """ Event codes for saving to output JSON """
    SYS_Setup = 1
    SYS_Stop = 2
    USR_Tweet = 3
    USR_GetReply = 4
    USR_GiveReply = 5
    USR_GetDM = 6
    USR_GiveDM = 7
    ERR_KeyboardInterrupt = 8
    ERR_Communications = 9

''' Log Format

int last_index
list events []
    string "type": "BotEvents.SYS_Start",
    string "text": "BotFunctions()",
    string "time": "2017-05-19 21:26:45.656315"

'''

class HaguEigoBot(tweepy.StreamListener):
    '''
    While running, refreshes a JSON feed and settings file periodically
    so as to deliver content to Twitter. Also, responds to Twitter inputs.
    Requires: credentials.py, config.json, feed.json
    Will create output.json if it doesn't exist already, to track place in feed and current version
    '''
    FEED = "feed.json"
    CONFIG = "config.json"
    OUTPUT = "output.csv"

    def __init__(self, functionality=BotFunctions(), api=None):
        """
        Create an instance of a HaguEigoBot,
        acquire authorization from Twitter (or run offline)
        """
        self.running = False
        self._tweet_thread = None
        self.api = api or API()
        tweepy.StreamListener.__init__(self.api) #self.api becomes active
        self.functionality = functionality
        self.tweet_times = []
        self.event_log = []
        self.feed_index = 0
        self.feed_length = 0
        self.min_tweet_delay = 10
        self.load_config() # Get tweeting times and current feed_index
        if functionality < BotFunctions.LogStream or functionality == BotFunctions.TweetTimed:
            # Testing offline or online
            self.min_tweet_delay = 0.5
            self.running = True
            self._start_tweeting()

    def load_config(self):
        """
        Loads config settings and attempts to
        resume the last session using output.json.
        """
        with open(HaguEigoBot.CONFIG) as config_json:
            config = json.load(config_json)
            print(config)
            for time_str in config['tweet_times']:
                self.tweet_times.append(
                    [int(x) for x in re.search(r'0?([12]?\d):0?([1-5]?\d)', time_str).groups()]
                )

        if os.path.exists(HaguEigoBot.OUTPUT):
            #Load last feed_index
            with open(HaguEigoBot.OUTPUT) as logfile:
                top = logfile.readline()
                self.feed_index = int(top) if len(top) > 0 else 0

        log_str = "Offline testing"
        if self.functionality >= BotFunctions.LogStream:
            log_str = str(self.functionality)
        self.log_event(BotEvents.SYS_Setup, log_str, False)

    def on_connect(self):
        """Called once connected to streaming server.

        This will be invoked once a successful response
        is received from the server. Allows the listener
        to perform some work prior to entering the read loop.
        """
        print("Connection established.")
        if BotFunctions.TweetTimed in self.functionality:
            self._start_tweeting()

    def on_direct_message(self, status):
        """Called when a new direct message arrives"""
        try:
            if status.direct_message['sender_screen_name'] != self.api.me.screen_name:
                self.log_event(BotEvents.USR_GetDM, str(status.direct_message))
            return True
        except BaseException as my_event:
            self.log_event(BotEvents.ERR_Communications, str(my_event), False)

    def load_next_tweets(self):
        """ Loads feed data necessary for the next tweet batch. """
        print("Current feed index = " + str(self.feed_index))
        next_tweets = []
        with open(HaguEigoBot.FEED, encoding="utf8") as feed_json:
            feed_data = json.load(feed_json)
            self.feed_length = len(feed_data)
            if self.feed_index >= len(feed_data):
                return None
            print("Feed index: " + str(self.feed_index))
            next_tweets.append(feed_data[self.feed_index])
            while feed_data[self.feed_index]['chain'] and self.feed_index < len(feed_data):
                self.feed_index += 1
                next_tweets.append(feed_data[self.feed_index])

            self.feed_index += 1 # Final increment
        return next_tweets

    def get_next_tweet_datetime(self):
        """ Gets the next datetime at which tweeting will occur. """
        if len(self.tweet_times) > 0:
            now_t = datetime.datetime.now()
            next_t = now_t
            if not self.functionality:
                #Don't use config's times if simulating
                return datetime.datetime.now() + datetime.timedelta(seconds=self.min_tweet_delay*4)

            if (
                    self.tweet_times[-1][0] < now_t.hour or
                    (
                        self.tweet_times[-1][0] == now_t.hour and
                        self.tweet_times[-1][1] < now_t.minute
                    )
                ): #Add a day if it's too late
                next_t = next_t + datetime.timedelta(days=1)
            elif (
                    self.tweet_times[-1][0] == now_t.hour and
                    self.tweet_times[-1][1] == now_t.minute
                ):
                # DO IT NOW!!
                return datetime.datetime.now()

            for time in self.tweet_times:
                # Pick apart time tuple, put in next_t
                next_t = next_t.replace(hour=time[0], minute=time[1])
                if now_t < next_t: # If next_t is in the future
                    return next_t.replace(second=0)

        #No viable times were found
        return None

    def log_event(self, ev_type, text="", save=True):
        """ Add an event to the event log before potentially saving. """
        event = dict()
        event['time'] = datetime.datetime.now().strftime("%m/%d/%y %H:%M:%S")
        event['type'] = str(ev_type)
        event['text'] = text
        self.event_log.append(event)
        if save:
            self._save_event_log()

    def _save_event_log(self):
        """
        Writes to output.json to save progress and action log.
        Usually performed after adding an event.
        """
        # Overwrite header data (not CSV header)
        print("writing")
        touch = open(HaguEigoBot.OUTPUT, 'a')
        touch.close()
        with open(HaguEigoBot.OUTPUT, 'r+', newline='\n') as outfile:
            outfile.write(str(self.feed_index) + '\n')
            outfile.seek(0, os.SEEK_END) #Jump to the end to append
            print(outfile.readline())
            csv_writer = csv.DictWriter(outfile, ['time', 'type', 'text'])
            csv_writer.writerows(self.event_log)
            self.event_log = []

    def _start_tweeting(self):
        """ Begin normal functionality loop. """

        self._tweet_thread = Thread(target=self._tweet_loop)
        self._tweet_thread.start()


    def _tweet_loop(self):
        """ Loop for tweeting, while the stream is open. """
        while self.running:
            # Get next tweet ready
            next_index = self.feed_index + 1
            next_tweets = self.load_next_tweets()

            if not next_tweets:
                self.log_event(BotEvents.SYS_Stop, "Ran out of tweets.")
                raise EOFError("Arrived at the end of feed.json")

            # Sleep until time in config
            delta = self.get_next_tweet_datetime() - datetime.datetime.now()
            sleep(delta.total_seconds())
            self.log_event(
                BotEvents.USR_Tweet,
                str("{} tweet{} starting at {} ({})".format(
                    len(next_tweets),
                    's' if (len(next_tweets) > 1) else '',
                    next_index,
                    next_tweets[-1]['title']
                    )
                   )
            )
            for idx, tweet in enumerate(next_tweets):
                print('Tweet {} of {}'.format(next_index + idx, self.feed_length))
            if BotFunctions.TweetTimed in self.functionality:
                for tweet in next_tweets:
                    self.api.update_status(
                        '{}\n{} of {}'.format(tweet['text'], next_index, self.feed_length)
                    )
                    next_index += 1
                    sleep(self.min_tweet_delay)
        # Running was made false for some reason
        self.log_event(BotEvents.SYS_Stop)

def main():
    """ Main body for starting up and terminating HaguEigoBot """
    # pylint: disable=no-member
    try:
        authorization = tweepy.OAuthHandler(
            credentials.consumer_key, credentials.consumer_secret
        )
        authorization.set_access_token(
            credentials.access_token, credentials.access_token_secret
        )
        api = tweepy.API(authorization)
        bot = HaguEigoBot(BotFunctions.TestOffline)
        #bot = HaguEigoBot(BotFunctions.Full, api)
        #stream = tweepy.Stream(authorization, bot)

    except KeyboardInterrupt:
        bot.log_events("Terminated at console.")
        bot.disconnect()

if __name__ == '__main__':
    main()
