''' Refer to class HaguEigoBot '''
import os
import re
from time import sleep
from threading import Thread
import datetime
import json
import csv
from shutil import copyfile
from enum import Enum, auto
from flags import Flags
import credentials
import tweepy

'''
TODO:
Take commands using MASTER_ID
favorite all replies
make parallel JSON file to feed to track favorites + retweets "feed_tracking.json"?
log users' next tweet after retweeting bot's tweet
'''

class BotFunctions(Flags):
    """ Determines the functionality of a bot while running """
    LogEvents = 1           #Write to event log file
    TweetOffline = 2        #Run through tweets offline, merely printing them
    SaveTweetIndex = 4      #Save tweeting progress in feed tracking JSON
    TweetOnline = 8         #Tweet from feed_log (requires config.json)
    SaveTweetStats = 16     #Save tweet IDs as they're tweeted plus...
                            #...stats collected from stream.track
    WatchUserStream = 32    #Pull events from stream.userstream
    Interact = 64          #Unimplemented
    Everything = 127
    TestStreamsOnly = 1+32


class BotEvents(Enum):
    """ Event codes for saving to output JSON """
    SYS_Setup = auto()
    SYS_StartThread = auto()
    SYS_Stop = auto()
    SYS_Connect = auto()
    SYS_Disconnect = auto()
    SYS_Command = auto()
    USR_LoadTweet = auto()
    USR_PublishedTweet = auto()
    USR_GetRetweeted = auto()
    USR_GetQuoteRetweeted = auto()
    USR_GetFavorited = auto()
    USR_GetReply = auto()
    USR_GiveReply = auto()
    USR_GetDM = auto()
    USR_GiveDM = auto()
    ERR_KeyboardInterrupt = auto()
    ERR_UnhandledEvent = auto()
    ERR_UnauthorizedCommand = auto()
    ERR_Logic = auto()

''' Log Format

int last_index
list events []
    string "type": "BotEvents.SYS_Start",
    string "text": "BotFunctions()",
    string "time": "2017-05-19 21:26:45.656315"

'''

class HaguEigoBot(tweepy.StreamListener):
    '''
    While running, refreshes a JSON feed and JSON settings file periodically
    so as to deliver content to Twitter. Also, responds to Twitter inputs.
    Requires: credentials.py, CONFIG, FEED
    Will create OUTPUT if it doesn't exist already, to track place in feed and current version
    '''
    CONFIG = "config.json"
    FEED = "feed.json"
    FEED_TRACKING = "feed_tracking.json"
    EVENT_LOG = "event_log.csv"
    TWEET_DELAY = 10
    MY_ID = 862201622939578368
    MASTER_ID = 202527649

    @staticmethod
    def load_tweet_times():
        """
        Loads tweet times from the config file.
        For the moment, that's all the config files does.
        """
        tweet_times = []
        with open(HaguEigoBot.CONFIG) as config_json:
            config = json.load(config_json)
            for time_str in config['tweet_times']:
                tweet_times.append(
                    [int(x) for x in re.search(r'0?([12]?\d):0?([1-5]?\d)', time_str).groups()]
                )
        return tweet_times
    @staticmethod
    def load_tweet_data(feed_index):
        """
        Loads a tweet or chain of tweets at feed_index
        and returns them along with the total tweets available.
        """
        next_tweets = []
        with open(HaguEigoBot.FEED, encoding="utf8") as feed_json:
            feed_data = json.load(feed_json)
            feed_length = len(feed_data)
            if feed_index >= feed_length:
                return (None, feed_length)
            next_tweets.append(feed_data[feed_index])
            while feed_data[feed_index]['chain'] and feed_index < len(feed_data):
                feed_index += 1
                next_tweets.append(feed_data[feed_index])

            feed_index += 1 # Final increment
        return (next_tweets, feed_length)

    @staticmethod
    def load_last_feed_index():
        """
        Loads the feed index saved from a previous session if
        FEED_TRACKING exists
        """
        if os.path.exists(HaguEigoBot.FEED_TRACKING):
            with open(HaguEigoBot.FEED_TRACKING, 'r', encoding="utf8") as loadfile:
                file_tweet_data = json.load(loadfile)
                return file_tweet_data['feed_index']
        else:
            return 0
    @staticmethod
    def _add_to_event_log_file(events):
        """
        Writes to EVENT_LOG to preserve events
        for debugging and review purposes.
        """
        # Overwrite header data (not CSV header)
        with open(HaguEigoBot.EVENT_LOG, 'a', encoding="utf8", newline='\n') as logfile:
            csv_writer = csv.DictWriter(logfile, ['time', 'type', 'text'])
            csv_writer.writerows(events)
            return True
        return False

    def __init__(self, functionality=BotFunctions(), api=None):
        """
        Create an instance of a HaguEigoBot,
        acquire authorization from Twitter (or run offline)
        """
        self.functionality = functionality
        self._event_log = []
        self.log_event(
            BotEvents.SYS_Setup,
            "{:-<50}".format(str(functionality) if functionality else "Offline testing")
        )
        print("{:-^80}".format(str(functionality) if functionality else "Offline testing"))

        self._tweet_thread = None
        self.tweet_times = HaguEigoBot.load_tweet_times()
        self.api = api
        tweepy.StreamListener.__init__(api)
        if(
                BotFunctions.TweetOffline in functionality or
                BotFunctions.TweetOnline in functionality
        ):
            self.running = True
            self._start_tweeting()

    def on_connect(self):
        """Called once connected to streaming server.

        This will be invoked once a successful response
        is received from the server. Allows the listener
        to perform some work prior to entering the read loop.
        """
        self.log_event(BotEvents.SYS_Connect)

    def on_direct_message(self, status):
        """ Called when a new direct message arrives """
        print("Got a direct message.")
        try:
            if status.direct_message['sender_id'] != self.MY_ID:
                self.log_event(
                    BotEvents.USR_GetDM, "{}: {}".format(
                        status.direct_message['sender_screen_name'],
                        status.direct_message['text']
                        )
                    )
                return True
        except BaseException as my_event:
            self.log_event(BotEvents.ERR_Logic, str(my_event), False)

    def on_event(self, status):
        """ Called when a new event arrives.
        This responds to "favorite" and "quoted_tweet."
        """
        if status.event == "favorite": #This tends to come in delayed bunches
            self.log_event(
                BotEvents.USR_GetQuoteRetweeted,
                "{}: {}".format(
                    status.source.screen_name,
                    status.target_object.id
                    )
            )
        elif status.event == "quoted_tweet":
            self.log_event(
                BotEvents.USR_GetQuoteRetweeted,
                "{}: {}".format(
                    status.source['screen_name'],
                    status.target_object['text']
                    )
            )
        elif status.event == "unfavorite":
            pass #feed tracking only requires updating tweet stats based on current totals
        else:
            self.log_event(BotEvents.ERR_UnhandledEvent, "on_event: " + status.event)

    def on_status(self, status):
        """ Called when a new status arrives. """
        if hasattr(status, 'retweeted_status'):
            self.log_event(
                BotEvents.USR_GetRetweeted,
                "{}: {}".format(
                    status.user.screen_name,
                    status.retweeted_status.id
                    )
            )
        elif status.is_quote_status:
            pass #Ignore; this will be picked up by on_event
        elif status.in_reply_to_user_id == HaguEigoBot.MY_ID:
            self.log_event(
                BotEvents.USR_GetReply,
                "{}: {}".format(
                    status.author.screen_name,
                    status.text
                    )
            )
        elif status.author.id == HaguEigoBot.MY_ID and not status.in_reply_to_user_id:
            self.log_event(BotEvents.USR_PublishedTweet, status.id)
            #TODO: Register tweet in feed_tracking.json
        else:
            self.log_event(
                BotEvents.ERR_UnhandledEvent,
                "on_status: " + str(status._json)
            )

    def on_disconnect(self, notice):
        """ Called when Twitter submits an error """
        self.log_event(BotEvents.SYS_Disconnect, notice)
        self.running = False

    def get_next_tweet_datetime(self):
        """ Gets the next datetime at which tweeting will occur. """
        # Supply immediate times if no tweet times and tweeting offline
        if not self.tweet_times and BotFunctions.TweetOffline in self.functionality:
            return datetime.datetime.now() + datetime.timedelta(seconds=HaguEigoBot.TWEET_DELAY*0.2)
        # Offline or not, if there are tweet times, use them
        if self.tweet_times:
            final_time = self.tweet_times[-1]
            now_t = datetime.datetime.now()
            next_t = now_t.replace(
                hour=final_time[0],
                minute=final_time[1],
                second=0,
                microsecond=0)

            if now_t > next_t: #The final time lies before the current
                next_t = next_t + datetime.timedelta(days=1)

            for time in self.tweet_times:
                # Pick apart time tuple, put in next_t
                next_t = next_t.replace(hour=time[0], minute=time[1])
                if now_t < next_t: # If next_t is in the future
                    return next_t.replace(second=0)

        #No viable times were found
        print("No time found!")
        return None

    def log_event(self, ev_type, text="", save=True):
        """ Add an event to the event log before potentially saving. """
        if BotFunctions.LogEvents in self.functionality:
            event = dict()
            event['time'] = datetime.datetime.now().strftime("%m/%d/%y %H:%M:%S")
            event['type'] = str(ev_type)
            event['text'] = text
            self._event_log.append(event)
            if save and HaguEigoBot._add_to_event_log_file(self._event_log):
                self._event_log = []

    def update_feed_index(self, index):
        """ Wrapper for _save_tweet_data; updates feed index """
        self._save_tweet_data(index=index)

    def update_tweet_stats(self, tweet):
        """ Wrapper for _save_tweet_data; updates tweet stats """
        self._save_tweet_data(tweet=tweet)

    def _save_tweet_data(self, index=0, tweet=None):
        """ Saves the current feed index and altered tweet stats. """
        all_tweet_data = dict()
        #Prepare all_tweet_data; attempt to load existing data
        if os.path.exists(HaguEigoBot.FEED_TRACKING): #Load existing data
            with open(HaguEigoBot.FEED_TRACKING, 'r', encoding="utf8") as infile:
                all_tweet_data = json.load(infile)
            copyfile(HaguEigoBot.FEED_TRACKING, HaguEigoBot.FEED_TRACKING + ".bak")
        else:
            all_tweet_data = {"feed_index": 0}
        #Edit all_tweet_data
        if BotFunctions.SaveTweetIndex in self.functionality and index > 0:
            all_tweet_data['feed_index'] = index
        if BotFunctions.SaveTweetStats in self.functionality and tweet:
            if tweet.author.id == HaguEigoBot.MY_ID: #Bot tweeted this
                all_tweet_data['tweet_stats'][tweet.id]['title'] = tweet.title
        #Save all_tweet_data to FEED_TRACKING
        with open(HaguEigoBot.FEED_TRACKING, 'w', encoding="utf8") as outfile:
            json.dump(all_tweet_data, outfile)

    def _start_tweeting(self):
        """ Begin normal functionality loop. """
        self.log_event(BotEvents.SYS_StartThread, "Tweet loop")
        self._tweet_thread = Thread(target=self._tweet_loop)
        self._tweet_thread.start()


    def _tweet_loop(self):
        """ Loop for tweeting, while the stream is open. """
        next_index = self.load_last_feed_index()

        while self.running:
            # Get next tweet(s) ready
            next_tweets, feed_length = self.load_tweet_data(next_index)
            next_index += 1

            if not next_tweets:
                self.log_event(BotEvents.SYS_Stop, "No tweets given (ran out, probably)")
                self.running = False
                break

            # Sleep until time in config
            next_time = self.get_next_tweet_datetime()
            if next_time:
                delta = next_time - datetime.datetime.now()
            else:
                self.log_event(BotEvents.ERR_Logic, "Couldn't get next_time.")
                self.running = False
                break

            print("Wait for {} seconds".format(delta.total_seconds()))
            sleep(delta.total_seconds()) # > WAIT FOR NEXT TWEET TIME <<<<<<<<<<<<<<<<<<<<<<<<<<
            log_str = "{} tweet{} starting at {} ({})".format(
                len(next_tweets),
                's' if (len(next_tweets) > 1) else '',
                next_index,
                next_tweets[-1]['title']
                )
            self.log_event(BotEvents.USR_LoadTweet, log_str)
            print(log_str)

            # Submit each tweet in chain (or just one, if not a chain)
            if BotFunctions.TweetOnline in self.functionality:
                for tweet in next_tweets:
                    self.api.update_status(
                        '{}\n{} of {}'.format(tweet['text'], next_index, feed_length)
                    )
                    next_index += 1
                    sleep(HaguEigoBot.TWEET_DELAY)
            self.update_feed_index(next_index)
        # Running loop ended
        self.log_event(BotEvents.SYS_Stop, "Tweet loop ended.")

def main():
    """ Main body for starting up and terminating HaguEigoBot """
    # pylint: disable=no-member
    # .TestOffline
    try:
        authorization = tweepy.OAuthHandler(
            credentials.consumer_key, credentials.consumer_secret
        )
        authorization.set_access_token(
            credentials.access_token, credentials.access_token_secret
        )
        api = tweepy.API(authorization)
        bot = HaguEigoBot(BotFunctions.TestStreamsOnly, api)
        stream = tweepy.Stream(authorization, bot)
        if BotFunctions.WatchUserStream in bot.functionality:
            stream.userstream()

    except KeyboardInterrupt:
        bot.log_event(BotEvents.SYS_Stop, "Terminated at console.")
        bot.disconnect()

if __name__ == '__main__':
    main()
